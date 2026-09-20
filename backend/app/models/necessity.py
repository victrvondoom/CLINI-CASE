"""Necessity assessment - output of the Necessity Reasoner agent.

Source of truth: PROPOSAL.md §9.3.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CriterionAssessment(BaseModel):
    criterion_text: str             # the policy criterion verbatim
    criterion_type: Literal["inclusion", "exclusion"] = "inclusion"
    """Inclusion criteria must be MET for approval. Exclusion criteria
    must NOT be MET (i.e. must NOT apply to the patient) for approval."""
    policy_excerpt_index: int       # which PolicyExcerpt it came from
    status: Literal["MET", "NOT_MET", "AMBIGUOUS"]
    supporting_evidence: list[str]  # excerpts from ClinicalSnapshot
    missing_evidence: str | None = None  # what would resolve an ambiguity
    confidence: float               # 0..1
    rationale: str                  # one or two sentences


class NecessityAssessment(BaseModel):
    criteria: list[CriterionAssessment]
    overall_confidence: float       # min of criterion confidences
    summary: str                    # 2-3 sentences plain English
