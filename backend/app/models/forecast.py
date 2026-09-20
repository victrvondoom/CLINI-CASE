"""Denial Forecaster output schema.

Source of truth: PROPOSAL.md §9.5 (and the Phase-1 deck Page 3 architecture
diagram + Page 6 "Denial probability forecasting" feature).

The forecaster runs on every case after the Decision Composer fires. Its job
is to predict what the payer will do with this submission — independent of
ClinCase's own verdict — so the coordinator can pre-empt avoidable denials
and the Appeals Drafter can pre-load the most likely contested points.

Decomposed into 3 sub-agents (declared in the agent file):
  1. Probability Estimator    — overall denial likelihood 0..1
  2. Reason Predictor         — top 3 likely denial rationales the payer would cite
  3. Appeal Path Recommender  — which appeal angle is highest-probability of overturn
"""
from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class DenialReason(BaseModel):
    """One predicted denial rationale, ranked by likelihood."""

    rank: int = Field(..., ge=1, le=10)
    text: str = Field(..., description="One-sentence reason in payer language.")
    policy_section_pointer: str = Field(
        default="",
        description="Which payer policy section drives this risk (e.g. 'Aetna 0048 § Initial Authorization Criteria').",
    )
    likelihood: float = Field(..., ge=0.0, le=1.0)


class AppealStrategy(BaseModel):
    """Recommended appeal angle if the case ends up denied."""

    model_config = {"populate_by_name": True}

    primary_angle: Literal[
        "biomarker_evidence",
        "guideline_alignment",
        "prior_therapy_failure",
        "step_therapy_completed",
        "medical_necessity_letter",
        "documentation_gap_resolved",
    ] = Field(
        ...,
        validation_alias=AliasChoices("primary_angle", "angle", "appeal_angle", "strategy"),
        description="Highest-probability angle for an appeal to overturn.",
    )
    rationale: str = Field(default="", description="Why this angle is strongest for this case.")
    expected_overturn_probability: float = Field(
        ..., ge=0.0, le=1.0,
        description="Expected probability the appeal succeeds, calibrated against KFF 2024 (80.7% baseline)."
    )


class DenialForecast(BaseModel):
    """Forecaster output.

    Notes:
      - `denial_probability` is the *payer's* denial probability — not ClinCase's
        verdict. A case with ClinCase verdict=APPROVE can still have a non-trivial
        payer denial probability (e.g. when the case sits at the policy edge).
      - `top_reasons` is empty when denial_probability is below 0.15.
      - `appeal_strategy` is None when denial_probability is below 0.35.
    """

    denial_probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0,
                              description="Forecaster's confidence in its probability estimate.")
    top_reasons: list[DenialReason] = Field(default_factory=list, max_length=3)
    appeal_strategy: AppealStrategy | None = None
    summary: str = Field(..., description="One-sentence summary fit for a coordinator dashboard.")
