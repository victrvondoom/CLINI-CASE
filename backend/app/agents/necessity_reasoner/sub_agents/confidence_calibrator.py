"""ConfidenceCalibrator — assigns calibrated confidence + aggregates.

LLM-backed (Haiku). The aggregation invariant
(overall_confidence = MIN of per-criterion) is enforced deterministically
post-LLM so the parent's contract is mathematically guaranteed regardless
of LLM output.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import HAIKU_LITE, Agent, SchemaGuardrail
from app.agents.necessity_reasoner.schemas import (
    ConfidenceCalibratorInput,
    ConfidenceCalibratorOutput,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "necessity_reasoner" / "sub_agents" / "confidence_calibrator.txt"
)


class ConfidenceCalibratorAgent(
    Agent[ConfidenceCalibratorInput, ConfidenceCalibratorOutput]
):
    name: ClassVar[str] = "confidence_calibrator"
    parent: ClassVar[str] = "necessity_reasoner"
    role: ClassVar[str] = "confidence_aggregation"
    description: ClassVar[str] = (
        "Calibrates per-criterion confidence ∈ [0,1] and aggregates to overall "
        "(deterministic min — enforced post-LLM). Drives the HITL gate threshold."
    )

    input_schema: ClassVar[type] = ConfidenceCalibratorInput
    output_schema: ClassVar[type] = ConfidenceCalibratorOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT_PATH.read_text(encoding="utf-8")
    estimated_input_tokens: ClassVar[int] = 1200
    estimated_output_tokens: ClassVar[int] = 800
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(ConfidenceCalibratorOutput)]

    def _build_user_message(self, input: ConfidenceCalibratorInput) -> str:
        return (
            input.model_dump_json(indent=2)
            + "\n\nReminder: overall_confidence MUST equal min(per-criterion)."
        )

    def _parse_response(self, text: str) -> ConfidenceCalibratorOutput:
        out = super()._parse_response(text)
        # Enforce min-aggregation invariant deterministically
        if out.confidences:
            true_overall = min(out.confidences)
            if abs(out.overall_confidence - true_overall) > 1e-3:
                out = out.model_copy(update={"overall_confidence": round(true_overall, 4)})
        return out


confidence_calibrator = ConfidenceCalibratorAgent()
