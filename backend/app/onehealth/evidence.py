"""Deterministic evidence gates, not disease prediction or causal attribution."""

from __future__ import annotations

from datetime import timedelta

from app.onehealth.models import ExposureRecord

WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/arsenic"
NOTICE = (
    "Exposure decision support only. Not a diagnosis, disease probability, water-safety "
    "certification or proof that water caused disease. Clinical models remain unchanged."
)


def assess(record: ExposureRecord) -> dict:
    h = record.history
    gates = [
        ("laboratory", "Laboratory evidence verified by a reviewer", record.lab_verified),
        (
            "consent",
            "Recorded consent remains active",
            bool(h and h.consent_recorded and not record.consent_withdrawn),
        ),
        (
            "pathway",
            "Actual drinking-water pathway documented",
            bool(h and h.route == "drinking" and h.pathway_confirmed and h.pathway_evidence),
        ),
        (
            "point_of_use",
            "Sample represents consumed drinking water",
            record.sample.kind == "drinking_water",
        ),
        ("treatment", "Treatment and water-use context recorded", bool(h and h.treatment_context)),
        (
            "time",
            "Sample collected within documented exposure period",
            bool(h and h.started_on <= record.sample.collected_at <= h.ended_on),
        ),
    ]
    ready = all(passed for _, _, passed in gates)
    concentration = record.sample.value * (1000 if record.sample.unit == "mg/L" else 1)
    # The WHO provisional drinking-water guideline is not a diagnostic threshold.
    comparison = "not_applicable"
    if record.lab_verified and record.sample.kind == "drinking_water":
        if record.sample.qualifier == "lt":
            comparison = "below_reporting_limit_not_quantified"
        else:
            comparison = (
                "above_provisional_guideline"
                if concentration > 10
                else "at_or_below_provisional_guideline"
            )
    state = "ready_for_clinical_review" if ready else "evidence_incomplete"
    if record.consent_withdrawn:
        state = "consent_withdrawn"
    elif record.review == "rejected":
        state = "review_rejected"
    elif record.review == "more_information":
        state = "more_information_requested"
    elif ready and record.review == "reviewed":
        state = "reviewed_exposure_context"
    return {
        "state": state,
        "gates": [{"id": code, "label": label, "passed": passed} for code, label, passed in gates],
        "eligible_for_review": ready and not record.consent_withdrawn,
        "concentration_ug_l": concentration,
        "comparison": comparison,
        "reference": {
            "value": 10,
            "unit": "ug/L",
            "name": "WHO provisional arsenic drinking-water guideline",
            "url": WHO_URL,
        },
        "meaning": "A single sample does not establish historical dose; a value below this guideline does not certify water safety.",
        "clinical_context": {
            "oncology": "Long-term inorganic arsenic ingestion is linked to skin, bladder and lung cancers; this record does not establish cause or diagnosis.",
            "cardiovascular": "Long-term inorganic arsenic ingestion is associated with cardiovascular disease; exposure is not an input to the existing CAD classifier.",
            "speciation": "Total arsenic is not a measurement of inorganic arsenic dose. No cancer-risk calculator is applied.",
        },
        "notice": NOTICE,
    }


def ablation(record: ExposureRecord) -> list[dict]:
    """Remove one evidence dependency at a time on copies; never change stored evidence."""
    rows = []
    for gate in assess(record)["gates"]:
        candidate = record.model_copy(deep=True)
        if gate["id"] == "laboratory":
            candidate.lab_verified = False
        elif gate["id"] == "point_of_use":
            candidate.sample.kind = "stream"
        elif candidate.history:
            if gate["id"] == "consent":
                candidate.history.consent_recorded = False
            elif gate["id"] == "pathway":
                candidate.history.pathway_confirmed = False
            elif gate["id"] == "treatment":
                candidate.history.treatment_context = ""
            elif gate["id"] == "time":
                candidate.history.ended_on = candidate.sample.collected_at - timedelta(seconds=1)
        result = assess(candidate)
        rows.append(
            {
                "removed": gate["label"],
                "eligible_for_review": result["eligible_for_review"],
                "state": result["state"],
            }
        )
    return rows
