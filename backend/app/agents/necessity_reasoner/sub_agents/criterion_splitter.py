"""CriterionSplitter — atomicizes payer criteria.

LLM-backed (Sonnet). Reads the top-N PolicyExcerpts and emits a flat list
of atomic, individually-checkable criteria with type tags + section pointers.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import (
    SONNET_MEDIUM_JSON,
    Agent,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)
from app.agents.necessity_reasoner.schemas import (
    CriterionSplitterInput,
    CriterionSplitterOutput,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "necessity_reasoner" / "sub_agents" / "criterion_splitter.txt"
)


class CriterionSplitterAgent(Agent[CriterionSplitterInput, CriterionSplitterOutput]):
    name: ClassVar[str] = "criterion_splitter"
    parent: ClassVar[str] = "necessity_reasoner"
    role: ClassVar[str] = "policy_atomization"
    description: ClassVar[str] = (
        "Splits multi-clause policy criteria into atomic, individually-checkable "
        "statements with type tags (inclusion/exclusion) and section pointers."
    )

    input_schema: ClassVar[type] = CriterionSplitterInput
    output_schema: ClassVar[type] = CriterionSplitterOutput

    # Round-15: SONNET_REASONING (3000) → SONNET_MEDIUM_JSON (4000).
    # Output is 8 atomic criteria with text + pointer + tag + source. Each
    # criterion ~150 tokens; 8 criteria + JSON envelope ≈ 1300-1600 tokens
    # (well under 4000), but reflection retry could include "previous output
    # was X, fix it" prepended to the prompt → headroom matters.
    primary_model: ClassVar = SONNET_MEDIUM_JSON
    system_prompt: ClassVar[str] = _PROMPT_PATH.read_text(encoding="utf-8")
    estimated_input_tokens: ClassVar[int] = 3000
    estimated_output_tokens: ClassVar[int] = 2500
    max_iterations: ClassVar[int] = 3

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=12_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(CriterionSplitterOutput)]


criterion_splitter = CriterionSplitterAgent()
