"""Schemas for the decision_composer package — orchestrator + sub-agents."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models import (
    Citation,
    ClinicalSnapshot,
    Decision,
    NecessityAssessment,
    PolicyExcerpt,
)

# =============================================================================
# Orchestrator I/O — parent agent contract
# =============================================================================

class DecisionComposerInput(BaseModel):
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt] = Field(..., min_length=1)
    assessment: NecessityAssessment

    @model_validator(mode="after")
    def validate_policy_references(self) -> DecisionComposerInput:
        if any(c.policy_excerpt_index >= len(self.excerpts) for c in self.assessment.criteria):
            raise ValueError("Assessment references an unavailable policy excerpt")
        return self


class DecisionComposerOutput(BaseModel):
    decision: Decision
    verdict_rule: str
    n_citations: int


# -----------------------------------------------------------------------------
# 1. VerdictSynthesizer (deterministic)
# -----------------------------------------------------------------------------


class VerdictSynthesizerInput(BaseModel):
    assessment: NecessityAssessment
    approve_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class VerdictDecisionTrace(BaseModel):
    """The deterministic rule's full evaluation trace — fully audit-replayable."""

    triggered_rule: Literal[
        "inclusion_NOT_MET",
        "exclusion_MET",
        "any_AMBIGUOUS",
        "low_overall_confidence",
        "all_clear_approve",
    ]
    triggering_criterion_index: int | None = None
    overall_confidence: float


class VerdictSynthesizerOutput(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    trace: VerdictDecisionTrace


# -----------------------------------------------------------------------------
# 2. RationaleWriter (LLM)
# -----------------------------------------------------------------------------


class RationaleWriterInput(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    assessment: NecessityAssessment
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt]


class RationaleWriterOutput(BaseModel):
    rationale: str = Field(..., description="2–4 sentence executive rationale.")
    risk_flags: list[str] = Field(default_factory=list, max_length=5)


# -----------------------------------------------------------------------------
# 3. CitationLinker (LLM, Haiku)
# -----------------------------------------------------------------------------


class CitationLinkerInput(BaseModel):
    rationale: str
    assessment: NecessityAssessment
    excerpts: list[PolicyExcerpt]
    snapshot: ClinicalSnapshot


class CitationLinkerOutput(BaseModel):
    citations: list[Citation] = Field(..., min_length=1, max_length=10)
    every_claim_has_pointer: bool = Field(
        ...,
        description="Asserted by the LLM and re-verified by the parent post-call.",
    )
