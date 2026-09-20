"""Schemas for the Clinical Extractor package — orchestrator + 3 sub-agents."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import Biomarker, ClinicalSnapshot

# =============================================================================
# Orchestrator I/O
# =============================================================================


class ClinicalExtractorInput(BaseModel):
    fhir_bundle: dict[str, Any]
    physician_note: str | None = None
    requested_treatment: dict[str, Any]


class ClinicalExtractorOutput(BaseModel):
    snapshot: ClinicalSnapshot
    n_resources_validated: int
    phi_entities_masked: int
    n_biomarkers_extracted: int


# =============================================================================
# Sub-agent #1: FHIRResourceValidator
# =============================================================================


class FHIRResourceValidatorInput(BaseModel):
    fhir_bundle: dict[str, Any]


class FHIRResourceIssue(BaseModel):
    severity: Literal["error", "warning"]
    path: str
    message: str


class FHIRResourceValidatorOutput(BaseModel):
    is_valid: bool
    resource_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[FHIRResourceIssue] = Field(default_factory=list)


# =============================================================================
# Sub-agent #2: BiomarkerSpecialist
# =============================================================================


class BiomarkerSpecialistInput(BaseModel):
    fhir_bundle: dict[str, Any]
    physician_note_redacted: str | None = None
    requested_treatment_name: str


class BiomarkerSpecialistOutput(BaseModel):
    biomarkers: list[Biomarker] = Field(default_factory=list)


# =============================================================================
# Sub-agent #3: PHISanitizer
# =============================================================================


class PHISanitizerInput(BaseModel):
    text: str


class PHIMask(BaseModel):
    type: Literal["NAME", "DOB", "MRN", "SSN", "PHONE", "ADDRESS", "EMAIL"]
    masked_value: str
    char_offset: int


class PHISanitizerOutput(BaseModel):
    sanitized_text: str
    masks: list[PHIMask] = Field(default_factory=list)
    bedrock_guardrail_compatible: bool = True
