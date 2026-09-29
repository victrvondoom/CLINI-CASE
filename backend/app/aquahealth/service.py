"""AquaHealth service layer — observation intake, assessment, review, aggregates.

This is the module the API talks to. It owns the pipeline:

    Citizen observation
        -> AI assessment (7 deterministic agents)
        -> evidence + confidence
        -> human review (accept / modify / reject / request info)
        -> final assessment

The agents run through the real ClinCase `Agent.invoke` lifecycle so their runs
are traced, budgeted and recorded exactly like clinical agent runs. When that
lifecycle is unavailable (no DB for the trace sink, for instance) the pipeline
falls back to calling the same deterministic functions directly — an
assessment must never fail just because tracing is unavailable, and because
both paths call `app.aquahealth.assess`, the result is identical either way.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.aquahealth import assess, store
from app.aquahealth.agents.env_agents import (
    WM_KEY,
    BiodiversityAgent,
    EnvAgentInput,
    EnvironmentalContextAgent,
    EnvironmentalValidationAgent,
    ExplanationAgent,
    OneHealthAgent,
    TrendAgent,
    WaterQualityAgent,
)
from app.aquahealth.models import (
    AgentFinding,
    Badge,
    CommunityStats,
    DashboardOverview,
    EnvironmentalAssessment,
    GeoPoint,
    HumanReview,
    Observation,
    ObservationCreate,
    ObservationSummary,
    ReviewRequest,
    Waterbody,
)
from app.aquahealth.vocab import (
    Confidence,
    EcosystemStatus,
    Presence,
    ReviewDecision,
    ReviewStatus,
    VerificationState,
)

log = structlog.get_logger()

#: Stage agents in pipeline order, excluding the aggregator.
_STAGE_AGENTS = (
    EnvironmentalValidationAgent,
    WaterQualityAgent,
    BiodiversityAgent,
    EnvironmentalContextAgent,
    TrendAgent,
    OneHealthAgent,
)

#: Direct fallbacks keyed by agent name, for when the traced lifecycle is
#: unavailable. These call the same functions the agents do.
_FALLBACKS = {
    "environmental_validation": lambda obs, hist: assess.validate_observation(obs),
    "water_quality": lambda obs, hist: assess.assess_water_quality(obs),
    "biodiversity": lambda obs, hist: assess.assess_biodiversity(obs),
    "environmental_context": lambda obs, hist: assess.assess_context(obs),
    "trend": lambda obs, hist: assess.assess_trend(obs, hist),
    "one_health": lambda obs, hist: assess.assess_one_health(obs),
}

_POSITIVE_BIO_FIELDS = (
    "fish",
    "birds",
    "insects",
    "aquatic_plants",
    "macroinvertebrates",
)


# =============================================================================
# Intake
# =============================================================================


async def create_observation(
    org_store: store.OrgAquaStore,
    payload: ObservationCreate,
    *,
    observer_id: str | None,
    observer_label: str | None,
    is_demo: bool = False,
) -> Observation:
    """Persist a new observation and run the AI assessment over it.

    Resolves the waterbody first: an explicit `waterbody_id` wins, then a name
    match (so repeat visits to "Demo Stream" group together instead of
    creating a duplicate site), then a new waterbody.
    """
    wb = _resolve_waterbody(org_store, payload, is_demo=is_demo)

    observed_at = payload.observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    location = wb.location
    if payload.latitude is not None and payload.longitude is not None:
        location = GeoPoint(latitude=payload.latitude, longitude=payload.longitude)

    obs = Observation(
        reference=org_store.next_reference(),
        organization_id=org_store.organization_id,
        waterbody_id=wb.id,
        waterbody_name=wb.name,
        location=location,
        locality=payload.locality or wb.locality,
        observed_at=observed_at,
        observer_id=observer_id,
        observer_label=observer_label,
        observer_note=payload.observer_note,
        appearance=payload.appearance,
        biodiversity=payload.biodiversity,
        context=payload.context,
        measurements=payload.measurements,
        photos=payload.photos,
        source=payload.source,
        is_demo=is_demo,
        verification=VerificationState.UNVERIFIED,
        review_status=ReviewStatus.PENDING,
    )

    org_store.put_observation(obs)

    obs.assessment = await run_assessment(org_store, obs)
    obs.verification = VerificationState.AI_ASSISTED
    org_store.put_observation(obs)

    await store.persist_waterbody(wb)
    await store.persist_observation(obs)
    return obs


def _resolve_waterbody(
    org_store: store.OrgAquaStore,
    payload: ObservationCreate,
    *,
    is_demo: bool,
) -> Waterbody:
    if payload.waterbody_id:
        existing = org_store.waterbody(payload.waterbody_id)
        if existing is not None:
            return existing

    name = (payload.waterbody_name or "").strip()
    if name:
        by_name = org_store.find_waterbody_by_name(name)
        if by_name is not None:
            return by_name

    location = None
    if payload.latitude is not None and payload.longitude is not None:
        location = GeoPoint(latitude=payload.latitude, longitude=payload.longitude)

    return org_store.add_waterbody(
        Waterbody(
            organization_id=org_store.organization_id,
            name=name or "Unnamed waterbody",
            kind=payload.waterbody_kind,
            locality=payload.locality,
            location=location,
            is_demo=is_demo,
        )
    )


# =============================================================================
# Assessment pipeline
# =============================================================================


async def run_assessment(
    org_store: store.OrgAquaStore,
    obs: Observation,
) -> EnvironmentalAssessment:
    """Run the seven agents over one observation and assemble the assessment."""
    history = [h for h in org_store.history_for(obs.waterbody_id) if h.id != obs.id]
    agent_input = EnvAgentInput(observation=obs, history=history)

    ctx = _new_context(obs)
    findings: list[AgentFinding] = []

    for agent_cls in _STAGE_AGENTS:
        finding = await _run_stage(agent_cls, agent_input, ctx, obs, history)
        if finding is not None:
            findings.append(finding)
        if ctx is not None:
            ctx.working_memory.setdefault(WM_KEY, {})["findings"] = findings

    # Aggregate. The explanation agent reads the findings above out of working
    # memory; without a context we compute the same aggregate directly.
    status_out = None
    if ctx is not None:
        try:
            result = await ExplanationAgent().invoke(agent_input, ctx=ctx)
            status_out = result.output
        except Exception as e:  # noqa: BLE001 — traced path is best-effort
            log.info("aquahealth.agent.explanation_fallback", error=str(e)[:160])

    if status_out is not None:
        status = status_out.status
        reason = status_out.status_reason
        confidence = status_out.confidence
        early_warning = status_out.early_warning
        one_health_note = status_out.one_health_note
    else:
        status, reason, confidence = assess.derive_status(obs)
        warning = assess.derive_early_warning(obs, history, status)
        early_warning = warning if warning.active else None
        one_health = next((f for f in findings if f.agent == "one_health"), None)
        one_health_note = one_health.finding if one_health else None

    return EnvironmentalAssessment(
        observation_id=obs.id,
        status=status,
        status_reason=reason,
        confidence=confidence,
        data_quality=assess.data_quality(obs),
        completeness=assess.completeness(obs),
        findings=findings,
        one_health_note=one_health_note,
        early_warning=early_warning,
    )


def _new_context(obs: Observation) -> Any:
    """Build an AgentContext, or None when the framework can't provide one.

    A missing trace sink (DB-less deployment) must not block an assessment, so
    failure here downgrades to the direct path rather than raising.
    """
    try:
        from app.agents.framework import new_agent_context

        return new_agent_context(
            case_id=obs.id,
            organization_id=obs.organization_id,
        )
    except Exception as e:  # noqa: BLE001
        log.info("aquahealth.agent_context.unavailable", error=str(e)[:160])
        return None


async def _run_stage(
    agent_cls: type,
    agent_input: EnvAgentInput,
    ctx: Any,
    obs: Observation,
    history: list[Observation],
) -> AgentFinding | None:
    """Run one stage agent, falling back to its pure function on failure."""
    if ctx is not None:
        try:
            result = await agent_cls().invoke(agent_input, ctx=ctx)
            return result.output.finding
        except Exception as e:  # noqa: BLE001 — fall back, never lose the stage
            log.info(
                "aquahealth.agent.fallback",
                agent=getattr(agent_cls, "name", agent_cls.__name__),
                error=str(e)[:160],
            )

    fallback = _FALLBACKS.get(getattr(agent_cls, "name", ""))
    if fallback is None:
        return None
    return fallback(obs, history)


# =============================================================================
# Human-in-the-loop review
# =============================================================================


async def apply_review(
    org_store: store.OrgAquaStore,
    obs: Observation,
    request: ReviewRequest,
    *,
    reviewer_id: str,
    reviewer_label: str,
) -> Observation:
    """Record a reviewer's decision and update the observation's final state.

    A MODIFIED decision carries the reviewer's corrected status, which
    `Observation.effective_status` then prefers over the AI status everywhere.
    A MORE_INFO decision deliberately leaves the record in review rather than
    completing it — the question is still open.
    """
    review = HumanReview(
        observation_id=obs.id,
        decision=request.decision,
        reviewer_id=reviewer_id,
        reviewer_label=reviewer_label,
        comment=request.comment,
        corrected_status=(
            request.corrected_status if request.decision == ReviewDecision.MODIFIED else None
        ),
        rejected_findings=request.rejected_findings,
    )

    obs.review = review
    if request.decision == ReviewDecision.MORE_INFO:
        obs.review_status = ReviewStatus.IN_REVIEW
        obs.verification = VerificationState.AI_ASSISTED
    else:
        obs.review_status = ReviewStatus.COMPLETED
        obs.verification = (
            VerificationState.VERIFIED
            if request.decision == ReviewDecision.ACCEPTED
            else VerificationState.HUMAN_REVIEWED
        )

    if obs.assessment is not None:
        obs.assessment.human_verification = (
            "required" if request.decision == ReviewDecision.MORE_INFO else "reviewed"
        )

    org_store.put_observation(obs)
    await store.persist_observation(obs)
    return obs


# =============================================================================
# Read models / aggregates
# =============================================================================


def summarize(obs: Observation) -> ObservationSummary:
    a = obs.assessment
    return ObservationSummary(
        id=obs.id,
        reference=obs.reference,
        waterbody_id=obs.waterbody_id,
        waterbody_name=obs.waterbody_name,
        location=obs.location,
        observed_at=obs.observed_at,
        status=obs.effective_status,
        confidence=a.confidence if a else Confidence.LOW,
        data_quality=a.data_quality if a else assess.data_quality(obs),
        source=obs.source,
        verification=obs.verification,
        review_status=obs.review_status,
        is_demo=obs.is_demo,
        headline=(
            a.early_warning.headline
            if a and a.early_warning and a.early_warning.active
            else (a.findings[0].finding if a and a.findings else None)
        ),
    )


def dashboard(org_store: store.OrgAquaStore, *, recent_limit: int = 8) -> DashboardOverview:
    """Aggregate the overview panel.

    Distributions are computed over `effective_status`, so a reviewer's
    correction is reflected in the dashboard rather than the AI's original call.
    """
    rows = org_store.observations()
    status_counts: Counter[str] = Counter()
    conf_counts: Counter[str] = Counter()
    dq_counts: Counter[str] = Counter()
    src_counts: Counter[str] = Counter()

    for o in rows:
        status_counts[o.effective_status.value] += 1
        src_counts[o.source.value] += 1
        if o.assessment is not None:
            conf_counts[o.assessment.confidence.value] += 1
            dq_counts[o.assessment.data_quality.value] += 1

    warnings = [
        o
        for o in rows
        if o.assessment is not None
        and o.assessment.early_warning is not None
        and o.assessment.early_warning.active
    ]

    return DashboardOverview(
        waterbody_count=len(org_store.waterbodies()),
        observation_count=len(rows),
        awaiting_review=sum(1 for o in rows if o.review_status != ReviewStatus.COMPLETED),
        demo_observation_count=sum(1 for o in rows if o.is_demo),
        status_distribution=dict(status_counts),
        confidence_distribution=dict(conf_counts),
        data_quality_distribution=dict(dq_counts),
        source_distribution=dict(src_counts),
        recent=[summarize(o) for o in rows[:recent_limit]],
        active_warnings=[summarize(o) for o in warnings[:recent_limit]],
    )


def trends(
    org_store: store.OrgAquaStore,
    *,
    waterbody_id: str | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """Time series for the trends page.

    Returns `sufficient: False` with an explicit message when there are too
    few observations, so the UI can say "insufficient historical observations"
    instead of drawing a misleading line.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = [o for o in org_store.observations(waterbody_id=waterbody_id) if o.observed_at >= cutoff]
    rows.sort(key=lambda o: o.observed_at)

    if len(rows) < assess.MIN_TREND_OBSERVATIONS:
        return {
            "sufficient": False,
            "message": (
                "Insufficient historical observations to determine a trend "
                f"({len(rows)} of {assess.MIN_TREND_OBSERVATIONS} needed)."
            ),
            "window_days": days,
            "observation_count": len(rows),
            "series": [],
            "status_history": [],
        }

    # Bucket by ISO date so several observations on one day collapse to a point.
    by_day: dict[str, list[Observation]] = {}
    for o in rows:
        by_day.setdefault(o.observed_at.date().isoformat(), []).append(o)

    series = []
    for day in sorted(by_day):
        bucket = by_day[day]
        measured_do = [
            o.measurements.dissolved_oxygen_mgl
            for o in bucket
            if o.measurements.dissolved_oxygen_mgl is not None
        ]
        measured_turb = [
            o.measurements.turbidity_ntu for o in bucket if o.measurements.turbidity_ntu is not None
        ]
        biodiversity_positives = sum(
            1
            for o in bucket
            for f in _POSITIVE_BIO_FIELDS
            if getattr(o.biodiversity, f, None) == Presence.OBSERVED
        )
        series.append(
            {
                "date": day,
                "observations": len(bucket),
                "adverse_signals": sum(adverse_signal_count(o) for o in bucket),
                "biodiversity_positives": biodiversity_positives,
                "mean_dissolved_oxygen_mgl": (
                    round(sum(measured_do) / len(measured_do), 2) if measured_do else None
                ),
                "mean_turbidity_ntu": (
                    round(sum(measured_turb) / len(measured_turb), 1) if measured_turb else None
                ),
            }
        )

    return {
        "sufficient": True,
        "message": None,
        "window_days": days,
        "observation_count": len(rows),
        "series": series,
        "status_history": [
            {
                "date": o.observed_at.date().isoformat(),
                "reference": o.reference,
                "status": o.effective_status.value,
                "waterbody_name": o.waterbody_name,
            }
            for o in rows
        ],
        "note": (
            "Citizen observations are irregular in timing and observer. Treat "
            "these series as a participation-weighted signal, not a monitoring "
            "record."
        ),
    }


def adverse_signal_count(obs: Observation) -> int:
    """Public wrapper over the engine's adverse-signal count."""
    return assess._adverse_signal_count(obs)  # noqa: SLF001 — same package


def one_health_view(org_store: store.OrgAquaStore) -> dict[str, Any]:
    """Ecosystem -> biodiversity/animal -> community relevance chain."""
    rows = org_store.observations()

    ecosystem_signals: Counter[str] = Counter()
    animal_signals: Counter[str] = Counter()
    pathways: list[dict[str, Any]] = []

    for o in rows:
        for field in ("algae", "foam", "oily_film", "unusual_odour", "floating_waste"):
            if getattr(o.appearance, field, None) == Presence.OBSERVED:
                ecosystem_signals[field] += 1
        for field in ("dead_organisms", "unusual_organisms"):
            if getattr(o.biodiversity, field, None) == Presence.OBSERVED:
                animal_signals[field] += 1

        if o.assessment is None:
            continue
        oh = next((f for f in o.assessment.findings if f.agent == "one_health"), None)
        if oh is not None and oh.evidence:
            pathways.append(
                {
                    "observation_id": o.id,
                    "reference": o.reference,
                    "waterbody_name": o.waterbody_name,
                    "observed_at": o.observed_at.isoformat(),
                    "finding": oh.finding,
                    "confidence": oh.confidence.value,
                    "evidence": [e.model_dump() for e in oh.evidence],
                    "uncertainty": oh.uncertainty,
                    "status": o.effective_status.value,
                }
            )

    return {
        "chain": [
            {
                "layer": "ecosystem",
                "label": "Ecosystem",
                "signal_count": sum(ecosystem_signals.values()),
                "signals": dict(ecosystem_signals),
                "description": ("Water-quality signals observed in the freshwater body itself."),
            },
            {
                "layer": "animal",
                "label": "Biodiversity / animal",
                "signal_count": sum(animal_signals.values()),
                "signals": dict(animal_signals),
                "description": ("Signals observed in the organisms living in or around the water."),
            },
            {
                "layer": "community",
                "label": "Community health relevance",
                "signal_count": len(pathways),
                "signals": {},
                "description": (
                    "Potential relevance to people using the waterbody. Stated as "
                    "potential relevance only — never a diagnosis or a causal claim."
                ),
            },
        ],
        "pathways": pathways[:20],
        "disclaimer": (
            "One Health linkages here are prototype signals from citizen "
            "observations. They indicate where human verification is worthwhile, "
            "not that any health effect has occurred."
        ),
    }


def community_stats(
    org_store: store.OrgAquaStore,
    *,
    observer_id: str | None,
) -> CommunityStats:
    """Participation metrics and badges for one contributor.

    Deliberately isolated from the assessment path: `assess.py` never reads
    these numbers, so a prolific contributor's observations are assessed by
    exactly the same rules as a first-timer's.
    """
    rows = org_store.observations()
    mine = [o for o in rows if observer_id and o.observer_id == observer_id]

    my_count = len(mine)
    my_waterbodies = len({o.waterbody_id for o in mine})
    my_reviewed = sum(1 for o in mine if o.review_status == ReviewStatus.COMPLETED)
    my_biodiversity = sum(
        1
        for o in mine
        if any(getattr(o.biodiversity, f).is_informative for f in _POSITIVE_BIO_FIELDS)
    )

    badges = [
        _badge(
            "first_observation",
            "First Observation",
            "Contribute your first freshwater observation.",
            my_count,
            1,
        ),
        _badge(
            "water_watcher",
            "Water Watcher",
            "Contribute 5 observations.",
            my_count,
            5,
        ),
        _badge(
            "biodiversity_observer",
            "Biodiversity Observer",
            "Record biodiversity on 3 observations.",
            my_biodiversity,
            3,
        ),
        _badge(
            "community_contributor",
            "Community Contributor",
            "Observe at 3 different waterbodies.",
            my_waterbodies,
            3,
        ),
    ]

    return CommunityStats(
        observations_contributed=my_count,
        waterbodies_explored=my_waterbodies,
        reviewed_contributions=my_reviewed,
        community_observers=len({o.observer_id for o in rows if o.observer_id}),
        community_observations=len(rows),
        badges=badges,
    )


def _badge(code: str, label: str, description: str, progress: int, target: int) -> Badge:
    return Badge(
        code=code,
        label=label,
        description=description,
        earned=progress >= target,
        progress=min(progress, target),
        target=target,
    )


def map_points(org_store: store.OrgAquaStore) -> list[dict[str, Any]]:
    """Observations that have coordinates, shaped for the map view."""
    out: list[dict[str, Any]] = []
    for o in org_store.observations():
        if o.location is None:
            continue
        a = o.assessment
        out.append(
            {
                "observation_id": o.id,
                "reference": o.reference,
                "waterbody_id": o.waterbody_id,
                "waterbody_name": o.waterbody_name,
                "latitude": o.location.latitude,
                "longitude": o.location.longitude,
                "observed_at": o.observed_at.isoformat(),
                "status": o.effective_status.value,
                "confidence": (a.confidence.value if a else Confidence.LOW.value),
                "review_status": o.review_status.value,
                "verification": o.verification.value,
                "source": o.source.value,
                "is_demo": o.is_demo,
                "summary": (a.findings[0].finding if a and a.findings else None),
            }
        )
    return out


def status_catalog() -> list[dict[str, str]]:
    """The five statuses with their plain-language meaning, for UI legends."""
    return [
        {
            "status": EcosystemStatus.HEALTHY_SIGNAL.value,
            "label": "Healthy Signal",
            "meaning": "No adverse signals were reported in this observation.",
        },
        {
            "status": EcosystemStatus.WATCH.value,
            "label": "Watch",
            "meaning": "A single mild signal was reported; worth watching.",
        },
        {
            "status": EcosystemStatus.POTENTIAL_STRESS.value,
            "label": "Potential Stress",
            "meaning": "Several signals, or one strong signal, suggest possible stress.",
        },
        {
            "status": EcosystemStatus.CRITICAL_SIGNAL.value,
            "label": "Critical Signal",
            "meaning": ("A combination of adverse signals consistent with an acute event."),
        },
        {
            "status": EcosystemStatus.INSUFFICIENT_DATA.value,
            "label": "Insufficient Data",
            "meaning": (
                "Too few fields were answered to suggest a status. Not a "
                "statement that the water is healthy."
            ),
        },
    ]
