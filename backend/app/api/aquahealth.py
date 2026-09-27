"""AquaHealth API — the OneAquaHealth freshwater-ecosystem module.

Mounted at /api/v1/aquahealth. Purely additive: no existing ClinCase route
changes, and the clinical prior-authorisation workflow is untouched. Auth,
roles and tenancy reuse ClinCase's own dependencies, so an AquaHealth
observation is scoped to the caller's organisation exactly like a clinical
case is.

Role model mirrors ClinCase's:
  • any authenticated user may submit and read observations (citizen science);
  • `reviewer` / `admin` may complete the human-in-the-loop review and manage
    the demonstration dataset — the same roles that gate ClinCase's clinical
    HITL resume endpoint.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.aquahealth import demo as demo_data
from app.aquahealth import service, store
from app.aquahealth.agents.env_agents import aquahealth_manifest
from app.aquahealth.fhir import mapping
from app.aquahealth.models import (
    DashboardOverview,
    Observation,
    ObservationCreate,
    ReviewRequest,
)
from app.aquahealth.vocab import (
    BIODIVERSITY_FIELDS,
    CONTEXT_FIELDS,
    WATER_APPEARANCE_FIELDS,
    DataSource,
    EcosystemStatus,
    Presence,
    ReviewStatus,
    VerificationState,
)
from app.auth import get_current_user, require_role

router = APIRouter(prefix="/aquahealth", tags=["aquahealth"])

Reviewer = require_role("reviewer", "admin")

MODULE_VERSION = "0.1.0"


async def org_store(
    user: dict[str, Any] = Depends(get_current_user),
) -> store.OrgAquaStore:
    """Resolve the caller's organisation store, rehydrating once per process.

    The DB load is attempted exactly once per store; when no database is
    configured it is a no-op and the in-process store stands alone, which is
    the DB-less mode ClinCase already supports.
    """
    st = store.get_store(user["organization_id"])
    if not st.loaded_from_db:
        await store.load_from_db(user["organization_id"])
        st.loaded_from_db = True
    return st


def _actor(user: dict[str, Any]) -> str:
    return f"{user.get('email', user.get('id'))} ({user.get('role')})"


def _observation_or_404(st: store.OrgAquaStore, observation_id: str) -> Observation:
    obs = st.observation(observation_id)
    if obs is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    return obs


# =============================================================================
# Module metadata
# =============================================================================


@router.get("/meta")
async def aquahealth_meta() -> dict[str, Any]:
    """What this module is, in machine-readable form.

    Unauthenticated so the landing surface can describe the module without a
    session, matching ClinCase's own public metadata endpoints.
    """
    return {
        "module": "AquaHealth",
        "version": MODULE_VERSION,
        "parent_product": "ClinCase",
        "summary": (
            "Urban freshwater ecosystem monitoring and One Health intelligence, "
            "added to ClinCase for the IEEE OneAquaHealth challenge."
        ),
        "case_type": "ENVIRONMENTAL_OBSERVATION",
        "disclaimers": {
            "status": (
                "Ecosystem status is a Prototype Ecosystem Observation Status, "
                "not a validated environmental index."
            ),
            "ai": (
                "AI assessments are prototype, deterministic and always require "
                "human verification."
            ),
            "interoperability": mapping.STANDARDS_NOTE,
        },
        "statuses": service.status_catalog(),
        "presence_values": [
            {"value": p.value, "informative": p.is_informative} for p in Presence
        ],
        "data_sources": [s.value for s in DataSource],
        "verification_states": [v.value for v in VerificationState],
    }


@router.get("/form-schema")
async def form_schema() -> dict[str, Any]:
    """Field catalogue driving the citizen observation form.

    Served from the same constants the agents read, so the form can never
    drift from what the assessment logic actually interprets.
    """
    return {
        "presence_options": [
            {"value": Presence.OBSERVED.value, "label": "Observed"},
            {"value": Presence.NOT_OBSERVED.value, "label": "Not observed"},
            {"value": Presence.UNKNOWN.value, "label": "Unknown"},
            {"value": Presence.NOT_AVAILABLE.value, "label": "Not available"},
        ],
        "guidance": (
            "Answer only what you actually saw. 'Not observed' means you looked "
            "and it was not there — that is useful information. 'Unknown' and "
            "'Not available' mean you could not check, and are never treated as "
            "evidence."
        ),
        "sections": [
            {
                "key": "appearance",
                "label": "Water appearance",
                "fields": [{"code": c, "label": lab} for c, lab in WATER_APPEARANCE_FIELDS],
            },
            {
                "key": "biodiversity",
                "label": "Biodiversity",
                "fields": [{"code": c, "label": lab} for c, lab in BIODIVERSITY_FIELDS],
            },
            {
                "key": "context",
                "label": "Environmental context",
                "fields": [{"code": c, "label": lab} for c, lab in CONTEXT_FIELDS],
            },
        ],
        "clarity_options": [
            {"value": "clear", "label": "Clear"},
            {"value": "slightly_cloudy", "label": "Slightly cloudy"},
            {"value": "cloudy", "label": "Cloudy"},
            {"value": "opaque", "label": "Opaque / cannot see through"},
            {"value": "unknown", "label": "Unknown"},
        ],
        "measurements": [
            {"code": "ph", "label": "pH", "unit": "", "min": 0, "max": 14},
            {
                "code": "water_temperature_c", "label": "Water temperature",
                "unit": "C", "min": -5, "max": 60,
            },
            {
                "code": "turbidity_ntu", "label": "Turbidity",
                "unit": "NTU", "min": 0, "max": 5000,
            },
            {
                "code": "dissolved_oxygen_mgl", "label": "Dissolved oxygen",
                "unit": "mg/L", "min": 0, "max": 25,
            },
        ],
        "measurement_note": (
            "All measurements are optional. An observation with no instrument "
            "readings is still a complete and useful contribution."
        ),
        "waterbody_kinds": [
            "stream", "river", "lake", "pond", "canal", "wetland", "other",
        ],
    }


@router.get("/agents/manifest")
async def agents_manifest(
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """The AquaHealth agent manifest.

    Separate from ClinCase's `/agents/manifest`, which continues to report its
    own clinical agents unchanged.
    """
    return aquahealth_manifest()


# =============================================================================
# Dashboard / aggregates
# =============================================================================


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    st: store.OrgAquaStore = Depends(org_store),
) -> DashboardOverview:
    """Counts, distributions, recent observations and active warnings."""
    return service.dashboard(st)


@router.get("/map")
async def map_view(
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Observation locations with status, confidence and review state."""
    return {
        "points": service.map_points(st),
        "waterbodies": [
            {
                "id": w.id,
                "name": w.name,
                "kind": w.kind,
                "locality": w.locality,
                "latitude": w.location.latitude if w.location else None,
                "longitude": w.location.longitude if w.location else None,
                "is_demo": w.is_demo,
            }
            for w in st.waterbodies()
        ],
        "statuses": service.status_catalog(),
    }


@router.get("/trends")
async def trends(
    waterbody_id: str | None = Query(default=None),
    days: int = Query(default=90, ge=7, le=365),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Observation time series. Says so plainly when there is too little data."""
    return service.trends(st, waterbody_id=waterbody_id, days=days)


@router.get("/one-health")
async def one_health(
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Ecosystem -> biodiversity/animal -> community relevance chain."""
    return service.one_health_view(st)


@router.get("/community")
async def community(
    user: dict[str, Any] = Depends(get_current_user),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Participation stats and badges for the calling contributor."""
    return service.community_stats(st, observer_id=user.get("id")).model_dump()


@router.get("/waterbodies")
async def waterbodies(
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Waterbodies with their observation counts and latest status."""
    out = []
    for w in st.waterbodies():
        rows = st.observations(waterbody_id=w.id)
        latest = rows[0] if rows else None
        out.append({
            "id": w.id,
            "name": w.name,
            "kind": w.kind,
            "locality": w.locality,
            "latitude": w.location.latitude if w.location else None,
            "longitude": w.location.longitude if w.location else None,
            "is_demo": w.is_demo,
            "observation_count": len(rows),
            "latest_status": latest.effective_status.value if latest else None,
            "latest_observed_at": latest.observed_at.isoformat() if latest else None,
        })
    return {"waterbodies": out, "total": len(out)}


# =============================================================================
# Observations
# =============================================================================


@router.post("/observations", status_code=201)
async def create_observation(
    payload: ObservationCreate,
    user: dict[str, Any] = Depends(get_current_user),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Submit a citizen observation and run the AI assessment over it.

    A submission via this endpoint is never demonstration data, even if the
    client asks for `source=demonstration_data` — demo rows are created only
    through the demo endpoints, so the DEMO badge cannot be spoofed onto a
    real contribution or vice versa.
    """
    if payload.source == DataSource.DEMO:
        payload = payload.model_copy(update={"source": DataSource.CITIZEN})

    obs = await service.create_observation(
        st,
        payload,
        observer_id=user.get("id"),
        observer_label=user.get("full_name") or user.get("email"),
        is_demo=False,
    )
    return obs.model_dump()


@router.get("/observations")
async def list_observations(
    waterbody_id: str | None = Query(default=None),
    review_status: ReviewStatus | None = Query(default=None),
    status: EcosystemStatus | None = Query(default=None),
    include_demo: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """List observation summaries, newest first."""
    rows = st.observations(
        waterbody_id=waterbody_id,
        review_status=review_status,
        include_demo=include_demo,
    )
    if status is not None:
        rows = [o for o in rows if o.effective_status == status]

    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "observations": [service.summarize(o).model_dump() for o in page],
    }


@router.get("/observations/{observation_id}")
async def get_observation(
    observation_id: str,
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Full observation with its assessment, evidence and review."""
    return _observation_or_404(st, observation_id).model_dump()


@router.post("/observations/{observation_id}/reassess")
async def reassess_observation(
    observation_id: str,
    _user: dict[str, Any] = Depends(Reviewer),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Re-run the agent pipeline.

    Useful after later observations at the same waterbody arrive, since the
    trend and early-warning stages read that history.
    """
    obs = _observation_or_404(st, observation_id)
    obs.assessment = await service.run_assessment(st, obs)
    st.put_observation(obs)
    await store.persist_observation(obs)
    return obs.model_dump()


# =============================================================================
# Human-in-the-loop review
# =============================================================================


@router.get("/review/queue")
async def review_queue(
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Observations awaiting human verification, most concerning first.

    Ordering puts critical signals at the top, because that is where a
    reviewer's time is most valuable.
    """
    rows = [o for o in st.observations() if o.review_status != ReviewStatus.COMPLETED]

    severity = {
        EcosystemStatus.CRITICAL_SIGNAL: 0,
        EcosystemStatus.POTENTIAL_STRESS: 1,
        EcosystemStatus.WATCH: 2,
        EcosystemStatus.INSUFFICIENT_DATA: 3,
        EcosystemStatus.HEALTHY_SIGNAL: 4,
    }
    rows.sort(
        key=lambda o: (severity.get(o.effective_status, 9), -o.observed_at.timestamp())
    )

    return {
        "total": len(rows),
        "observations": [service.summarize(o).model_dump() for o in rows],
        "decisions": [
            {"value": "accepted", "label": "Accept assessment"},
            {"value": "modified", "label": "Modify status"},
            {"value": "rejected", "label": "Reject assessment"},
            {"value": "more_info_requested", "label": "Request more information"},
        ],
    }


@router.post("/observations/{observation_id}/review")
async def review_observation(
    observation_id: str,
    payload: ReviewRequest,
    user: dict[str, Any] = Depends(Reviewer),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Record a reviewer decision: accept, modify, reject or request more info.

    A `modified` decision must carry `corrected_status`; without it the review
    would claim a correction it cannot express, so it is rejected at the edge.
    """
    obs = _observation_or_404(st, observation_id)

    if payload.decision.value == "modified" and payload.corrected_status is None:
        raise HTTPException(
            status_code=422,
            detail="corrected_status is required when decision is 'modified'.",
        )

    updated = await service.apply_review(
        st,
        obs,
        payload,
        reviewer_id=user.get("id", "unknown"),
        reviewer_label=_actor(user),
    )
    return updated.model_dump()


# =============================================================================
# Interoperability
# =============================================================================


@router.get("/observations/{observation_id}/export")
async def export_observation(
    observation_id: str,
    format: Literal["prototype", "fhir"] = Query(default="prototype"),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Export one observation as the prototype record or a FHIR R4 resource."""
    obs = _observation_or_404(st, observation_id)
    if format == "fhir":
        return mapping.to_fhir_observation(obs)
    return mapping.to_prototype_record(obs)


@router.get("/export/bundle")
async def export_bundle(
    waterbody_id: str | None = Query(default=None),
    include_demo: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Export a FHIR R4 collection Bundle of observations."""
    rows = st.observations(waterbody_id=waterbody_id, include_demo=include_demo)[:limit]
    return mapping.to_fhir_bundle(rows)


@router.get("/export/catalog")
async def export_catalog() -> dict[str, Any]:
    """The code catalogue an integrator needs to map AquaHealth payloads."""
    return mapping.signal_catalog()


# =============================================================================
# Demonstration data
# =============================================================================


@router.post("/demo/seed")
async def seed_demo(
    force: bool = Query(default=False),
    _user: dict[str, Any] = Depends(Reviewer),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Seed the clearly-labelled demonstration dataset.

    Idempotent unless `force=true`, which re-seeds. Either way only demo rows
    are affected — real citizen observations are never removed.
    """
    return await demo_data.seed_demo_data(st, force=force)


@router.post("/demo/reset")
async def reset_demo(
    _user: dict[str, Any] = Depends(Reviewer),
    st: store.OrgAquaStore = Depends(org_store),
) -> dict[str, Any]:
    """Remove every demonstration row, leaving real observations untouched."""
    return demo_data.clear_demo_data(st)
