"""RationaleWriter — Decision Composer sub-agent.

LLM-backed (Sonnet). Composes a 2–4 sentence executive-grade rationale
paragraph that justifies the (already-determined) verdict using snapshot
fields and policy phrases. Reflection enabled to catch hallucinations.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.decision_composer.schemas import RationaleWriterInput, RationaleWriterOutput
from app.agents.framework import (
    SONNET_REASONING,
    Agent,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "decision_composer" / "sub_agents" / "rationale_writer.txt"
).read_text(encoding="utf-8")


class RationaleWriterAgent(Agent[RationaleWriterInput, RationaleWriterOutput]):
    name: ClassVar[str] = "rationale_writer"
    parent: ClassVar[str] = "decision_composer"
    role: ClassVar[str] = "executive_rationale"
    description: ClassVar[str] = (
        "Composes a 2–4 sentence executive rationale paragraph that justifies "
        "the (already-determined) verdict using snapshot fields and policy phrases."
    )

    input_schema: ClassVar[type] = RationaleWriterInput
    output_schema: ClassVar[type] = RationaleWriterOutput

    primary_model: ClassVar = SONNET_REASONING
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 3500
    estimated_output_tokens: ClassVar[int] = 800
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(RationaleWriterOutput)]


rationale_writer = RationaleWriterAgent()
