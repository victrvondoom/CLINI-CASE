"""CounterEvidenceFinder — Appeals Drafter sub-agent (REFLECTION-enabled).

LLM-backed (Sonnet). For each contested criterion, extracts payer position +
counter position + supporting evidence quotations from the snapshot.
quality_threshold=0.80 because counter-evidence accuracy directly determines
appeal-overturn probability.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.appeals_drafter.schemas import (
    CounterEvidenceFinderInput,
    CounterEvidenceFinderOutput,
)
from app.agents.framework import (
    SONNET_LONG_JSON,
    Agent,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "appeals_drafter" / "sub_agents" / "counter_evidence_finder.txt"
).read_text(encoding="utf-8")


class CounterEvidenceFinderAgent(
    Agent[CounterEvidenceFinderInput, CounterEvidenceFinderOutput]
):
    name: ClassVar[str] = "counter_evidence_finder"
    parent: ClassVar[str] = "appeals_drafter"
    role: ClassVar[str] = "counter_evidence_extraction"
    description: ClassVar[str] = (
        "For each contested criterion, extracts payer position + counter position "
        "+ supporting evidence quotations from the snapshot."
    )

    input_schema: ClassVar[type] = CounterEvidenceFinderInput
    output_schema: ClassVar[type] = CounterEvidenceFinderOutput

    # Round-15 (2nd iter): bumped to SONNET_LONG_JSON (max_tokens=8000).
    # Even at 3500 tokens, output JSON truncated at line 1 col 5831 (~1450
    # tokens of dense JSON). 8000 gives ~5x margin; the prompt also caps the
    # item count at 3 as belt-and-suspenders (see counter_evidence_finder.txt).
    primary_model: ClassVar = SONNET_LONG_JSON
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 4000
    estimated_output_tokens: ClassVar[int] = 5000

    quality_threshold: ClassVar[float] = 0.80
    max_iterations: ClassVar[int] = 3

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=15_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(CounterEvidenceFinderOutput)]


counter_evidence_finder = CounterEvidenceFinderAgent()
