"""Longitudinal patient record types shared by the simulator, engine and FHIR layer.

A `PatientRecord` is what the twin is allowed to see: timestamped
observations and clinical events, each with provenance. Simulator ground
truth (latent loads, future events) lives in `SimulationTruth` and is NEVER
passed to the twin engine — only to label generation and tests.

Days are 1-based study days; `effective` carries the real ISO-8601 instant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

# Day 1 of every synthetic timeline. Chosen so a 56-day course ends shortly
# before the build date; purely a display anchor.
ANCHOR_DATE = date(2026, 7, 27)

EventKind = Literal[
    "diagnosis", "pathology", "genomics", "imaging", "careplan", "medication_request",
    "chemo_dose", "gcsf_dose", "supportive_dose", "antibiotic", "hydration",
    "encounter", "procedure", "performance_status", "clinician_note",
]


def day_to_datetime(day: int, hour: int = 8, minute: int = 0) -> datetime:
    return datetime.combine(ANCHOR_DATE + timedelta(days=day - 1), time(hour, minute), tzinfo=UTC)


def day_to_iso(day: int, hour: int = 8, minute: int = 0) -> str:
    return day_to_datetime(day, hour, minute).isoformat().replace("+00:00", "Z")


def datetime_to_day(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt.astimezone(UTC).date() - ANCHOR_DATE).days + 1


@dataclass
class Observation:
    id: str
    signal: str
    day: int
    value: float
    effective: str
    source: str                     # e.g. "wearable/smartwatch", "ehr/lab", "pro/app", "api/ingest"
    status: str = "final"
    device_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "signal": self.signal, "day": self.day, "value": self.value,
            "effective": self.effective, "source": self.source, "status": self.status,
            "device_id": self.device_id,
        }


@dataclass
class ClinicalEvent:
    id: str
    day: int
    kind: EventKind
    display: str
    effective: str
    fhir_type: str
    code: dict[str, str] | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "day": self.day, "kind": self.kind, "display": self.display,
            "effective": self.effective, "fhir_type": self.fhir_type, "code": self.code,
            "detail": self.detail,
        }


@dataclass
class PatientProfile:
    patient_id: str
    label: str                       # e.g. "OT-001"
    age: int
    sex: Literal["female", "male"]
    cancer: str                      # e.g. "Invasive ductal carcinoma, left breast"
    icd10: str
    stage: str
    biomarkers: dict[str, str]
    regimen_code: str
    payer_id: str
    comorbidities: list[dict[str, str]]
    ecog: int
    archetype: str
    narrative: str
    diabetic: bool = False
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id, "label": self.label, "age": self.age, "sex": self.sex,
            "cancer": self.cancer, "icd10": self.icd10, "stage": self.stage,
            "biomarkers": self.biomarkers, "regimen_code": self.regimen_code,
            "payer_id": self.payer_id, "comorbidities": self.comorbidities, "ecog": self.ecog,
            "archetype": self.archetype, "narrative": self.narrative, "diabetic": self.diabetic,
            "synthetic": self.synthetic,
        }


@dataclass
class PatientRecord:
    """Everything a data source has delivered for one patient (all days)."""
    profile: PatientProfile
    observations: list[Observation]
    events: list[ClinicalEvent]
    n_days: int
    planned_dose_days: list[int]      # CarePlan schedule (known in advance)

    def observations_until(self, as_of_day: int) -> list[Observation]:
        return [o for o in self.observations if o.day <= as_of_day]

    def events_until(self, as_of_day: int) -> list[ClinicalEvent]:
        return [e for e in self.events if e.day <= as_of_day]


@dataclass
class SimulationTruth:
    """Ground truth — for labels, validation and tests ONLY."""
    infection: list[float]
    dehydration: list[float]
    fatigue: list[float]
    anc_true: list[float]
    event_onsets: list[dict[str, Any]]   # {day, condition, discharge_day}
    admitted_days: list[int]
