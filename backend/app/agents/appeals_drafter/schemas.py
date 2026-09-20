"""Schemas for the appeals_drafter package — orchestrator + sub-agents."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import (
    AppealArgument,
    AppealDraft,
    ClinicalSnapshot,
    Decision,
    NecessityAssessment,
    PolicyExcerpt,
)

# =============================================================================
# Orchestrator I/O — parent agent contract
# =============================================================================

class AppealsDrafterInput(BaseModel):
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt]
    assessment: NecessityAssessment
    decision: Decision
    payer_id: str
    patient_initials: str = "JD"
    external_denial_letter: str | None = None


class AppealsDrafterOutput(BaseModel):
    appeal: AppealDraft
    n_counter_items: int
    n_nccn_refs: int
    letter_length_chars: int


# -----------------------------------------------------------------------------
# 1. CounterEvidenceFinder
# -----------------------------------------------------------------------------


class CounterEvidenceItem(BaseModel):
    contested_criterion: str
    payer_position: str
    counter_position: str
    cited_evidence: list[str] = Field(default_factory=list, max_length=4)


class CounterEvidenceFinderInput(BaseModel):
    decision: Decision
    assessment: NecessityAssessment
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt]


class CounterEvidenceFinderOutput(BaseModel):
    items: list[CounterEvidenceItem] = Field(..., min_length=1, max_length=5)


# -----------------------------------------------------------------------------
# 2. NCCNReferenceSpecialist
# -----------------------------------------------------------------------------


class NCCNReferenceSpecialistInput(BaseModel):
    treatment_name: str
    diagnosis_icd10: str
    counter_items: list[CounterEvidenceItem]


class NCCNReferenceSpecialistOutput(BaseModel):
    nccn_references: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="Precise NCCN guideline references (e.g. 'NCCN Breast 4.2025 § BINV-J').",
    )


# -----------------------------------------------------------------------------
# 3. LetterComposer
# -----------------------------------------------------------------------------


class LetterComposerInput(BaseModel):
    counter_items: list[CounterEvidenceItem]
    nccn_references: list[str]
    decision: Decision
    snapshot: ClinicalSnapshot
    payer_id: str


class LetterComposerOutput(BaseModel):
    appeal_body: str = Field(..., description="Formal letter prose, ~600 words.")
    structured_arguments: list[AppealArgument] = Field(default_factory=list)
    requested_action: str
    attachments_referenced: list[str] = Field(default_factory=list)
