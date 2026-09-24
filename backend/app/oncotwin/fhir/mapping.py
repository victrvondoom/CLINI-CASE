"""FHIR R4 mapping for OncoTwin.

Outbound: every observation and clinical event the twin consumes is
expressible as a FHIR R4 resource — Patient, Observation, Condition,
MedicationRequest, MedicationAdministration, DiagnosticReport, Procedure,
CarePlan, Encounter (+ Communication for care-team notes). Synthetic
resources carry a meta.tag so they can never be mistaken for real data.

Inbound: FHIR Observations, and vendor-neutral wearable samples shaped like
Apple HealthKit or Android Health Connect exports, are mapped onto the
signal registry (LOINC-coded where a code exists). These adapters define the
mapping only — OncoTwin ships NO live vendor connection; a production
deployment would put an authorised device-data pipeline in front of them.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.oncotwin import SYNTHETIC_TAG
from app.oncotwin.records import (
    ANCHOR_DATE,
    ClinicalEvent,
    Observation,
    PatientProfile,
    PatientRecord,
    datetime_to_day,
)
from app.oncotwin.signals import CODE_INDEX, SIGNALS, UCUM

OBS_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category"
ACT_CODE = "http://terminology.hl7.org/CodeSystem/v3-ActCode"

# ---------------------------------------------------------------------------
# Wearable sample adapters (mapping definitions only)
# ---------------------------------------------------------------------------
HEALTHKIT_TYPES: dict[str, tuple[str, float]] = {
    # HK identifier → (signal key, multiplier to registry unit)
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", 1.0),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", 1.0),
    "HKQuantityTypeIdentifierBodyTemperature": ("temperature", 1.0),
    "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", 100.0),      # HealthKit reports a fraction
    "HKQuantityTypeIdentifierStepCount": ("steps", 1.0),
    "HKQuantityTypeIdentifierBodyMass": ("weight", 1.0),
    "HKQuantityTypeIdentifierBloodPressureSystolic": ("sbp", 1.0),
    "HKQuantityTypeIdentifierBloodPressureDiastolic": ("dbp", 1.0),
    "HKQuantityTypeIdentifierBloodGlucose": ("glucose_cgm", 1.0),
    "HKCategoryTypeIdentifierSleepAnalysis": ("sleep_hours", 1.0),    # pre-aggregated hours
}
HEALTH_CONNECT_TYPES: dict[str, tuple[str, str, float]] = {
    # record type → (signal key, value field, multiplier)
    "RestingHeartRateRecord": ("resting_hr", "beatsPerMinute", 1.0),
    "HeartRateVariabilityRmssdRecord": ("hrv_sdnn", "heartRateVariabilityMillis", 1.0),
    "BodyTemperatureRecord": ("temperature", "temperatureCelsius", 1.0),
    "OxygenSaturationRecord": ("spo2", "percentage", 1.0),
    "StepsRecord": ("steps", "count", 1.0),
    "WeightRecord": ("weight", "weightKg", 1.0),
    "BloodPressureRecord": ("sbp", "systolicMmHg", 1.0),
    "BloodGlucoseRecord": ("glucose_cgm", "levelMgPerDl", 1.0),
    "SleepSessionRecord": ("sleep_hours", "durationHours", 1.0),
}
MAPPING_NOTES = {
    "hrv_sdnn": ("Health Connect exposes RMSSD, not SDNN; the two are correlated but not interchangeable. "
                 "A deployment must keep one metric per patient so the personal baseline stays comparable."),
    "glucose_cgm": "Daily mean of CGM readings; coded with a local code pending terminology review.",
    "sleep_hours": "Sleep samples must be aggregated to total sleep per night before mapping.",
}


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def wearable_sample_to_observation(sample: dict[str, Any], patient_id: str) -> Observation:
    """Map one HealthKit- or Health-Connect-shaped sample to an internal Observation."""
    if "type" in sample and sample["type"] in HEALTHKIT_TYPES:
        key, mult = HEALTHKIT_TYPES[sample["type"]]
        value = float(sample["value"]) * mult
        when = _parse_time(sample.get("end") or sample.get("start"))
        vendor = f"healthkit:{sample.get('source', 'unknown')}"
    elif "recordType" in sample and sample["recordType"] in HEALTH_CONNECT_TYPES:
        key, field, mult = HEALTH_CONNECT_TYPES[sample["recordType"]]
        value = float(sample[field]) * mult
        when = _parse_time(sample.get("time") or sample.get("endTime") or sample.get("startTime"))
        vendor = f"healthconnect:{sample.get('dataOrigin', 'unknown')}"
    else:
        raise ValueError("Unsupported wearable sample: expected a known HealthKit `type` or Health Connect `recordType`")
    day = datetime_to_day(when)
    stamp = when.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return Observation(id=f"{patient_id}-{key}-ingest-{int(when.timestamp())}", signal=key, day=day,
                       value=round(value, SIGNALS[key].decimals), effective=stamp,
                       source=f"api/{vendor}", device_id=sample.get("device"))


def fhir_to_observation(resource: dict[str, Any], patient_id: str) -> Observation:
    """Map an inbound FHIR R4 Observation (LOINC or OncoTwin local code) to the registry."""
    if resource.get("resourceType") != "Observation":
        raise ValueError("resourceType must be Observation")
    key = None
    for coding in resource.get("code", {}).get("coding", []):
        key = CODE_INDEX.get((coding.get("system"), coding.get("code")))
        if key:
            break
    if key is None:
        raise ValueError("Observation.code is not a signal OncoTwin understands (see /oncotwin/signals)")
    vq = resource.get("valueQuantity") or {}
    if "value" not in vq:
        raise ValueError("Observation.valueQuantity.value is required")
    stamp = resource.get("effectiveDateTime") or resource.get("issued")
    if not stamp:
        raise ValueError("Observation.effectiveDateTime is required")
    when = _parse_time(stamp)
    return Observation(
        id=str(resource.get("id") or f"{patient_id}-{key}-ingest-{int(when.timestamp())}"),
        signal=key, day=datetime_to_day(when), value=float(vq["value"]),
        effective=when.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        source="api/fhir", status=resource.get("status", "final"),
    )


# ---------------------------------------------------------------------------
# Outbound resources
# ---------------------------------------------------------------------------


def _meta(synthetic: bool) -> dict[str, Any]:
    return {"tag": [SYNTHETIC_TAG]} if synthetic else {}


_FHIR_ID_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-.")


def fhir_id(raw: str) -> str:
    """Internal ids → valid FHIR ids ([A-Za-z0-9-.]{1,64}); deterministic."""
    return "".join(ch if ch in _FHIR_ID_OK else "-" for ch in raw)[:64]


def patient_to_fhir(p: PatientProfile) -> dict[str, Any]:
    birth_year = (ANCHOR_DATE - timedelta(days=365 * p.age)).year
    return {
        "resourceType": "Patient", "id": fhir_id(p.patient_id), "meta": _meta(p.synthetic),
        "identifier": [{"system": "https://clincase.health/oncotwin/patient", "value": p.label}],
        "name": [{"text": f"Synthetic {p.label}"}],
        "gender": p.sex, "birthDate": f"{birth_year}",
    }


def observation_to_fhir(o: Observation, patient_id: str, synthetic: bool = True) -> dict[str, Any]:
    spec = SIGNALS[o.signal]
    return {
        "resourceType": "Observation", "id": fhir_id(o.id), "meta": _meta(synthetic), "status": o.status,
        "category": [{"coding": [{"system": OBS_CATEGORY_SYSTEM, "code": spec.fhir_category}]}],
        "code": {"coding": [{"system": spec.code_system, "code": spec.code, "display": spec.code_display}],
                 "text": spec.label},
        "subject": {"reference": f"Patient/{fhir_id(patient_id)}"},
        "effectiveDateTime": o.effective,
        "valueQuantity": {"value": o.value, "unit": spec.unit_display, "system": UCUM, "code": spec.unit},
        "device": {"display": f"{spec.device} ({o.source})"},
    }


def event_to_fhir(e: ClinicalEvent, patient_id: str, synthetic: bool = True) -> dict[str, Any]:
    subj = {"reference": f"Patient/{fhir_id(patient_id)}"}
    cc = {"coding": [e.code], "text": e.display} if e.code else {"text": e.display}
    base = {"id": fhir_id(e.id), "meta": _meta(synthetic)}
    d = e.detail
    if e.fhir_type == "Condition":
        return {**base, "resourceType": "Condition", "subject": subj, "code": cc,
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                               "code": d.get("clinical_status", "active")}]},
                "onsetDateTime": e.effective,
                **({"stage": [{"summary": {"text": d["stage"]}}]} if d.get("stage") else {})}
    if e.fhir_type == "DiagnosticReport":
        return {**base, "resourceType": "DiagnosticReport", "status": "final", "subject": subj, "code": cc,
                "effectiveDateTime": e.effective, "conclusion": e.display}
    if e.fhir_type == "Observation":
        val = d.get("value")
        res = {**base, "resourceType": "Observation", "status": "final", "subject": subj, "code": cc,
               "effectiveDateTime": e.effective}
        if val is not None:
            res["valueQuantity"] = {"value": val, **({"unit": d["unit"]} if d.get("unit") else {})}
        return res
    if e.fhir_type == "CarePlan":
        return {**base, "resourceType": "CarePlan", "status": "active", "intent": "plan", "subject": subj,
                "title": e.display, "created": e.effective}
    if e.fhir_type == "MedicationRequest":
        return {**base, "resourceType": "MedicationRequest", "status": d.get("status", "active"), "intent": "order",
                "subject": subj, "medicationCodeableConcept": cc, "authoredOn": e.effective}
    if e.fhir_type == "MedicationAdministration":
        status = d.get("status", "completed")
        res = {**base, "resourceType": "MedicationAdministration", "status": status, "subject": subj,
               "medicationCodeableConcept": cc, "effectiveDateTime": e.effective}
        if status == "not-done":
            res["statusReason"] = [{"text": "Dose not taken (patient-reported / smart dispenser)"}]
        return res
    if e.fhir_type == "Encounter":
        klass = d.get("encounter_class", "AMB")
        res = {**base, "resourceType": "Encounter", "status": "finished" if d.get("discharge_day") else "in-progress",
               "class": {"system": ACT_CODE, "code": klass}, "subject": subj,
               "period": {"start": e.effective}}
        if d.get("qualifying"):
            res["reasonCode"] = [cc]
            res["hospitalization"] = {"admitSource": {"text": "emergency department"}}
        else:
            res["reasonCode"] = [{"text": d.get("reason", e.display)}]
        return res
    if e.fhir_type == "Procedure":
        return {**base, "resourceType": "Procedure", "status": "completed", "subject": subj, "code": cc,
                "performedDateTime": e.effective}
    return {**base, "resourceType": "Communication", "status": "completed", "subject": subj,
            "sent": e.effective, "payload": [{"contentString": e.display}]}


def build_bundle(record: PatientRecord, as_of_day: int, *, include_daily: bool = True) -> dict[str, Any]:
    pid = record.profile.patient_id
    synth = record.profile.synthetic
    entries = [patient_to_fhir(record.profile)]
    entries += [event_to_fhir(e, pid, synth) for e in record.events_until(as_of_day)]
    for o in record.observations_until(as_of_day):
        if include_daily or SIGNALS[o.signal].category == "lab":
            entries.append(observation_to_fhir(o, pid, synth))
    return {
        "resourceType": "Bundle", "type": "collection", "id": fhir_id(f"oncotwin-{pid}-d{as_of_day}"),
        "meta": _meta(synth),
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "entry": [{"fullUrl": f"urn:uuid:{r['resourceType']}-{r['id']}", "resource": r} for r in entries],
    }


def signal_catalog() -> list[dict[str, Any]]:
    return [{
        "key": s.key, "label": s.label, "category": s.category, "code_system": s.code_system, "code": s.code,
        "code_display": s.code_display, "unit_ucum": s.unit, "adverse_direction": s.adverse,
        "cadence_hours": s.cadence_hours, "plausible_range": list(s.plausible), "device": s.device,
        "model_input": s.in_model, "mapping_note": MAPPING_NOTES.get(s.key),
        "healthkit": [k for k, v in HEALTHKIT_TYPES.items() if v[0] == s.key],
        "health_connect": [k for k, v in HEALTH_CONNECT_TYPES.items() if v[0] == s.key],
    } for s in SIGNALS.values()]
