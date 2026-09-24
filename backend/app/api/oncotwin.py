"""OncoTwin API — the dynamic digital-twin layer on top of ClinCase.

Mounted at /api/v1/oncotwin. Every route is authenticated and scoped to the
caller's organisation. Clinician decisions (accept / dismiss / investigate,
hand-off to ClinCase, demo reset) require the reviewer or admin role, the
same roles ClinCase uses for its HITL resume endpoint.
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_role
from app.oncotwin import ONCOTWIN_VERSION, runtime
from app.oncotwin.agents import oncotwin_manifest
from app.oncotwin.engine.simulate import SCENARIOS
from app.oncotwin.fhir.mapping import build_bundle, signal_catalog
from app.oncotwin.ml.model import ModelArtifactError, load_model
from app.oncotwin.outcome import OUTCOME_DEFINITION, QUALIFYING_CONDITIONS
from app.oncotwin.service import compute_twin, twin_card
from app.oncotwin.store import OrgTwinStore, get_store

router = APIRouter(prefix="/oncotwin", tags=["oncotwin"])
Clinician = require_role("reviewer", "admin")


def clean(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays so every payload is JSON-safe."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if np.isnan(v) else v
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    return obj


async def org_store(user: dict[str, Any] = Depends(get_current_user)) -> OrgTwinStore:
    store = await asyncio.to_thread(get_store, user["organization_id"])
    await store.ledger.load_tip()
    return store


async def _persist(store: OrgTwinStore, entries: list[dict[str, Any] | None]) -> None:
    for e in entries:
        if e is not None:
            await store.ledger.persist(e)
    await store.bus.flush_outbox()      # forward queued twin events to ClinCase's outbox (fail-soft)


def _actor(user: dict[str, Any]) -> str:
    return f"{user.get('email', user.get('id'))} ({user.get('role')})"


def _patient_or_404(store: OrgTwinStore, pid: str):
    try:
        return store.patient(pid)
    except KeyError as e:
        raise HTTPException(404, f"Twin patient {pid!r} not found") from e


def _model_or_503():
    try:
        return load_model()
    except ModelArtifactError as e:
        raise HTTPException(503, str(e)) from e


# =============================================================================
# Definitions
# =============================================================================


@router.get("/overview")
async def overview(store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    model = _model_or_503()
    return clean({
        "name": "OncoTwin",
        "tagline": ("We don't just store a patient's history. We continuously model how the patient's health is "
                    "changing, detect deviations from their personal baseline, simulate possible trajectories, and "
                    "give clinicians transparent decision support."),
        "oncotwin_version": ONCOTWIN_VERSION,
        "outcome": OUTCOME_DEFINITION,
        "model": model.version_info(),
        "headline_metrics": {
            "data": model.artifact["metrics"]["data"],
            "day_level": model.artifact["metrics"]["day_level"],
            "event_level": model.artifact["metrics"]["event_level"],
            "comparators": model.artifact["comparators"],
        },
        "patients": len(store.patients),
        "open_alerts": sum(1 for a in store.alerts.values() if a["status"] in ("open", "investigating")),
        "ledger": store.ledger.verify(),
        "decision_support_notice": ("Clinical decision support only — not a diagnosis, not a treatment decision, "
                                    "not a medical device. All demo patients are synthetic."),
    })


@router.get("/outcome")
async def outcome(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"outcome": OUTCOME_DEFINITION, "qualifying_conditions": QUALIFYING_CONDITIONS}


@router.get("/model")
async def model_card(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return clean(_model_or_503().card())


@router.get("/signals")
async def signals(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"signals": signal_catalog(),
            "note": "Mapping adapters for HealthKit / Health Connect-shaped samples; no live vendor connection is shipped."}


@router.get("/agents/manifest")
async def agents_manifest(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return clean(oncotwin_manifest())


@router.get("/scenarios")
async def scenario_catalog(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"scenarios": SCENARIOS}


# =============================================================================
# Patients
# =============================================================================


@router.get("/patients")
async def list_patients(store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _model_or_503()
    rows = await asyncio.to_thread(lambda: [runtime.patient_summary(store, pid) for pid in store.patients])
    return clean({"patients": rows, "synthetic": True})


@router.get("/patients/{pid}")
async def patient_dashboard(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                            simulate: bool = True, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    return clean(await asyncio.to_thread(runtime.dashboard, store, pid, as_of_day, simulate=simulate))


@router.get("/patients/{pid}/replay")
async def patient_replay(pid: str, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    return clean(await asyncio.to_thread(runtime.replay, store, pid))


@router.get("/patients/{pid}/timeline")
async def patient_timeline(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                           store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    return clean(await asyncio.to_thread(runtime.timeline, store, pid, as_of_day))


@router.get("/patients/{pid}/fhir")
async def patient_fhir(pid: str, as_of_day: int | None = Query(default=None, ge=1), include_daily: bool = True,
                       store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    st = _patient_or_404(store, pid)
    day = min(as_of_day or st.live_day, st.live_day)
    return clean(build_bundle(st.record(), day, include_daily=include_daily))


class SimulateRequest(BaseModel):
    as_of_day: int | None = Field(default=None, ge=1)
    scenarios: list[Literal["current", "early_intervention", "improved_recovery",
                            "reduced_adherence", "regimen_change"]] | None = None


@router.post("/patients/{pid}/simulate")
async def patient_simulate(pid: str, req: SimulateRequest, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    st = _patient_or_404(store, pid)
    model = _model_or_503()

    def run() -> dict[str, Any]:
        hist = runtime.history_for(st)
        day = min(req.as_of_day or st.live_day, st.live_day)
        comp = compute_twin(st.record(), day, history=[h for h in hist if h["day"] <= day],
                            simulate=list(req.scenarios or SCENARIOS), model=model)
        return {"as_of_day": day, "current_risk": comp.prediction["risk"], "tier": comp.prediction["tier"],
                "card": twin_card(comp), "simulation": comp.simulation}

    return clean(await asyncio.to_thread(run))


class AdvanceRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=14)


@router.post("/patients/{pid}/advance")
async def patient_advance(pid: str, req: AdvanceRequest, user: dict[str, Any] = Depends(get_current_user),
                          store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    res = await asyncio.to_thread(runtime.advance, store, pid, req.days, actor=_actor(user))
    await _persist(store, res.pop("entries"))
    return clean(res)


@router.post("/patients/{pid}/evaluate")
async def patient_evaluate(pid: str, user: dict[str, Any] = Depends(get_current_user),
                           store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    res = await asyncio.to_thread(runtime.commit_evaluation, store, pid, actor=_actor(user),
                                  trigger="manual evaluation", force_simulation=True)
    await _persist(store, [res["evaluation"], res["alert_entry"]])
    return clean({k: res[k] for k in ("evaluation", "alert", "agent_trace", "tier", "risk", "as_of_day")})


class InjectRequest(BaseModel):
    kind: Literal["infection", "dehydration", "nonadherence"]


@router.post("/patients/{pid}/inject")
async def patient_inject(pid: str, req: InjectRequest, user: dict[str, Any] = Depends(get_current_user),
                         store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    try:
        res = await asyncio.to_thread(runtime.inject, store, pid, req.kind, actor=_actor(user))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    await _persist(store, [res["entry"]])
    return clean(res)


class IngestRequest(BaseModel):
    fhir_observations: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    wearable_samples: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


@router.post("/patients/{pid}/observations")
async def patient_ingest(pid: str, req: IngestRequest, user: dict[str, Any] = Depends(get_current_user),
                         store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    res = await asyncio.to_thread(runtime.ingest, store, pid, req.model_dump(), actor=_actor(user))
    await _persist(store, [res["entry"], *res.pop("extra_entries", [])])
    return clean(res)


# =============================================================================
# Alerts + HITL
# =============================================================================


@router.get("/alerts")
async def list_alerts(patient_id: str | None = None, status: str | None = None,
                      store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    rows = [runtime.alert_summary(a) for a in store.alerts.values()
            if (patient_id is None or a["patient_id"] == patient_id) and (status is None or a["status"] == status)]
    rows.sort(key=lambda a: a["created_at"], reverse=True)
    return clean({"alerts": rows})


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    alert = store.alerts.get(alert_id)
    if alert is None:
        raise HTTPException(404, f"Alert {alert_id!r} not found")
    return clean(alert)


@router.get("/alerts/{alert_id}/why")
async def alert_why(alert_id: str, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    try:
        return clean(runtime.why(store, alert_id))
    except KeyError as e:
        raise HTTPException(404, f"Alert {alert_id!r} not found") from e


class AlertActionRequest(BaseModel):
    action: Literal["accept", "dismiss", "investigate"]
    note: str | None = Field(default=None, max_length=2000)


@router.post("/alerts/{alert_id}/action")
async def alert_action(alert_id: str, req: AlertActionRequest, user: dict[str, Any] = Depends(Clinician),
                       store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    try:
        res = runtime.act_on_alert(store, alert_id, req.action, req.note, user)
    except KeyError as e:
        raise HTTPException(404, f"Alert {alert_id!r} not found") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    await _persist(store, [res["entry"]])
    return clean(res)


class RequestedTreatment(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    hcpcs_code: str | None = Field(default=None, max_length=20)
    j_code: str | None = Field(default=None, max_length=20)
    dose: str | None = Field(default=None, max_length=300)
    frequency: str | None = Field(default=None, max_length=120)
    intent: str | None = Field(default=None, max_length=200)


class HandoffRequest(BaseModel):
    requested_treatment: RequestedTreatment | None = None


@router.post("/alerts/{alert_id}/handoff")
async def alert_handoff(alert_id: str, req: HandoffRequest, user: dict[str, Any] = Depends(Clinician),
                        store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    override = req.requested_treatment.model_dump() if req.requested_treatment else None
    try:
        res = await runtime.handoff(store, alert_id, user, override)
    except KeyError as e:
        raise HTTPException(404, f"Alert {alert_id!r} not found") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    await _persist(store, [res.get("entry")])
    return clean({k: v for k, v in res.items() if k != "entry"})


# =============================================================================
# Audit + demo controls
# =============================================================================


@router.get("/audit")
async def audit(patient_id: str | None = None, limit: int = Query(default=200, ge=1, le=2000),
                store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    return clean(runtime.audit(store, patient_id, limit))


@router.post("/demo/reset")
async def demo_reset(user: dict[str, Any] = Depends(Clinician), store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    await asyncio.to_thread(store.reset)
    entry = store.ledger.append("demo_reset", patient_id=None, actor=_actor(user), payload={
        "notice": "Demo patients, twin clocks and alerts reset to their seeded state. The audit ledger is NOT reset."})
    await _persist(store, [entry])
    return clean({"reset": True, "entry": entry})
