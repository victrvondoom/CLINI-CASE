"""Strict input contracts. Client payloads cannot set review identities or verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Analyte = Literal["total_arsenic", "inorganic_arsenic", "dissolved_arsenic"]
ANALYTES: tuple[Analyte, ...] = get_args(Analyte)


def now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class LabSample(StrictModel):
    sample_id: str = Field(min_length=1, max_length=120)
    location_name: str = Field(min_length=1, max_length=200)
    kind: Literal["stream", "source_water", "drinking_water"]
    laboratory: str = Field(min_length=1, max_length=200)
    collector: str = Field(min_length=1, max_length=200)
    report_reference: str = Field(min_length=1, max_length=300)
    method: str = Field(min_length=1, max_length=200)
    collected_at: AwareDatetime
    reported_at: AwareDatetime
    analyte: Analyte = "total_arsenic"
    value: float = Field(ge=0, le=100000)
    unit: Literal["ug/L", "mg/L"] = "ug/L"
    qualifier: Literal["eq", "lt"] = "eq"

    @model_validator(mode="after")
    def dates(self) -> LabSample:
        if self.reported_at < self.collected_at:
            raise ValueError("Laboratory report cannot precede sample collection")
        if self.reported_at > now():
            raise ValueError("Laboratory report cannot be in the future")
        return self


class ExposureHistory(StrictModel):
    patient_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9.-]+$")
    consent_reference: str = Field(min_length=1, max_length=200)
    consent_recorded: bool
    route: Literal["drinking", "other", "unknown"] = "unknown"
    pathway_confirmed: bool = False
    pathway_evidence: str = Field(default="", max_length=1000)
    treatment_context: str = Field(default="", max_length=500)
    started_on: AwareDatetime
    ended_on: AwareDatetime

    @model_validator(mode="after")
    def dates(self) -> ExposureHistory:
        if self.ended_on < self.started_on or self.ended_on > now():
            raise ValueError("Exposure dates must be ordered and not in the future")
        if self.pathway_confirmed and not self.pathway_evidence:
            raise ValueError("A confirmed pathway requires supporting evidence")
        return self


class ExposureCreate(StrictModel):
    observation_id: str = Field(min_length=1, max_length=100)
    sample: LabSample


class Versioned(StrictModel):
    expected_version: int = Field(ge=1)


class Attestation(Versioned):
    note: str = Field(min_length=8, max_length=1500)


class LinkRequest(Versioned):
    history: ExposureHistory


class ReviewRequest(Attestation):
    decision: Literal["reviewed", "more_information", "rejected"]


class FollowupRequest(Attestation):
    status: Literal["in_progress", "completed"]
    evidence_reference: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def completion_evidence(self) -> FollowupRequest:
        if self.status == "completed" and not self.evidence_reference:
            raise ValueError(
                "A completed follow-up requires a retest or investigation report reference"
            )
        return self


class CaseLinkRequest(Attestation):
    case_id: str = Field(min_length=1, max_length=100)
    same_patient_confirmed: Literal[True]


class AuditEvent(StrictModel):
    action: str
    actor_id: str
    at: AwareDatetime = Field(default_factory=now)
    note: str


class ExposureRecord(StrictModel):
    id: str = Field(default_factory=lambda: "oh-" + uuid.uuid4().hex[:20])
    organization_id: str
    version: int = 1
    observation_id: str
    waterbody_id: str
    waterbody_name: str
    synthetic: bool
    created_at: AwareDatetime = Field(default_factory=now)
    sample: LabSample
    lab_verified: bool = False
    history: ExposureHistory | None = None
    consent_withdrawn: bool = False
    review: Literal["pending", "reviewed", "more_information", "rejected"] = "pending"
    followup_status: Literal["requested", "in_progress", "completed"] = "requested"
    case_id: str | None = None
    followup_evidence_reference: str | None = None
    audit: list[AuditEvent] = Field(default_factory=list)
    incoming_bundle: dict[str, Any] | None = None
    gateway_job_id: str | None = None
    retest_of: str | None = None
    successor_id: str | None = None
    passport: list[dict[str, Any]] = Field(default_factory=list)


class RetestRequest(Attestation):
    sample: LabSample
