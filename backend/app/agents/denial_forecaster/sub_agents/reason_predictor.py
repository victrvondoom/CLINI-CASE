"""ReasonPredictor — Denial Forecaster sub-agent.

LLM-backed (Haiku). Up to 3 ranked payer denial rationales with policy-section
pointers. Empty list when denial_probability < 0.15.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.denial_forecaster.schemas import (
    ReasonPredictorInput,
    ReasonPredictorOutput,
)
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "denial_forecaster" / "sub_agents" / "reason_predictor.txt"
).read_text(encoding="utf-8")


class ReasonPredictorAgent(Agent[ReasonPredictorInput, ReasonPredictorOutput]):
    name: ClassVar[str] = "reason_predictor"
    parent: ClassVar[str] = "denial_forecaster"
    role: ClassVar[str] = "denial_reason_ranking"
    description: ClassVar[str] = (
        "Up to 3 ranked payer denial rationales with policy-section pointers; "
        "empty when denial_probability < 0.15."
    )

    input_schema: ClassVar[type] = ReasonPredictorInput
    output_schema: ClassVar[type] = ReasonPredictorOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 2500
    estimated_output_tokens: ClassVar[int] = 800
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(ReasonPredictorOutput)]


reason_predictor = ReasonPredictorAgent()
