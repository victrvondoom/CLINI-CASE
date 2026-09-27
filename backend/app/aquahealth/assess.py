"""AquaHealth assessment engine — the deterministic logic behind the agents.

Every function here is pure: observations in, findings out. No LLM, no I/O.
That matters for three reasons the OneAquaHealth brief cares about:

  1. **Explainability.** Each finding is built from `Evidence` rows that name
     the exact field the citizen filled in, so the UI can always answer
     "why does it say that?" without exposing chain-of-thought.
  2. **Reproducibility.** The same observation always yields the same
     assessment, so a reviewer's disagreement is about the rule, not about
     model drift.
  3. **Honesty about gaps.** `unknown` / `not_available` never become
     evidence. A sparse observation produces INSUFFICIENT_DATA rather than a
     confident-looking guess.

The thresholds below are prototype heuristics chosen to be defensible and
readable, not a validated environmental index. They are stated as constants
with their rationale so a domain expert can tune them in one place.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.aquahealth.models import (
    AgentFinding,
    EarlyWarning,
    Evidence,
    Observation,
)
from app.aquahealth.vocab import (
    ADVERSE_WHEN_OBSERVED,
    BIODIVERSITY_FIELDS,
    CONTEXT_FIELDS,
    FIELD_LABELS,
    POSITIVE_WHEN_OBSERVED,
    WATER_APPEARANCE_FIELDS,
    Confidence,
    DataQuality,
    EcosystemStatus,
    Presence,
)

# --- Prototype thresholds ----------------------------------------------------
# General freshwater-ecology rules of thumb, deliberately wide so that only
# clearly notable readings are flagged.

PH_HEALTHY = (6.5, 8.5)
"""Typical range for most temperate freshwater. Outside this is 'notable'."""

PH_PLAUSIBLE = (4.0, 10.0)
"""Outside this, a citizen reading is more likely a mis-entry than reality."""

DO_LOW_MGL = 5.0
"""Below ~5 mg/L many fish species are stressed."""

DO_CRITICAL_MGL = 3.0
"""Below ~3 mg/L is acute hypoxia risk."""

TURBIDITY_ELEVATED_NTU = 25.0
"""Visibly cloudy; commonly linked to runoff or disturbance."""

TURBIDITY_HIGH_NTU = 100.0
"""Strongly turbid water."""

TEMP_HIGH_C = 25.0
"""Warm enough to reduce oxygen solubility in an urban stream."""

MIN_INFORMATIVE_FIELDS = 4
"""Fields needed before any status other than INSUFFICIENT_DATA.

Four is the smallest number that can express "some signals present, some
absent" rather than a single isolated data point.
"""

MIN_TREND_OBSERVATIONS = 4
"""Observations needed at one waterbody before a trend is reported at all."""

TREND_WINDOW_DAYS = 90

_MEASUREMENT_LABELS = {
    "ph": "pH",
    "water_temperature_c": "Water temperature",
    "turbidity_ntu": "Turbidity",
    "dissolved_oxygen_mgl": "Dissolved oxygen",
}


# =============================================================================
# Helpers
# =============================================================================


def _presence_of(obs: Observation, field: str) -> Presence | None:
    """Look a qualitative field up across the three observation sections."""
    for section in (obs.appearance, obs.biodiversity, obs.context):
        value = getattr(section, field, None)
        if isinstance(value, Presence):
            return value
    return None


def _informative_fields(obs: Observation) -> dict[str, Presence]:
    """Every qualitative field where the citizen actually looked."""
    out: dict[str, Presence] = {}
    for field, _label in WATER_APPEARANCE_FIELDS + BIODIVERSITY_FIELDS + CONTEXT_FIELDS:
        p = _presence_of(obs, field)
        if p is not None and p.is_informative:
            out[field] = p
    return out


def _evidence(field: str, presence: Presence, interpretation: str) -> Evidence:
    return Evidence(
        field=field,
        label=FIELD_LABELS.get(field, field.replace("_", " ").capitalize()),
        value=presence.value,
        interpretation=interpretation,
    )


def _measurement_evidence(field: str, value: float, unit: str, interpretation: str) -> Evidence:
    return Evidence(
        field=field,
        label=_MEASUREMENT_LABELS.get(field, field),
        value=f"{value:g} {unit}".strip(),
        interpretation=interpretation,
    )


def completeness(obs: Observation) -> float:
    """Fraction of qualitative fields the citizen answered informatively.

    Measurements are deliberately excluded: the brief is explicit that a
    citizen without instruments must still be able to file a complete
    observation.
    """
    total = len(WATER_APPEARANCE_FIELDS + BIODIVERSITY_FIELDS + CONTEXT_FIELDS)
    if total == 0:
        return 0.0
    return round(len(_informative_fields(obs)) / total, 3)


def data_quality(obs: Observation) -> DataQuality:
    n_informative = len(_informative_fields(obs))
    n_measurements = len(obs.measurements.present())
    if n_informative < MIN_INFORMATIVE_FIELDS:
        return DataQuality.INSUFFICIENT
    if n_informative >= 10 or (n_informative >= 6 and n_measurements >= 2):
        return DataQuality.GOOD
    return DataQuality.LIMITED


def _adverse_signal_count(obs: Observation) -> int:
    """How many adverse qualitative signals this observation reports.

    Dead organisms count twice: they are both an adverse signal in their own
    right and the strongest single indicator in the field set.
    """
    n = 0
    for field in ADVERSE_WHEN_OBSERVED:
        if _presence_of(obs, field) == Presence.OBSERVED:
            n += 1
    if _presence_of(obs, "dead_organisms") == Presence.OBSERVED:
        n += 1
    return n


def _confidence_from(severity: int, quality: DataQuality, n_evidence: int) -> Confidence:
    """Confidence is capped by data quality — sparse data can never be HIGH.

    This is the guard against the most common failure mode in a demo system:
    a confident-sounding conclusion drawn from two checkboxes.
    """
    if quality == DataQuality.INSUFFICIENT or n_evidence == 0:
        return Confidence.LOW
    if quality == DataQuality.LIMITED:
        return Confidence.MEDIUM if severity >= 2 else Confidence.LOW
    return Confidence.HIGH if severity >= 2 else Confidence.MEDIUM


# =============================================================================
# Stage 1 — validation
# =============================================================================


def validate_observation(obs: Observation) -> AgentFinding:
    """Data-quality gate: missing data, implausible values, contradictions.

    Returns a finding rather than raising: a questionable observation is
    still worth keeping, it just needs a reviewer to see the caveat.
    """
    evidence: list[Evidence] = []
    problems: list[str] = []

    informative = _informative_fields(obs)
    n_measurements = len(obs.measurements.present())
    m = obs.measurements

    if len(informative) < MIN_INFORMATIVE_FIELDS:
        problems.append(f"only {len(informative)} of the qualitative fields were answered")

    # Implausible-but-parseable readings. Pydantic already rejected physically
    # impossible values; these are the "probably a typo" band.
    if m.ph is not None and not (PH_PLAUSIBLE[0] <= m.ph <= PH_PLAUSIBLE[1]):
        problems.append(f"pH {m.ph:g} is outside the plausible field range")
        evidence.append(_measurement_evidence(
            "ph", m.ph, "",
            f"Outside {PH_PLAUSIBLE[0]:g}-{PH_PLAUSIBLE[1]:g}; verify the reading or the device.",
        ))

    if m.dissolved_oxygen_mgl is not None and m.dissolved_oxygen_mgl > 20:
        problems.append("dissolved oxygen is implausibly high")
        evidence.append(_measurement_evidence(
            "dissolved_oxygen_mgl", m.dissolved_oxygen_mgl, "mg/L",
            "Above the normal saturation range; verify calibration.",
        ))

    # Internal contradiction: abundant life reported alongside a fish kill.
    dead = _presence_of(obs, "dead_organisms")
    fish = _presence_of(obs, "fish")
    if dead == Presence.OBSERVED and fish == Presence.OBSERVED:
        problems.append(
            "both live fish and dead organisms were reported — not impossible, "
            "but worth confirming"
        )
        evidence.append(_evidence("dead_organisms", dead, "Dead organisms reported."))
        evidence.append(_evidence("fish", fish, "Live fish also reported."))

    # Drought and flooding at the same site on the same visit.
    flooding = _presence_of(obs, "flooding")
    drought = _presence_of(obs, "drought")
    if flooding == Presence.OBSERVED and drought == Presence.OBSERVED:
        problems.append("flooding and drought were both reported")
        evidence.append(_evidence("flooding", flooding, "Flooding reported."))
        evidence.append(_evidence("drought", drought, "Drought also reported."))

    if problems:
        quality = (
            DataQuality.INSUFFICIENT
            if len(informative) < MIN_INFORMATIVE_FIELDS
            else DataQuality.LIMITED
        )
        return AgentFinding(
            agent="environmental_validation",
            finding="Data-quality issues found: " + "; ".join(problems) + ".",
            evidence=evidence,
            confidence=Confidence.HIGH,
            data_quality=quality,
            uncertainty="Flagged automatically from the submitted values only.",
            recommended_next_step="Reviewer to confirm the flagged values with the observer.",
        )

    return AgentFinding(
        agent="environmental_validation",
        finding=(
            f"Observation passed automated validation "
            f"({len(informative)} qualitative fields answered, "
            f"{n_measurements} measurement(s) supplied)."
        ),
        evidence=[],
        confidence=Confidence.HIGH,
        data_quality=data_quality(obs),
    )


# =============================================================================
# Stage 2 — water quality
# =============================================================================


def assess_water_quality(obs: Observation) -> AgentFinding:
    """Interpret whatever water-quality signals exist — measured or visual."""
    evidence: list[Evidence] = []
    concerns = 0
    m = obs.measurements

    if m.dissolved_oxygen_mgl is not None:
        do = m.dissolved_oxygen_mgl
        if do < DO_CRITICAL_MGL:
            concerns += 2
            evidence.append(_measurement_evidence(
                "dissolved_oxygen_mgl", do, "mg/L",
                f"Below {DO_CRITICAL_MGL:g} mg/L — acute hypoxia risk for aquatic life.",
            ))
        elif do < DO_LOW_MGL:
            concerns += 1
            evidence.append(_measurement_evidence(
                "dissolved_oxygen_mgl", do, "mg/L",
                f"Below {DO_LOW_MGL:g} mg/L — many fish species are stressed.",
            ))
        else:
            evidence.append(_measurement_evidence(
                "dissolved_oxygen_mgl", do, "mg/L",
                "Within the range that generally supports aquatic life.",
            ))

    if m.ph is not None:
        if not (PH_HEALTHY[0] <= m.ph <= PH_HEALTHY[1]):
            concerns += 1
            evidence.append(_measurement_evidence(
                "ph", m.ph, "",
                f"Outside the typical {PH_HEALTHY[0]:g}-{PH_HEALTHY[1]:g} freshwater range.",
            ))
        else:
            evidence.append(_measurement_evidence(
                "ph", m.ph, "", "Within the typical freshwater range.",
            ))

    if m.turbidity_ntu is not None:
        t = m.turbidity_ntu
        if t >= TURBIDITY_HIGH_NTU:
            concerns += 2
            evidence.append(_measurement_evidence(
                "turbidity_ntu", t, "NTU",
                f"At or above {TURBIDITY_HIGH_NTU:g} NTU — strongly turbid.",
            ))
        elif t >= TURBIDITY_ELEVATED_NTU:
            concerns += 1
            evidence.append(_measurement_evidence(
                "turbidity_ntu", t, "NTU",
                f"Above {TURBIDITY_ELEVATED_NTU:g} NTU — elevated, often runoff or disturbance.",
            ))

    if m.water_temperature_c is not None and m.water_temperature_c >= TEMP_HIGH_C:
        concerns += 1
        evidence.append(_measurement_evidence(
            "water_temperature_c", m.water_temperature_c, "C",
            f"At or above {TEMP_HIGH_C:g} C — warm water holds less oxygen.",
        ))

    # Visual and olfactory signals — the citizen-science core.
    for field in (
        "algae", "foam", "oily_film", "unusual_colour", "unusual_odour", "floating_waste",
    ):
        p = _presence_of(obs, field)
        if p is not None and p == Presence.OBSERVED:
            concerns += 1
            evidence.append(_evidence(
                field, p, "Reported present — a visible water-quality signal.",
            ))

    clarity = obs.appearance.clarity
    if clarity in ("cloudy", "opaque"):
        concerns += 1
        evidence.append(Evidence(
            field="clarity",
            label="Water clarity",
            value=clarity,
            interpretation="Reduced clarity reported by the observer.",
        ))

    if not evidence:
        return AgentFinding(
            agent="water_quality",
            finding="No water-quality signals were recorded for this observation.",
            evidence=[],
            confidence=Confidence.LOW,
            data_quality=DataQuality.INSUFFICIENT,
            uncertainty="No measurements and no visual water-quality fields were answered.",
            recommended_next_step=(
                "Collect at least clarity, odour and visible-waste fields on the next visit."
            ),
        )

    if concerns >= 3:
        finding = "Multiple water-quality signals suggest possible ecosystem stress."
    elif concerns >= 1:
        finding = "One or more water-quality signals are worth monitoring."
    else:
        finding = "Recorded water-quality signals are within expected ranges."

    quality = data_quality(obs)
    return AgentFinding(
        agent="water_quality",
        finding=finding,
        evidence=evidence,
        confidence=_confidence_from(concerns, quality, len(evidence)),
        data_quality=quality,
        uncertainty=(
            None if m.present()
            else "Based on visual observation only — no instrument measurements supplied."
        ),
        recommended_next_step=(
            "Follow-up sampling with a probe kit would confirm these signals."
            if concerns >= 2 and not m.present() else None
        ),
    )


# =============================================================================
# Stage 3 — biodiversity
# =============================================================================


def assess_biodiversity(obs: Observation) -> AgentFinding:
    """Read presence AND absence signals from the biodiversity fields.

    `not_observed` is treated as real information here — "looked for
    macroinvertebrates and found none" is an ecologically meaningful
    observation, which is exactly why `Presence` is not a boolean.
    """
    evidence: list[Evidence] = []
    positives = 0
    absences = 0
    alarms = 0

    for field, _label in BIODIVERSITY_FIELDS:
        p = _presence_of(obs, field)
        if p is None or not p.is_informative:
            continue

        if field in POSITIVE_WHEN_OBSERVED:
            if p == Presence.OBSERVED:
                positives += 1
                evidence.append(_evidence(field, p, "Present — a sign of a living system."))
            else:
                absences += 1
                evidence.append(_evidence(
                    field, p, "Looked for but not seen — a possible absence signal.",
                ))
        elif field == "dead_organisms":
            if p == Presence.OBSERVED:
                alarms += 2
                evidence.append(_evidence(
                    field, p, "Dead organisms reported — a strong adverse signal.",
                ))
            else:
                evidence.append(_evidence(field, p, "No dead organisms seen."))
        elif field == "unusual_organisms" and p == Presence.OBSERVED:
            alarms += 1
            evidence.append(_evidence(
                field, p,
                "Unusual organisms reported — may indicate a change in the community.",
            ))

    if not evidence:
        return AgentFinding(
            agent="biodiversity",
            finding="No biodiversity fields were answered for this observation.",
            evidence=[],
            confidence=Confidence.LOW,
            data_quality=DataQuality.INSUFFICIENT,
            uncertainty="Presence and absence are both unknown.",
            recommended_next_step=(
                "Record fish, bird, insect and plant presence on the next visit."
            ),
        )

    barren = absences >= 3 and positives == 0
    if alarms >= 2:
        finding = "Adverse biodiversity signal reported at this site."
    elif barren:
        finding = (
            "No visible aquatic life was found across several groups that were "
            "checked — a possible absence signal."
        )
    elif positives >= 3 and alarms == 0:
        finding = "Multiple biodiversity groups were observed, indicating a living system."
    else:
        finding = "Mixed biodiversity signals recorded."

    severity = alarms + (1 if barren else 0)
    quality = data_quality(obs)
    return AgentFinding(
        agent="biodiversity",
        finding=finding,
        evidence=evidence,
        confidence=_confidence_from(severity, quality, len(evidence)),
        data_quality=quality,
        uncertainty=(
            "A single visit cannot distinguish a genuine absence from animals "
            "simply not being visible at the time."
        ),
        recommended_next_step=(
            "Repeat the observation at a different time of day to confirm."
            if barren else None
        ),
    )


# =============================================================================
# Stage 4 — environmental context
# =============================================================================


def assess_context(obs: Observation) -> AgentFinding:
    """Weather / land-use context that can explain or compound a signal."""
    evidence: list[Evidence] = []
    pressures = 0

    for field, _label in CONTEXT_FIELDS:
        p = _presence_of(obs, field)
        if p is None or p != Presence.OBSERVED:
            continue
        if field in ADVERSE_WHEN_OBSERVED:
            pressures += 1
            evidence.append(_evidence(
                field, p, "Reported present — a potential pressure on the waterbody.",
            ))
        else:
            evidence.append(_evidence(
                field, p,
                "Reported present — relevant context for interpreting the other signals.",
            ))

    # A natural explanation for turbidity is as important as a pollution one:
    # naming it stops the reviewer chasing a discharge that was just rain.
    rainfall = _presence_of(obs, "recent_rainfall")
    turbidity = obs.measurements.turbidity_ntu
    natural_cause = None
    if rainfall == Presence.OBSERVED and turbidity is not None and turbidity >= TURBIDITY_ELEVATED_NTU:
        natural_cause = (
            "Recent rainfall may explain the elevated turbidity; this is a "
            "plausible natural cause rather than a pollution event."
        )

    if not evidence:
        return AgentFinding(
            agent="environmental_context",
            finding="No environmental-context pressures were reported.",
            evidence=[],
            confidence=Confidence.LOW,
            data_quality=data_quality(obs),
            uncertainty="Context fields were largely unanswered.",
        )

    if pressures >= 2:
        finding = "Several environmental pressures were reported near this site."
    elif pressures == 1:
        finding = "One environmental pressure was reported near this site."
    else:
        finding = "Contextual conditions were reported without a clear pressure."

    quality = data_quality(obs)
    return AgentFinding(
        agent="environmental_context",
        finding=finding,
        evidence=evidence,
        confidence=_confidence_from(pressures, quality, len(evidence)),
        data_quality=quality,
        uncertainty=(
            natural_cause
            or "Context is observer-reported and not independently verified."
        ),
        recommended_next_step=(
            "Check local works notices or discharge consents for this reach."
            if pressures >= 2 else None
        ),
    )


# =============================================================================
# Stage 5 — trend
# =============================================================================


def assess_trend(obs: Observation, history: list[Observation]) -> AgentFinding:
    """Compare against prior observations at the same waterbody.

    Refuses to report a trend below MIN_TREND_OBSERVATIONS. The brief is
    explicit: never fabricate trends.
    """
    cutoff = datetime.now(UTC) - timedelta(days=TREND_WINDOW_DAYS)
    prior = [
        h for h in history
        if h.waterbody_id == obs.waterbody_id
        and h.id != obs.id
        and h.observed_at >= cutoff
    ]
    prior.sort(key=lambda h: h.observed_at)

    total = len(prior) + 1
    if total < MIN_TREND_OBSERVATIONS:
        return AgentFinding(
            agent="trend",
            finding=(
                "Insufficient historical observations to determine a trend "
                f"({total} of {MIN_TREND_OBSERVATIONS} needed at this waterbody)."
            ),
            evidence=[],
            confidence=Confidence.LOW,
            data_quality=DataQuality.INSUFFICIENT,
            uncertainty="A trend requires repeated visits to the same waterbody.",
            recommended_next_step="Keep observing this site to build a baseline.",
        )

    adverse_now = _adverse_signal_count(obs)
    adverse_prior = [_adverse_signal_count(h) for h in prior]
    mean_prior = sum(adverse_prior) / len(adverse_prior)

    evidence = [Evidence(
        field="history",
        label="Prior observations at this waterbody",
        value=f"{len(prior)} in the last {TREND_WINDOW_DAYS} days",
        interpretation=(
            f"Mean adverse signals previously {mean_prior:.1f}; "
            f"this observation has {adverse_now}."
        ),
    )]

    if adverse_now > mean_prior + 1:
        finding = "Adverse signals at this waterbody are higher than its recent baseline."
        conf = Confidence.MEDIUM
    elif adverse_now + 1 < mean_prior:
        finding = "Adverse signals at this waterbody are lower than its recent baseline."
        conf = Confidence.MEDIUM
    else:
        finding = "Adverse signals are broadly in line with this waterbody's recent baseline."
        conf = Confidence.LOW

    return AgentFinding(
        agent="trend",
        finding=finding,
        evidence=evidence,
        confidence=conf,
        data_quality=DataQuality.LIMITED if total < 8 else DataQuality.GOOD,
        uncertainty=(
            "Citizen observations are irregular in timing and observer, so a "
            "change may reflect who observed rather than the water itself."
        ),
    )


# =============================================================================
# Stage 6 — One Health
# =============================================================================


def assess_one_health(obs: Observation) -> AgentFinding:
    """Link ecosystem signals to animal and community relevance.

    Deliberately cautious language. This never diagnoses disease and never
    asserts causation — it states *potential relevance* and routes to human
    verification, which is what the One Health framing actually supports.
    """
    evidence: list[Evidence] = []
    pathways: list[str] = []

    dead = _presence_of(obs, "dead_organisms")
    if dead == Presence.OBSERVED:
        pathways.append(
            "dead organisms can indicate an acute water-quality event affecting animals"
        )
        evidence.append(_evidence(
            "dead_organisms", dead, "Animal-health signal observed directly.",
        ))

    discharge_like = [
        f for f in ("suspected_discharge", "foam", "unusual_odour")
        if _presence_of(obs, f) == Presence.OBSERVED
    ]
    if discharge_like:
        pathways.append(
            "discharge-like signals are a recognised route for water-borne "
            "pathogens and irritants to reach people using the water"
        )
        for f in discharge_like:
            p = _presence_of(obs, f)
            if p is not None:
                evidence.append(_evidence(f, p, "Potential contamination pathway signal."))

    algae = _presence_of(obs, "algae")
    if algae == Presence.OBSERVED:
        pathways.append(
            "algal blooms can produce toxins relevant to pets, livestock and "
            "people in contact with the water"
        )
        evidence.append(_evidence(
            "algae", algae, "Bloom signal with known animal/human relevance.",
        ))

    waste = _presence_of(obs, "waste_accumulation")
    if waste == Presence.OBSERVED:
        pathways.append("accumulated waste is a habitat and exposure pressure")
        evidence.append(_evidence("waste_accumulation", waste, "Exposure pressure signal."))

    if not pathways:
        return AgentFinding(
            agent="one_health",
            finding=(
                "No observation in this record indicates a potential "
                "ecosystem-to-community pathway."
            ),
            evidence=[],
            confidence=Confidence.LOW,
            data_quality=data_quality(obs),
            uncertainty=(
                "Absence of a reported signal is not evidence that no pathway exists."
            ),
        )

    return AgentFinding(
        agent="one_health",
        finding=(
            "Potential relevance to animal and community health: "
            + "; ".join(pathways)
            + "."
        ),
        evidence=evidence,
        confidence=Confidence.LOW if len(pathways) == 1 else Confidence.MEDIUM,
        data_quality=data_quality(obs),
        uncertainty=(
            "This is a potential pathway based on a single citizen observation. "
            "It is not a diagnosis, not a causal claim and not a public-health "
            "determination."
        ),
        recommended_next_step=(
            "Share with the local environmental authority for field verification "
            "before any community-facing advice is issued."
        ),
    )


# =============================================================================
# Status + early warning
# =============================================================================


def derive_status(obs: Observation) -> tuple[EcosystemStatus, str, Confidence]:
    """Prototype Ecosystem Observation Status with a human-readable reason.

    Returns INSUFFICIENT_DATA whenever the observation is too sparse to
    support any claim, rather than defaulting to a reassuring 'healthy'.
    """
    informative = _informative_fields(obs)
    if len(informative) < MIN_INFORMATIVE_FIELDS:
        return (
            EcosystemStatus.INSUFFICIENT_DATA,
            (
                f"Only {len(informative)} qualitative field(s) were answered; "
                f"at least {MIN_INFORMATIVE_FIELDS} are needed before a status "
                "can be suggested."
            ),
            Confidence.LOW,
        )

    adverse = _adverse_signal_count(obs)
    dead = _presence_of(obs, "dead_organisms") == Presence.OBSERVED
    m = obs.measurements

    critical_measure = (
        m.dissolved_oxygen_mgl is not None and m.dissolved_oxygen_mgl < DO_CRITICAL_MGL
    )
    elevated_measure = (
        (m.dissolved_oxygen_mgl is not None and m.dissolved_oxygen_mgl < DO_LOW_MGL)
        or (m.turbidity_ntu is not None and m.turbidity_ntu >= TURBIDITY_HIGH_NTU)
        or (m.ph is not None and not (PH_HEALTHY[0] <= m.ph <= PH_HEALTHY[1]))
    )

    reasons: list[str] = []
    if dead:
        reasons.append("dead organisms were reported")
    if critical_measure and m.dissolved_oxygen_mgl is not None:
        reasons.append(f"dissolved oxygen {m.dissolved_oxygen_mgl:g} mg/L is critically low")
    if adverse:
        reasons.append(f"{adverse} adverse visual signal(s) were reported")
    if elevated_measure and not critical_measure:
        reasons.append("a measurement is outside its expected range")

    if dead and (adverse >= 2 or critical_measure):
        status = EcosystemStatus.CRITICAL_SIGNAL
    elif critical_measure or dead or adverse >= 3:
        status = EcosystemStatus.POTENTIAL_STRESS
    elif adverse >= 1 or elevated_measure:
        status = EcosystemStatus.WATCH
    else:
        status = EcosystemStatus.HEALTHY_SIGNAL
        positives = sum(
            1 for f in POSITIVE_WHEN_OBSERVED
            if _presence_of(obs, f) == Presence.OBSERVED
        )
        reasons.append(
            f"no adverse signals were reported and {positives} biodiversity "
            "group(s) were observed"
            if positives
            else "no adverse signals were reported"
        )

    quality = data_quality(obs)
    if quality == DataQuality.GOOD:
        conf = Confidence.HIGH if status != EcosystemStatus.HEALTHY_SIGNAL else Confidence.MEDIUM
    elif quality == DataQuality.LIMITED:
        conf = Confidence.MEDIUM
    else:
        conf = Confidence.LOW

    reason = "Status derived from this observation because " + "; ".join(reasons) + "."
    return status, reason, conf


def derive_early_warning(
    obs: Observation,
    history: list[Observation],
    status: EcosystemStatus,
) -> EarlyWarning:
    """Prototype early-warning signal.

    Fires on a repeated pattern at one waterbody, or on a single critical
    observation. Explicitly informational — it recommends human field
    verification and never claims real-time monitoring.
    """
    if status == EcosystemStatus.CRITICAL_SIGNAL:
        return EarlyWarning(
            active=True,
            headline="Potential environmental signal",
            reason=(
                "A single observation reported a combination of adverse signals "
                "consistent with an acute event."
            ),
            confidence=Confidence.MEDIUM,
            recommended_next_step="Human field verification.",
        )

    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent_adverse = [
        h for h in history
        if h.waterbody_id == obs.waterbody_id
        and h.id != obs.id
        and h.observed_at >= cutoff
        and _adverse_signal_count(h) >= 2
    ]
    if _adverse_signal_count(obs) >= 2:
        recent_adverse.append(obs)

    if len(recent_adverse) >= 3:
        return EarlyWarning(
            active=True,
            headline="Potential environmental signal",
            reason=(
                f"Repeated unusual observations detected: {len(recent_adverse)} "
                "observations with multiple adverse signals at this waterbody "
                "in the last 30 days."
            ),
            confidence=Confidence.MEDIUM,
            recommended_next_step="Human field verification.",
        )

    return EarlyWarning(active=False)
