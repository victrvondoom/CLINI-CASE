"""ProbabilityEstimator — Denial Forecaster sub-agent.

LLM-backed (Sonnet). Calibrated payer-denial probability anchored against
MA / oncology-PA base rates. Outputs estimator_confidence and a one-line
summary fit for a coordinator dashboard.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.denial_forecaster.schemas import (
    ProbabilityEstimatorInput,
    ProbabilityEstimatorOutput,
)
from app.agents.framework import (
    SONNET_REASONING,
    Agent,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "denial_forecaster" / "sub_agents" / "probability_estimator.txt"
).read_text(encoding="utf-8")


class ProbabilityEstimatorAgent(
    Agent[ProbabilityEstimatorInput, ProbabilityEstimatorOutput]
):
    name: ClassVar[str] = "probability_estimator"
    parent: ClassVar[str] = "denial_forecaster"
    role: ClassVar[str] = "denial_probability_calibration"
    description: ClassVar[str] = (
        "Base-rate-calibrated payer-denial probability ∈ [0,1] anchored against "
        "MA / oncology-PA denial rates. Outputs estimator_confidence and a one-line summary."
    )

    input_schema: ClassVar[type] = ProbabilityEstimatorInput
    output_schema: ClassVar[type] = ProbabilityEstimatorOutput

    primary_model: ClassVar = SONNET_REASONING
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 3500
    estimated_output_tokens: ClassVar[int] = 500
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(ProbabilityEstimatorOutput)]


probability_estimator = ProbabilityEstimatorAgent()
