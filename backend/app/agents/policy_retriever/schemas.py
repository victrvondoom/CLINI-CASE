"""Schemas for the policy_retriever package — orchestrator + sub-agents."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models import ClinicalSnapshot, PolicyExcerpt

# =============================================================================
# Orchestrator I/O — parent agent contract
# =============================================================================

class PolicyRetrieverInput(BaseModel):
    payer_id: str
    snapshot: ClinicalSnapshot


class PolicyRetrieverOutput(BaseModel):
    excerpts: list[PolicyExcerpt]
    n_candidates: int
    reranked: bool


# -----------------------------------------------------------------------------
# 1. KeywordFilter (deterministic)
# -----------------------------------------------------------------------------


class KeywordFilterInput(BaseModel):
    payer_id: str
    treatment_name: str


class CandidateSection(BaseModel):
    """A (policy, section) pair surviving the keyword filter."""

    policy_id: str
    payer_id: str
    policy_title: str
    section_heading: str
    section_text: str
    source_url: str | None = None
    page_number: int | None = None


class KeywordFilterOutput(BaseModel):
    candidates: list[CandidateSection] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 2. LLMReranker (LLM)
# -----------------------------------------------------------------------------


class RerankerClinicalContext(BaseModel):
    """Minimal slice of the snapshot needed to rerank — keeps tokens low."""

    diagnosis_icd10: str
    diagnosis_description: str
    stage: str | None = None
    biomarkers: list[dict[str, Any]] = Field(default_factory=list)
    performance_status: str | None = None
    requested_treatment: str


class LLMRerankerInput(BaseModel):
    candidates: list[CandidateSection]
    clinical_context: RerankerClinicalContext
    top_k: int = Field(default=5, ge=1, le=10)


class LLMRerankerOutput(BaseModel):
    top_indices: list[int] = Field(..., min_length=1, max_length=10)


# -----------------------------------------------------------------------------
# 3. CitationResolver (deterministic)
# -----------------------------------------------------------------------------


class CitationResolverInput(BaseModel):
    candidates: list[CandidateSection]
    ranks: list[int] = Field(
        ..., description="Indices into candidates, in relevance order."
    )


class CitationResolverOutput(BaseModel):
    excerpts: list[PolicyExcerpt] = Field(default_factory=list)
