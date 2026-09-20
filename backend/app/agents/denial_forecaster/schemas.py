"""Schemas for the denial_forecaster package — orchestrator + sub-agents."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import (
    ClinicalSnapshot,
    Decision,
    NecessityAssessment,
    PolicyExcerpt,
)
from app.models.forecast import (
    AppealStrategy,
    DenialForecast,
    DenialReason,
)

# =============================================================================
# Orchestrator I/O — parent agent contract
# =============================================================================

class DenialForecasterInput(BaseModel):
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt]
    assessment: NecessityAssessment
    decision: Decision
    payer_id: str


class DenialForecasterOutput(BaseModel):
    forecast: DenialForecast
    n_reasons: int
    appeal_strategy_present: bool


# -----------------------------------------------------------------------------
# 1. ProbabilityEstimator
# -----------------------------------------------------------------------------


class ProbabilityEstimatorInput(BaseModel):
    decision: Decision
    assessment: NecessityAssessment
    snapshot: ClinicalSnapshot
    excerpts: list[PolicyExcerpt]
    payer_id: str


class ProbabilityEstimatorOutput(BaseModel):
    denial_probability: float = Field(..., ge=0.0, le=1.0)
    estimator_confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str = Field(..., description="One sentence for coordinator dashboard.")


# -----------------------------------------------------------------------------
# 2. ReasonPredictor
# -----------------------------------------------------------------------------


class ReasonPredictorInput(BaseModel):
    denial_probability: float
    decision: Decision
    assessment: NecessityAssessment
    excerpts: list[PolicyExcerpt]
    payer_id: str


class ReasonPredictorOutput(BaseModel):
    top_reasons: list[DenialReason] = Field(default_factory=list, max_length=3)


# -----------------------------------------------------------------------------
# 3. AppealPathRecommender
# -----------------------------------------------------------------------------


class AppealPathRecommenderInput(BaseModel):
    denial_probability: float
    decision: Decision
    snapshot: ClinicalSnapshot
    top_reasons: list[DenialReason]
    payer_id: str


class AppealPathRecommenderOutput(BaseModel):
    strategy: AppealStrategy | None = None
    skipped_reason: str | None = Field(
        default=None,
        description="Populated when denial_probability < 0.35 and we skip the recommendation.",
    )
