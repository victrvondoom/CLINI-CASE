"""AquaHealth interoperability export — prototype structured representation.

Two shapes are offered, and the honesty of the labelling matters more than the
completeness of either:

  1. `to_prototype_record()` — the flat, self-describing JSON in the brief.
     This is AquaHealth's own shape. It is NOT a standard and does not claim
     to be one.

  2. `to_fhir_bundle()` — a FHIR R4 `Bundle` of `Observation` resources using
     standard `Observation` fields (status, category, code, effective,
     component, valueQuantity) with UCUM units.

On point 2, the caveat that matters: environmental water observations have no
official HL7 FHIR profile, and the codes below are AquaHealth's own
CodeSystem-style identifiers under an example URI, not LOINC or SNOMED
concepts. So this is *valid FHIR R4 structure carrying non-standard codes* —
useful because any FHIR client can parse, store and route it, while a receiver
still must map the codes. Every payload says exactly that in `meta.tag` and in
the accompanying disclaimer, because overclaiming standards conformance is
worse than not claiming it.

ClinCase's existing FHIR work (`app/api/fhir_pas.py`, `app/api/fhir_bulk.py`,
`app/oncotwin/fhir/`) is untouched: this module adds a parallel export for a
different resource domain and reuses the same Bundle idiom.
"""
from __future__ import annotations

from typing import Any

from app.aquahealth.models import Observation
from app.aquahealth.vocab import (
    BIODIVERSITY_FIELDS,
    CONTEXT_FIELDS,
    FIELD_LABELS,
    WATER_APPEARANCE_FIELDS,
    Presence,
)

#: AquaHealth's own code system. Deliberately an example.org URI so nobody
#: mistakes these for LOINC/SNOMED concepts.
CODE_SYSTEM = "https://example.org/fhir/CodeSystem/aquahealth-observation"

STANDARDS_NOTE = (
    "Prototype interoperability representation. Structurally valid FHIR R4 "
    "Bundle/Observation resources carrying AquaHealth-defined codes, not an "
    "official HL7 FHIR profile and not LOINC/SNOMED-coded. A receiving system "
    "must map these codes before clinical or regulatory use."
)

PROTOTYPE_NOTE = (
    "Prototype interoperability representation. AquaHealth's own JSON shape, "
    "not a standard."
)

#: UCUM units for the quantitative measurements.
_UCUM = {
    "ph": ("pH", "1"),
    "water_temperature_c": ("degree Celsius", "Cel"),
    "turbidity_ntu": ("nephelometric turbidity unit", "[NTU]"),
    "dissolved_oxygen_mgl": ("milligram per liter", "mg/L"),
}

_MEASUREMENT_DISPLAY = {
    "ph": "pH",
    "water_temperature_c": "Water temperature",
    "turbidity_ntu": "Turbidity",
    "dissolved_oxygen_mgl": "Dissolved oxygen",
}


def _presence_entries(
    fields: tuple[tuple[str, str], ...],
    section: Any,
) -> list[dict[str, Any]]:
    """Only fields the citizen actually answered.

    `unknown` / `not_available` are omitted rather than exported as false —
    exporting a non-answer as a negative finding would be the interoperability
    equivalent of inventing data.
    """
    out: list[dict[str, Any]] = []
    for field, label in fields:
        value = getattr(section, field, None)
        if not isinstance(value, Presence) or not value.is_informative:
            continue
        out.append({
            "code": field,
            "label": label,
            "value": value.value,
            "observed": value == Presence.OBSERVED,
        })
    return out


def to_prototype_record(obs: Observation) -> dict[str, Any]:
    """AquaHealth's flat JSON representation of one observation."""
    a = obs.assessment
    r = obs.review

    return {
        "representation": "aquahealth.prototype.v1",
        "note": PROTOTYPE_NOTE,
        "observationId": obs.reference,
        "internalId": obs.id,
        "caseType": obs.case_type,
        "waterbody": obs.waterbody_name,
        "waterbodyId": obs.waterbody_id,
        "location": (
            {
                "latitude": obs.location.latitude,
                "longitude": obs.location.longitude,
                "locality": obs.locality,
            }
            if obs.location
            else {"locality": obs.locality}
        ),
        "observedAt": obs.observed_at.isoformat(),
        "recordedAt": obs.created_at.isoformat(),
        "dataSource": obs.source.value,
        "verification": obs.verification.value,
        "isDemonstrationData": obs.is_demo,
        "measurements": [
            {
                "code": k,
                "display": _MEASUREMENT_DISPLAY.get(k, k),
                "value": v,
                "unit": _UCUM.get(k, ("", ""))[1],
            }
            for k, v in obs.measurements.present().items()
        ],
        "waterAppearance": _presence_entries(WATER_APPEARANCE_FIELDS, obs.appearance),
        "biodiversity": _presence_entries(BIODIVERSITY_FIELDS, obs.biodiversity),
        "environmentalContext": _presence_entries(CONTEXT_FIELDS, obs.context),
        "clarity": obs.appearance.clarity,
        "observerNote": obs.observer_note,
        "photoCount": len(obs.photos),
        "aiAssessment": (
            {
                "status": a.status.value,
                "statusLabel": "Prototype Ecosystem Observation Status",
                "statusReason": a.status_reason,
                "confidence": a.confidence.value,
                "dataQuality": a.data_quality.value,
                "completeness": a.completeness,
                "humanVerification": a.human_verification,
                "findings": [
                    {
                        "agent": f.agent,
                        "finding": f.finding,
                        "confidence": f.confidence.value,
                        "dataQuality": f.data_quality.value,
                        "uncertainty": f.uncertainty,
                        "recommendedNextStep": f.recommended_next_step,
                        "evidence": [
                            {
                                "field": e.field,
                                "label": e.label,
                                "value": e.value,
                                "interpretation": e.interpretation,
                            }
                            for e in f.evidence
                        ],
                    }
                    for f in a.findings
                ],
                "oneHealthNote": a.one_health_note,
                "earlyWarning": (
                    {
                        "active": a.early_warning.active,
                        "headline": a.early_warning.headline,
                        "reason": a.early_warning.reason,
                        "confidence": a.early_warning.confidence.value,
                        "recommendedNextStep": a.early_warning.recommended_next_step,
                        "notice": a.early_warning.notice,
                    }
                    if a.early_warning
                    else None
                ),
                "disclaimer": a.disclaimer,
            }
            if a
            else None
        ),
        "humanReview": (
            {
                "decision": r.decision.value,
                "reviewer": r.reviewer_label,
                "comment": r.comment,
                "correctedStatus": (
                    r.corrected_status.value if r.corrected_status else None
                ),
                "rejectedFindings": r.rejected_findings,
                "reviewedAt": r.reviewed_at.isoformat(),
            }
            if r
            else None
        ),
        "finalStatus": obs.effective_status.value,
    }


def _quantity_component(field: str, value: float) -> dict[str, Any]:
    unit, ucum = _UCUM.get(field, ("", "1"))
    return {
        "code": {
            "coding": [{
                "system": CODE_SYSTEM,
                "code": field,
                "display": _MEASUREMENT_DISPLAY.get(field, field),
            }],
        },
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
            "code": ucum,
        },
    }


def _presence_component(field: str, presence: Presence) -> dict[str, Any]:
    """A qualitative field as a FHIR Observation.component.

    Uses `valueCodeableConcept` with the four-state code, preserving the
    observed / not-observed / unknown distinction a boolean would destroy.
    """
    return {
        "code": {
            "coding": [{
                "system": CODE_SYSTEM,
                "code": field,
                "display": FIELD_LABELS.get(field, field),
            }],
        },
        "valueCodeableConcept": {
            "coding": [{
                "system": f"{CODE_SYSTEM}-presence",
                "code": presence.value,
                "display": presence.value.replace("_", " ").capitalize(),
            }],
        },
    }


def to_fhir_observation(obs: Observation) -> dict[str, Any]:
    """One observation as a FHIR R4 `Observation` resource."""
    components: list[dict[str, Any]] = []

    for field, value in obs.measurements.present().items():
        components.append(_quantity_component(field, value))

    for fields, section in (
        (WATER_APPEARANCE_FIELDS, obs.appearance),
        (BIODIVERSITY_FIELDS, obs.biodiversity),
        (CONTEXT_FIELDS, obs.context),
    ):
        for field, _label in fields:
            value = getattr(section, field, None)
            if isinstance(value, Presence) and value.is_informative:
                components.append(_presence_component(field, value))

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": obs.id,
        "meta": {
            "tag": [
                {
                    "system": f"{CODE_SYSTEM}-tag",
                    "code": "prototype-representation",
                    "display": STANDARDS_NOTE,
                },
                {
                    "system": f"{CODE_SYSTEM}-tag",
                    "code": obs.source.value,
                    "display": f"Data source: {obs.source.value}",
                },
            ],
        },
        "identifier": [{
            "system": "https://example.org/aquahealth/observation",
            "value": obs.reference,
        }],
        # `final` once a reviewer has completed the loop; `preliminary` while
        # the AI assessment is still awaiting human verification.
        "status": (
            "final"
            if obs.review is not None and obs.review_status.value == "completed"
            else "preliminary"
        ),
        "category": [{
            "coding": [{
                "system": f"{CODE_SYSTEM}-category",
                "code": "environmental",
                "display": "Environmental / freshwater ecosystem observation",
            }],
        }],
        "code": {
            "coding": [{
                "system": CODE_SYSTEM,
                "code": "freshwater-ecosystem-observation",
                "display": "Urban freshwater ecosystem citizen observation",
            }],
            "text": f"Freshwater observation at {obs.waterbody_name}",
        },
        "effectiveDateTime": obs.observed_at.isoformat(),
        "issued": obs.created_at.isoformat(),
        "component": components,
    }

    if obs.location is not None:
        # There is no standard Observation element for a sampling coordinate,
        # so it travels as an explicitly-named extension rather than being
        # forced into an unrelated standard field.
        resource["extension"] = [{
            "url": "https://example.org/fhir/StructureDefinition/aquahealth-location",
            "extension": [
                {"url": "latitude", "valueDecimal": obs.location.latitude},
                {"url": "longitude", "valueDecimal": obs.location.longitude},
            ],
        }]

    if obs.assessment is not None:
        a = obs.assessment
        resource["note"] = [
            {
                "text": (
                    f"Prototype Ecosystem Observation Status: {a.status.value}. "
                    f"{a.status_reason} Confidence: {a.confidence.value}. "
                    f"Data quality: {a.data_quality.value}. "
                    f"Human verification: {a.human_verification}."
                ),
            },
            {"text": a.disclaimer},
        ]
        resource["interpretation"] = [{
            "coding": [{
                "system": f"{CODE_SYSTEM}-status",
                "code": a.status.value,
                "display": a.status.value.replace("_", " ").title(),
            }],
        }]

    return resource


def to_fhir_bundle(observations: list[Observation]) -> dict[str, Any]:
    """A FHIR R4 collection Bundle of the given observations."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {
            "tag": [{
                "system": f"{CODE_SYSTEM}-tag",
                "code": "prototype-representation",
                "display": STANDARDS_NOTE,
            }],
        },
        "total": len(observations),
        "entry": [{"resource": to_fhir_observation(o)} for o in observations],
    }


def signal_catalog() -> dict[str, Any]:
    """Self-describing catalogue of every code this module can emit.

    Lets an integrator see the whole vocabulary without submitting an
    observation first — and makes clear which codes are AquaHealth's own.
    """
    return {
        "system": CODE_SYSTEM,
        "standards_note": STANDARDS_NOTE,
        "presence_values": [p.value for p in Presence],
        "measurements": [
            {
                "code": k,
                "display": _MEASUREMENT_DISPLAY.get(k, k),
                "unit": v[0],
                "ucum": v[1],
            }
            for k, v in _UCUM.items()
        ],
        "qualitative": {
            "water_appearance": [
                {"code": c, "display": d} for c, d in WATER_APPEARANCE_FIELDS
            ],
            "biodiversity": [
                {"code": c, "display": d} for c, d in BIODIVERSITY_FIELDS
            ],
            "environmental_context": [
                {"code": c, "display": d} for c, d in CONTEXT_FIELDS
            ],
        },
    }
