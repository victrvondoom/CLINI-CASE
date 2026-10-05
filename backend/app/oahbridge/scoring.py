"""
Deterministic Evidence Support Scoring & Epistemic Classification Engine.
Version: v0.1-prototype

Methodology:
S = w_sensor * C_sensor + w_citizen * C_citizen + w_temporal * C_temporal
Weights: w_sensor = 0.40, w_citizen = 0.30, w_temporal = 0.30 (Sum = 1.00)

Disclaimer:
These weights are prototype assumptions for demonstration and are not clinically validated.
"""


from .models import (
    CitizenReport,
    CompositeEvidenceResult,
    EvidenceSubScores,
    LabAssay,
    SensorReading,
)

# Frozen prototype weights v0.1
WEIGHT_SENSOR = 0.40
WEIGHT_CITIZEN = 0.30
WEIGHT_TEMPORAL = 0.30

# Epistemic classification thresholds
THRESHOLD_STRONG_INFERRED = 0.70
THRESHOLD_MODERATE_INFERRED = 0.40


def calculate_sensor_corroboration(readings: list[SensorReading]) -> float:
    """
    Computes normalized corroboration among in-situ sensor telemetry readings.
    Evaluates both the proportion of parameters exceeding anomaly thresholds
    and the relative exceedance magnitude above baseline.
    """
    if not readings:
        return 0.0
    exceeded = [r for r in readings if r.threshold_exceeded]
    if not exceeded:
        return 0.0
    ratio = len(exceeded) / len(readings)
    excesses = [
        min(2.0, (r.value - r.nominal_baseline) / r.nominal_baseline)
        for r in exceeded if r.nominal_baseline > 0
    ]
    avg_excess = sum(excesses) / len(readings) if excesses else 0.0
    score = (ratio * 0.70) + (min(1.0, avg_excess / 1.5) * 0.30)
    return round(min(1.0, max(0.0, score)), 2)


def calculate_citizen_agreement(reports: list[CitizenReport]) -> float:
    """
    Computes citizen consensus and report density index.
    Based on report count and average severity rating (1-5).
    """
    if not reports:
        return 0.0
    avg_severity = sum(r.severity_rating for r in reports) / len(reports)
    # Severity normalized to 0.2 - 1.0
    severity_norm = avg_severity / 5.0
    # Density factor (reaches saturation at 3 reports)
    density_factor = min(1.0, len(reports) / 3.0)
    score = (severity_norm * 0.55) + (density_factor * 0.35)
    return round(min(1.0, max(0.0, score)), 2)


def calculate_temporal_consistency(readings: list[SensorReading], reports: list[CitizenReport]) -> float:
    """
    Evaluates trend persistence over the observation window.
    Evaluates distinct observation hourly buckets across telemetry and field reports.
    """
    timestamps = [r.timestamp for r in readings] + [c.timestamp for c in reports]
    if not timestamps:
        return 0.0
    distinct_hours = {ts[:13] for ts in timestamps if len(ts) >= 13}
    hour_count = len(distinct_hours)
    if hour_count >= 4:
        consistency = 0.92
    elif hour_count >= 3:
        consistency = 0.85
    elif hour_count >= 2:
        consistency = 0.75
    else:
        consistency = 0.50
    return round(consistency, 2)


def compute_composite_evidence(
    sub_scores: EvidenceSubScores | None = None,
    readings: list[SensorReading] | None = None,
    reports: list[CitizenReport] | None = None,
    lab_assays: list[LabAssay] | None = None
) -> CompositeEvidenceResult:
    """
    Executes the deterministic evidence fusion algorithm.
    """
    if sub_scores is None:
        c_sensor = calculate_sensor_corroboration(readings or [])
        c_citizen = calculate_citizen_agreement(reports or [])
        c_temporal = calculate_temporal_consistency(readings or [], reports or [])
        sub_scores = EvidenceSubScores(
            sensor_corroboration=c_sensor,
            citizen_agreement=c_citizen,
            temporal_consistency=c_temporal
        )

    # Formula: S = 0.40 * Cs + 0.30 * Cc + 0.30 * Ct
    raw_score = (
        (WEIGHT_SENSOR * sub_scores.sensor_corroboration) +
        (WEIGHT_CITIZEN * sub_scores.citizen_agreement) +
        (WEIGHT_TEMPORAL * sub_scores.temporal_consistency)
    )
    score = round(raw_score, 2)

    # Check for laboratory confirmation override
    has_lab_positive = False
    if lab_assays:
        has_lab_positive = any(a.confirmed_positive for a in lab_assays)

    if has_lab_positive:
        epistemic_status = "confirmed"
        epistemic_display = "Laboratory Confirmed"
    elif score >= THRESHOLD_STRONG_INFERRED:
        epistemic_status = "inferred"
        epistemic_display = "Modeled Inference (Strong Multi-Source Support)"
    elif score >= THRESHOLD_MODERATE_INFERRED:
        epistemic_status = "inferred"
        epistemic_display = "Modeled Inference (Moderate Support)"
    else:
        epistemic_status = "observed"
        epistemic_display = "Direct Empirical Observation (Low Corroboration)"

    return CompositeEvidenceResult(
        score=score,
        methodology_version="v0.1-prototype",
        weights={
            "sensor": WEIGHT_SENSOR,
            "citizen": WEIGHT_CITIZEN,
            "temporal": WEIGHT_TEMPORAL
        },
        sub_scores=sub_scores,
        epistemic_status=epistemic_status,
        epistemic_display=epistemic_display,
        is_lab_confirmed=has_lab_positive
    )
