"""OncoTwin 2.0 API — twin intelligence, clinical loop, MLOps, research and observability.

Mounted at /api/v1/oncotwin next to the original OncoTwin router (whose routes
are unchanged). Every route is authenticated and scoped to the caller's
organisation. Clinical actions (recording an intervention) need the reviewer or
admin role — the same roles ClinCase uses for HITL. Developer tools (Research
Lab experiment runs, the red-team stress test) are admin-only. Request bodies are
bounded pydantic models; free text is length-limited.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.oncotwin import _actor, _model_or_503, _patient_or_404, _persist, clean, org_store
from app.auth import get_current_user, require_role
from app.oncotwin import ONCOTWIN_VERSION, runtime
from app.oncotwin.engine.simulate import SCENARIOS
from app.oncotwin.observability import METRICS
from app.oncotwin.store import OrgTwinStore

router = APIRouter(prefix="/oncotwin", tags=["oncotwin-intelligence"])
Clinician = require_role("reviewer", "admin")
Admin = require_role("admin")
ScenarioKey = Literal["current", "early_intervention", "improved_recovery", "reduced_adherence", "regimen_change"]
Group = Literal["wearables", "home", "symptoms", "multi_signal", "labs_twin", "treatment", "adherence", "demographics"]


def _intel(store: OrgTwinStore, pid: str, day: int | None) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    return runtime.intelligence(store, pid, day)


# =============================================================================
# Clinical Command Center + per-patient intelligence
# =============================================================================


@router.get("/command-center")
async def command_center(store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _model_or_503()
    return clean(await asyncio.to_thread(runtime.command_center, store))


@router.get("/patients/{pid}/intelligence")
async def intelligence(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                       store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    return clean(await asyncio.to_thread(_intel, store, pid, as_of_day))


@router.get("/patients/{pid}/state")
async def twin_state(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                     store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    it = await asyncio.to_thread(_intel, store, pid, as_of_day)
    return clean({"as_of_day": it["as_of_day"], "state": it["state"], "transitions_recent": it["transitions_recent"],
                  "what_changed": it["what_changed"], "triage": it["triage"]})


@router.get("/patients/{pid}/transitions")
async def twin_transitions(pid: str, from_day: int = Query(default=2, ge=2), to_day: int | None = Query(default=None, ge=1),
                           store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.intel.state import transitions

    st = _patient_or_404(store, pid)
    states = await asyncio.to_thread(runtime.states_for, st)
    return clean({"patient_id": pid, "transitions": transitions(states, from_day=from_day, to_day=to_day or st.live_day),
                  "note": "Categorical status changes of the Living Twin State; historical states are never overwritten."})


@router.get("/patients/{pid}/what-changed")
async def what_changed(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                       compare_to: int | None = Query(default=None, ge=1),
                       store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.intel.explain import what_changed as wc

    st = _patient_or_404(store, pid)
    states = await asyncio.to_thread(runtime.states_for, st)
    return clean(wc(states, min(as_of_day or st.live_day, st.live_day), compare_to))


@router.get("/patients/{pid}/why-now")
async def why_now(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                  store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    it = await asyncio.to_thread(_intel, store, pid, as_of_day)
    return clean({"why_now": it["why_now"], "show_your_work": it["show_your_work"], "readiness": it["readiness"]})


@router.get("/patients/{pid}/graph")
async def state_graph(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                      store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    it = await asyncio.to_thread(_intel, store, pid, as_of_day)
    return clean(it["graph"])


@router.get("/patients/{pid}/features")
async def features(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                   store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.features.store import materialize
    from app.oncotwin.service import compute_twin

    st = _patient_or_404(store, pid)
    model = _model_or_503()

    def run() -> dict[str, Any]:
        hist = runtime.history_for(st)
        day = min(as_of_day or st.live_day, st.live_day)
        return materialize(compute_twin(st.record(), day, history=[h for h in hist if h["day"] <= day], model=model))
    return clean(await asyncio.to_thread(run))


class ExplainRequest(BaseModel):
    as_of_day: int | None = Field(default=None, ge=1)
    use_llm: bool | None = None


@router.post("/patients/{pid}/explain")
async def explain(pid: str, req: ExplainRequest, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.intel.narrative import explain as run_explain

    st = _patient_or_404(store, pid)
    it = await asyncio.to_thread(_intel, store, pid, req.as_of_day)
    return clean(await run_explain(st.record(), it, model_integrity=_model_or_503().integrity_verified,
                                   use_llm=req.use_llm, traces=store.llm_traces))


@router.get("/patients/{pid}/clinical-context")
async def clinical_context(pid: str, as_of_day: int | None = Query(default=None, ge=1),
                           store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.intel.analysis import stage_context
    from app.oncotwin.service import compute_twin

    st = _patient_or_404(store, pid)
    model = _model_or_503()
    day = min(as_of_day or st.live_day, st.live_day)
    hist = await asyncio.to_thread(runtime.history_for, st)
    comp = await asyncio.to_thread(compute_twin, st.record(), day, history=[h for h in hist if h["day"] <= day], model=model)
    ctx = await stage_context(comp, store.organization_id)
    alerts = [runtime.alert_summary(a) for a in store.alerts.values() if a["patient_id"] == pid]
    ids = {a["id"] for a in alerts}
    return clean({**ctx, "as_of_day": day, "tier": comp.prediction["tier"], "alerts": alerts,
                  "handoffs": [h for h in store.handoffs if h.get("alert_id") in ids]})


# =============================================================================
# What-if + counterfactual + clinical loop
# =============================================================================


class ScenarioParams(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    adherence: float | None = Field(default=None, ge=0.0, le=1.0)
    gcsf_tomorrow: bool = False
    antibiotics_start_day_offset: int | None = Field(default=None, ge=1, le=10)
    antibiotics_days: int = Field(default=7, ge=1, le=14)
    iv_hydration_day_offsets: list[int] = Field(default_factory=list, max_length=5)
    oral_hydration_coaching: bool = False
    activity_program: bool = False
    next_dose_scale: float = Field(default=1.0, ge=0.5, le=1.0)
    delay_next_dose_days: int = Field(default=0, ge=0, le=7)
    gcsf_with_next_cycle: bool | None = None
    new_infection: bool = False


class WhatIfRequest(BaseModel):
    as_of_day: int | None = Field(default=None, ge=1)
    scenarios: list[ScenarioKey] | None = None
    custom: ScenarioParams | None = None


@router.post("/patients/{pid}/whatif")
async def whatif(pid: str, req: WhatIfRequest, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.service import compute_twin, provenance

    st = _patient_or_404(store, pid)
    model = _model_or_503()

    def run() -> dict[str, Any]:
        hist = runtime.history_for(st)
        day = min(req.as_of_day or st.live_day, st.live_day)
        with METRICS.timed("oncotwin_whatif"):
            comp = compute_twin(st.record(), day, history=[h for h in hist if h["day"] <= day], model=model,
                                simulate=list(req.scenarios or SCENARIOS),
                                custom_scenario=req.custom.model_dump(exclude_none=True) if req.custom else None)
        prov = provenance(comp)
        return {"as_of_day": day, "risk": comp.prediction["risk"], "tier": comp.prediction["tier"],
                "simulation": comp.simulation,
                "observed": [{"day": h["day"], "risk": h["risk"], "risk_p10": h["risk_p10"], "risk_p90": h["risk_p90"],
                              "tier": h["tier"]} for h in hist if day - 13 <= h["day"] <= day],
                "data_used": {"as_of_day": day, "input_sha256": prov["input_sha256"], "n_inputs": prov["n_inputs"],
                              "model": comp.prediction["model"]},
                "label": "Simulation — not a clinical prediction or treatment recommendation."}
    return clean(await asyncio.to_thread(run))


@router.get("/patients/{pid}/counterfactual")
async def counterfactual(pid: str, anchor_day: int | None = Query(default=None, ge=2),
                         scenario: ScenarioKey = "current", store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    return clean(await asyncio.to_thread(runtime.counterfactual_view, store, pid, anchor_day, scenario=scenario))


@router.get("/interventions/catalog")
async def intervention_catalog(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"interventions": [{"kind": k, "label": v} for k, v in runtime.INTERVENTIONS.items()],
            "note": ("Recording an intervention changes the synthetic patient's world from the next twin day "
                     "(the past is verified unchanged); in production the EHR would supply the order as data.")}


class InterventionRequest(BaseModel):
    kind: Literal["urgent_eval_abx", "gcsf", "gcsf_secondary", "hydration", "adherence_support", "dose_reduction", "activity"]
    note: str | None = Field(default=None, max_length=2000)
    alert_id: str | None = Field(default=None, max_length=40, pattern=r"^ota_[0-9a-f]{6,32}$")


@router.post("/patients/{pid}/interventions")
async def record_intervention(pid: str, req: InterventionRequest, user: dict[str, Any] = Depends(Clinician),
                              store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    try:
        res = await asyncio.to_thread(runtime.record_intervention, store, pid, req.kind, req.note, user, req.alert_id)
    except KeyError as e:
        raise HTTPException(404, f"Alert {req.alert_id!r} not found for this patient") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    await _persist(store, [res["entry"]])
    return clean(res)


@router.get("/patients/{pid}/knowledge")
async def knowledge(pid: str, entry_id: str | None = Query(default=None, max_length=40),
                    day: int | None = Query(default=None, ge=1), store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _patient_or_404(store, pid)
    _model_or_503()
    try:
        return clean(await asyncio.to_thread(runtime.knowledge, store, pid, entry_id=entry_id, day=day))
    except KeyError as e:
        raise HTTPException(404, f"Evaluation {entry_id!r} not found for this patient") from e


# =============================================================================
# Feature store · models · MLOps · events · observability
# =============================================================================


@router.get("/feature-store/registry")
async def feature_registry(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.features.store import registry
    return clean(registry())


@router.get("/models/registry")
async def model_registry(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.ml.registry import registry
    return clean(await asyncio.to_thread(registry))


@router.get("/models/horizon")
async def horizon_card(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.ml.horizon import load_horizon_model
    hm = load_horizon_model()
    if hm is None:
        raise HTTPException(503, "Horizon model not trained (python -m app.oncotwin.ml.horizon).")
    return clean({k: v for k, v in hm.artifact.items() if k not in ("coef", "mean", "std", "bootstrap")}
                 | {"integrity_verified": hm.integrity_verified})


@router.get("/mlops/predictions")
async def predictions(patient_id: str | None = None, limit: int = Query(default=200, ge=1, le=2000),
                      store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.mlops.predictions import live_metrics
    metrics = await asyncio.to_thread(live_metrics, store)
    rows = [r for r in store.predictions if patient_id is None or r["patient_id"] == patient_id]
    return clean({"metrics": metrics, "predictions": rows[-limit:][::-1]})


@router.get("/mlops/drift")
async def drift(refresh: bool = False, store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    _model_or_503()
    return clean(await asyncio.to_thread(runtime.drift_status, store, refresh=refresh))


@router.get("/events")
async def events(patient_id: str | None = None, category: Literal["data", "twin", "hitl", "mlops"] | None = None,
                 limit: int = Query(default=200, ge=1, le=2000), store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    return clean({"events": store.bus.recent(limit, patient_id, category), "stats": store.bus.stats()})


@router.get("/observability")
async def observability(store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.mlops.predictions import live_metrics
    return clean({
        "oncotwin_version": ONCOTWIN_VERSION, "metrics": METRICS.snapshot(), "events": store.bus.stats(),
        "agent_runs": list(store.agent_runs)[-30:][::-1], "llm_traces": store.llm_traces[-30:][::-1],
        "predictions": await asyncio.to_thread(live_metrics, store),
        "drift": (store.drift_cache or (None, {"status": "not computed yet"}))[1],
        "ledger": store.ledger.verify(),
        "stress_test": store.stress_runs[-1] if store.stress_runs else None,
        "logging": "structlog JSON to stdout (application, event handlers, ledger persistence); no patient text in metrics",
    })


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus(_: dict[str, Any] = Depends(get_current_user)) -> str:
    return METRICS.prometheus()


@router.get("/health")
async def health(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.ml.horizon import load_horizon_model
    from app.oncotwin.ml.model import ModelArtifactError, load_model
    from app.oncotwin.mlops.drift import load_reference
    from app.oncotwin.research.benchmark import load_results

    checks: dict[str, Any] = {}
    try:
        m = load_model()
        checks["deterioration_model"] = {"ok": m.integrity_verified, "sha256": m.sha256[:16]}
    except ModelArtifactError as e:
        checks["deterioration_model"] = {"ok": False, "error": str(e)}
    hm = load_horizon_model()
    checks["horizon_model"] = {"ok": bool(hm and hm.integrity_verified)}
    checks["drift_reference_profile"] = {"ok": load_reference() is not None}
    checks["benchmark_results"] = {"ok": load_results() is not None}
    return {"status": "ok" if all(c["ok"] for c in checks.values()) else "degraded", "checks": checks,
            "oncotwin_version": ONCOTWIN_VERSION}


# =============================================================================
# Twin Research Lab (results for everyone; runs admin-only) + Stress Test (admin)
# =============================================================================

_JOBS: dict[str, dict[str, Any]] = {}
_JOB_LOCK = threading.Lock()


@router.get("/research/results")
async def research_results(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.research.benchmark import load_results
    res = await asyncio.to_thread(load_results)
    if res is None:
        raise HTTPException(503, "Benchmark not run yet (python -m app.oncotwin.research.benchmark).")
    return clean(res)


@router.get("/research/options")
async def research_options(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from app.oncotwin.research.lab import ALL_GROUPS, GROUP_LABELS, MODELS
    return {"groups": [{"id": g, "label": GROUP_LABELS[g]} for g in ALL_GROUPS], "models": MODELS,
            "baselines": ["personal", "population"], "horizons": [1, 3, 7],
            "datasets": [{"id": "synthetic-cohort-20260923-1000",
                          "label": "Synthetic cohort (1 000 patients, seed 20260923) — same split as the deployed model"}],
            "metrics": ["AUROC (95 % patient-bootstrap CI)", "AUPRC", "Brier", "ECE", "precision", "recall", "F1",
                        "false-alert onsets / 100 patient-days", "events detected", "median lead time"]}


class ExperimentRequest(BaseModel):
    name: str = Field(default="Custom experiment", max_length=80)
    groups: list[Group] = Field(default_factory=lambda: ["wearables", "home", "symptoms", "multi_signal", "labs_twin",
                                                         "treatment", "adherence", "demographics"], max_length=8)
    baseline: Literal["personal", "population"] = "personal"
    horizon: Literal[1, 3, 7] = 7
    model: Literal["logistic", "anomaly_score", "vital_threshold_rule"] = "logistic"
    compare_to_reference: bool = True


def _run_job(job_id: str, req: ExperimentRequest) -> None:
    from app.oncotwin.research.dataset import load_cohort
    from app.oncotwin.research.lab import ALL_GROUPS, ExperimentConfig, run

    job = _JOBS[job_id]
    try:
        job.update(status="loading dataset")
        cohort = load_cohort(progress=lambda i, n: job.update(progress=round(i / n, 3), status=f"building cohort {i}/{n}"))
        job.update(status="training + evaluating", progress=1.0)
        groups = tuple(g for g in ALL_GROUPS if g in req.groups) or ("wearables",)
        cfg = ExperimentConfig(req.name, groups, baseline=req.baseline, horizon=req.horizon, model=req.model)
        ref = (ExperimentConfig("Multimodal Digital Twin (reference)", ALL_GROUPS, horizon=req.horizon)
               if req.compare_to_reference else None)
        job.update(status="done", result=run(cohort, cfg, ref), finished_at=time.time())
    except Exception as e:  # noqa: BLE001 — surfaced to the researcher, never swallowed
        job.update(status="error", error=f"{type(e).__name__}: {e}")


@router.post("/research/experiments")
async def start_experiment(req: ExperimentRequest, user: dict[str, Any] = Depends(Admin)) -> dict[str, Any]:
    if req.model == "anomaly_score" and "multi_signal" not in req.groups:
        raise HTTPException(422, "The anomaly-score model needs the multi_signal group.")
    with _JOB_LOCK:
        if any(j["status"] not in ("done", "error") for j in _JOBS.values()):
            raise HTTPException(409, "An experiment is already running; one at a time.")
        job_id = f"otx_{uuid.uuid4().hex[:10]}"
        _JOBS[job_id] = {"id": job_id, "status": "queued", "progress": 0.0, "config": req.model_dump(),
                         "started_by": user.get("email"), "started_at": time.time(), "result": None, "error": None}
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return {"job": _JOBS[job_id]}


@router.get("/research/experiments/{job_id}")
async def experiment_status(job_id: str, _: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, f"Experiment {job_id!r} not found")
    return clean(job)


@router.post("/stress-test")
async def stress_test(user: dict[str, Any] = Depends(Admin), store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    from app.oncotwin.stress import run_all
    res = await asyncio.to_thread(run_all)
    res.update(run_by=user.get("email"), at=runtime._now())
    store.stress_runs.append(res)
    entry = store.ledger.append("stress_test", patient_id=None, actor=_actor(user), payload={
        "passed": res["passed"], "total": res["total"], "failed": [r["id"] for r in res["results"] if not r["passed"]]})
    await _persist(store, [entry])
    return clean(res)


@router.get("/stress-test/latest")
async def stress_latest(store: OrgTwinStore = Depends(org_store)) -> dict[str, Any]:
    return clean(store.stress_runs[-1] if store.stress_runs else {"status": "not run yet"})


ARCHITECTURE = [
    {"component": "FastAPI services (this backend)", "status": "implemented",
     "why": "one API surface for ClinCase + OncoTwin, authenticated and organisation-scoped",
     "data": "FHIR / wearable ingestion, twin reads, HITL actions", "if_it_fails": "API unavailable; ledger already persisted"},
    {"component": "In-process TwinEventBus → ClinCase transactional outbox", "status": "implemented (outbox bridge fail-soft)",
     "why": "new data update the twin incrementally; downstream consumers decouple through the outbox",
     "data": "typed CloudEvents oncotwin.<Event>.v1", "if_it_fails": "events stay in the in-process log marked bridged=false"},
    {"component": "Amazon EventBridge / Kinesis (ClinCase outbox publisher)", "status": "designed — enabled by EVENT_BUS_TARGET",
     "why": "fan-out to other services without coupling", "data": "outbox rows",
     "if_it_fails": "outbox rows stay pending and are retried (SKIP LOCKED drain)"},
    {"component": "PostgreSQL (Amazon RDS)", "status": "implemented (write-through, fail-soft)",
     "why": "durable hash-chained audit ledger + outbox + ClinCase cases", "data": "oncotwin_audit, event_outbox",
     "if_it_fails": "the in-process ledger stays authoritative for the running demo"},
    {"component": "Model artifacts (JSON, SHA-256 verified; Amazon S3 in production)", "status": "implemented locally",
     "why": "versioned, integrity-checked models and reference profiles",
     "data": "deterioration_lr_v1, horizon_survival_v1, reference_profile_v1",
     "if_it_fails": "503 for predictions; an integrity failure suppresses every confident statement"},
    {"component": "Amazon Bedrock (via ClinCase GenAI gateway)", "status": "optional (ONCOTWIN_LLM_EXPLANATIONS=1)",
     "why": "explanation synthesis only — never quantitative work", "data": "computed evidence JSON",
     "if_it_fails": "the deterministic explanation is shown; the trace records the error"},
    {"component": "Amazon SageMaker", "status": "not used — deliberately",
     "why": "the numpy models train in minutes on a CPU; SageMaker would add cost without a current need",
     "data": "—", "if_it_fails": "—"},
    {"component": "Prometheus / Amazon CloudWatch", "status": "implemented (/oncotwin/metrics + structlog JSON)",
     "why": "latency, error, event and safety-gate metrics for alerting", "data": "bounded-cardinality metrics, no patient data",
     "if_it_fails": "a metrics gap; the service is unaffected"},
    {"component": "AWS Secrets Manager / KMS / IAM", "status": "inherited from the ClinCase deployment (ops/terraform)",
     "why": "no secrets in code, encryption at rest, least-privilege roles", "data": "credentials, keys",
     "if_it_fails": "fails closed — no credentials, no database / LLM"},
]


@router.get("/architecture")
async def architecture(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Every infrastructure component: why it exists, what flows through it, what happens if it fails, its status."""
    return {"components": ARCHITECTURE}
