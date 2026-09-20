"""Schemas for the Necessity Reasoner package.

Co-located with the agents that use them. Contains:
  • Orchestrator I/O    — NecessityReasonerInput / NecessityReasonerOutput
  • Sub-agent I/O       — for criterion_splitter, evidence_matcher, confidence_calibrator

These are PRIVATE to the parent package. Cross-package imports come from
canonical types in `app.models` (NecessityAssessment, ClinicalSnapshot, etc.)
which are stable, app-wide contracts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models import (
    ClinicalSnapshot,
    CriterionAssessment,
    NecessityAssessment,
    PolicyExcerpt,
)

# =============================================================================
# Orchestrator I/O — what the parent agent receives + emits
# =============================================================================


class NecessityReasonerInput(BaseModel):
    """Input contract for the Necessity Reasoner parent agent."""
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt] = Field(..., min_length=1)


class NecessityReasonerOutput(BaseModel):
    """Output contract for the Necessity Reasoner parent agent."""
    assessment: NecessityAssessment
    n_atomic_criteria: int
    n_evidence_matches: int
    overall_confidence: float
    triggered_hitl: bool = False


# =============================================================================
# Sub-agent #1: CriterionSplitter
# =============================================================================


class AtomicCriterion(BaseModel):
    """One indivisible inclusion/exclusion criterion."""
    text: str
    criterion_type: Literal["inclusion", "exclusion"] = "inclusion"
    policy_excerpt_index: int = Field(..., ge=0)
    section_pointer: str = ""


class CriterionSplitterInput(BaseModel):
    excerpts: list[PolicyExcerpt]
    requested_treatment_name: str


class CriterionSplitterOutput(BaseModel):
    atomic_criteria: list[AtomicCriterion] = Field(..., min_length=1, max_length=20)


# =============================================================================
# Sub-agent #2: EvidenceMatcher
# =============================================================================


class EvidenceMatcherInput(BaseModel):
    criterion: AtomicCriterion
    snapshot: ClinicalSnapshot


class EvidenceMatch(BaseModel):
    """Output schema for the evidence_matcher sub-agent.

    The `criterion` field is optional on the LLM's output — it's set by the
    orchestrator post-call (the parent already knows which criterion it
    sent) so we don't waste tokens making the LLM echo it back.
    """

    criterion: AtomicCriterion | None = None
    status: Literal["MET", "NOT_MET", "AMBIGUOUS"]
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: str | None = None
    rationale: str


# =============================================================================
# Sub-agent #3: ConfidenceCalibrator
# =============================================================================


class CalibratedCriterion(BaseModel):
    match: EvidenceMatch
    confidence: float = Field(..., ge=0.0, le=1.0)


class ConfidenceCalibratorInput(BaseModel):
    matches: list[EvidenceMatch]


class ConfidenceCalibratorOutput(BaseModel):
    """Output schema for confidence_calibrator.

    Returns just the per-criterion confidences (in the SAME ORDER as the
    input matches) plus the aggregate. The orchestrator zips these with the
    input matches to assemble the full NecessityAssessment — keeping the
    calibrator's output small and the LLM's job focused (numeric calibration,
    not echoing back all the match content).
    """

    confidences: list[float] = Field(..., min_length=1, description="One confidence ∈ [0,1] per input match, in input order.")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str

    def to_assessment(self, matches: list[EvidenceMatch]) -> NecessityAssessment:
        """Zip calibrated confidences with the input matches to form the
        canonical NecessityAssessment. The orchestrator owns the matches
        because it sent them — the calibrator only returns numbers."""
        n = min(len(self.confidences), len(matches))
        criteria: list[CriterionAssessment] = []
        for i in range(n):
            m = matches[i]
            conf = self.confidences[i]
            crit = m.criterion
            criteria.append(
                CriterionAssessment(
                    criterion_text=crit.text if crit else "(criterion missing)",
                    criterion_type=crit.criterion_type if crit else "inclusion",
                    policy_excerpt_index=crit.policy_excerpt_index if crit else 0,
                    status=m.status,
                    supporting_evidence=m.supporting_evidence,
                    missing_evidence=m.missing_evidence,
                    confidence=conf,
                    rationale=m.rationale,
                )
            )
        return NecessityAssessment(
            criteria=criteria,
            overall_confidence=self.overall_confidence,
            summary=self.summary,
        )
