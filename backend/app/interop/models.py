"""Typed gateway contracts; incoming data never grants clinical trust."""

from typing import Any, Literal
from uuid import uuid4

from pydantic import ConfigDict, Field

from app.onehealth.models import StrictModel, now

TARGETS = {
    "sample_id": "Specimen.identifier",
    "location_name": "Location.name",
    "kind": "Location.type",
    "laboratory": "Organization.name",
    "collector": "PractitionerRole.code.text",
    "report_reference": "Observation.identifier",
    "method": "Observation.method.text",
    "collected_at": "Observation.effectiveDateTime",
    "reported_at": "Observation.issued",
    "analyte": "Observation.code",
    "value": "Observation.valueQuantity.value",
    "unit": "Observation.valueQuantity.code",
    "qualifier": "Observation.valueQuantity.comparator",
    "waterbody_name": "Location.name (waterbody)",
}


class Source(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, allow_inf_nan=False)
    source_system: str = Field(min_length=1, max_length=100)
    original_record_id: str = Field(min_length=1, max_length=120)
    format: Literal["json", "csv", "fhir"] = "json"
    payload: dict[str, Any] | str
    synthetic: bool = False


class Mapping(StrictModel):
    source_field: str
    target: str | None = None
    fhir_target: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    origin: Literal["deterministic", "ai_suggested", "unresolved"] = "unresolved"
    decision: Literal["pending", "accepted", "rejected"] = "pending"
    concept: Literal["total_arsenic", "inorganic_arsenic"] | None = None
    terminology_status: Literal["local_code", "unresolved"] = "unresolved"
    reason: str = "Unresolved; human mapping required"
    reviewer: str | None = None


class Suggestions(StrictModel):
    mappings: list[Mapping] = Field(max_length=80)


class Event(StrictModel):
    timestamp: str = Field(default_factory=lambda: now().isoformat())
    event_type: str
    actor: str
    status: str
    correlation_id: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class Job(StrictModel):
    id: str = Field(default_factory=lambda: "ig-" + uuid4().hex)
    organization_id: str
    version: int = 1
    source: Source
    fields: dict[str, Any] = Field(default_factory=dict)
    mappings: list[Mapping] = Field(default_factory=list)
    mapping_version: int = 0
    ai_status: str = "not_requested"
    normalized: dict[str, Any] | None = None
    bundle: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    transfers: list[dict[str, Any]] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    exposure_id: str | None = None
    exposure_version: int | None = None
    passport: list[dict[str, Any]] = Field(default_factory=list)


class Command(StrictModel):
    job_id: str
    expected_version: int = Field(ge=1)


class Analyze(Command):
    use_ai: bool = False


class Decision(Command):
    source_field: str
    target: str | None = None
    concept: Literal["total_arsenic", "inorganic_arsenic"] | None = None


class ValidationRequest(Command):
    bundle: dict[str, Any]


class Transfer(Command):
    receiver: Literal["clinical"] = "clinical"


class Receive(StrictModel):
    correlation_id: str = Field(min_length=1, max_length=100)
    bundle: dict[str, Any]
