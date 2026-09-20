"""LetterComposer — Appeals Drafter sub-agent (REFLECTION-enabled).

LLM-backed (Sonnet). Produces a ~600-word formal appeal letter (5-paragraph
structure) plus AppealArgument JSON entries for payer-API submission.
quality_threshold=0.80 because letter quality drives overturn rate.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.appeals_drafter.schemas import LetterComposerInput, LetterComposerOutput
from app.agents.framework import (
    SONNET_LONG_JSON,
    Agent,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "appeals_drafter" / "sub_agents" / "letter_composer.txt"
).read_text(encoding="utf-8")


class LetterComposerAgent(Agent[LetterComposerInput, LetterComposerOutput]):
    name: ClassVar[str] = "letter_composer"
    parent: ClassVar[str] = "appeals_drafter"
    role: ClassVar[str] = "appeal_letter_composition"
    description: ClassVar[str] = (
        "Produces a ~600-word formal appeal letter (5-paragraph structure) plus "
        "AppealArgument JSON entries for payer-API submission."
    )

    input_schema: ClassVar[type] = LetterComposerInput
    output_schema: ClassVar[type] = LetterComposerOutput

    # Round-15 (3rd iter): bumped to SONNET_LONG_JSON (max_tokens=8000).
    # Same JSON-truncation pattern as counter_evidence_finder — ~600-word
    # formal letters were exceeding the 1500-token SONNET_REASONING limit
    # mid-stream, causing Pydantic parse failures + AgentExhausted retries.
    primary_model: ClassVar = SONNET_LONG_JSON
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 4000
    estimated_output_tokens: ClassVar[int] = 5000

    quality_threshold: ClassVar[float] = 0.80
    max_iterations: ClassVar[int] = 3

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=15_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(LetterComposerOutput)]


letter_composer = LetterComposerAgent()
