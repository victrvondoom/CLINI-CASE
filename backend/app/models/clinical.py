"""Clinical snapshot - structured output of the Clinical Extractor agent.

Source of truth: PROPOSAL.md §9.1.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    icd10_code: str
    description: str
    stage: str | None = None  # AJCC notation, e.g. "IIIA", "IV"
    onset_date: str | None = None
    source_resource_id: str  # FHIR Condition.id


class PriorTherapy(BaseModel):
    therapy_name: str
    start_date: str | None = None
    end_date: str | None = None
    response: str | None = None  # complete | partial | progression | intolerance
    source_resource_id: str | None = None


class Biomarker(BaseModel):
    name: str  # e.g. "HER2", "ER", "PR", "PD-L1", "BRAF V600E"
    value: str  # e.g. "positive", "negative", "3+", "high"
    test_date: str | None = None
    source_resource_id: str | None = None


class Comorbidity(BaseModel):
    icd10_code: str
    description: str


class RequestedTreatment(BaseModel):
    name: str
    hcpcs_code: str | None = None
    j_code: str | None = None
    dose: str | None = None
    frequency: str | None = None
    intent: str | None = None  # curative | palliative | adjuvant | neoadjuvant


class ClinicalSnapshot(BaseModel):
    """The structured clinical record consumed by every downstream agent."""

    patient_age: int | None = None
    patient_sex: str | None = None
    primary_diagnosis: Diagnosis
    additional_diagnoses: list[Diagnosis] = Field(default_factory=list)
    prior_therapies: list[PriorTherapy] = Field(default_factory=list)
    biomarkers: list[Biomarker] = Field(default_factory=list)
    comorbidities: list[Comorbidity] = Field(default_factory=list)
    performance_status: str | None = None  # ECOG 0-4 as string, e.g. "1"
    requested_treatment: RequestedTreatment
    free_text_summary: str  # 3-5 sentence narrative for the trace UI
