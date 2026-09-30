"""Necessity assessment - output of the Necessity Reasoner agent.

Source of truth: PROPOSAL.md §9.3.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CriterionAssessment(BaseModel):
    criterion_text: str = Field(..., min_length=1)  # the policy criterion verbatim
    criterion_type: Literal["inclusion", "exclusion"] = "inclusion"
    """Inclusion criteria must be MET for approval. Exclusion criteria
    must NOT be MET (i.e. must NOT apply to the patient) for approval."""
    policy_excerpt_index: int = Field(..., ge=0)  # which PolicyExcerpt it came from
    status: Literal["MET", "NOT_MET", "AMBIGUOUS"]
    supporting_evidence: list[str]  # excerpts from ClinicalSnapshot
    missing_evidence: str | None = None  # what would resolve an ambiguity
    confidence: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    rationale: str  # one or two sentences


class NecessityAssessment(BaseModel):
    criteria: list[CriterionAssessment] = Field(..., min_length=1)
    overall_confidence: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    summary: str  # 2-3 sentences plain English

    @model_validator(mode="after")
    def bound_overall_confidence(self) -> NecessityAssessment:
        """The weakest criterion bounds the aggregate, regardless of model output.

        Preserve a lower aggregate supplied by a reviewer or model; never let
        an optimistic aggregate bypass a low-confidence criterion's review gate.
        """
        self.overall_confidence = min(
            self.overall_confidence, *(criterion.confidence for criterion in self.criteria)
        )
        return self
