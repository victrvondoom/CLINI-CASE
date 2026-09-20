"""CitationLinker — Decision Composer sub-agent.

LLM-backed (Haiku). Builds the citation chain so every factual claim in the
rationale points to either a clinical evidence resource or a policy excerpt.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.decision_composer.schemas import CitationLinkerInput, CitationLinkerOutput
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    CitationCompletenessGuardrail,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "decision_composer" / "sub_agents" / "citation_linker.txt"
).read_text(encoding="utf-8")


class CitationLinkerAgent(Agent[CitationLinkerInput, CitationLinkerOutput]):
    name: ClassVar[str] = "citation_linker"
    parent: ClassVar[str] = "decision_composer"
    role: ClassVar[str] = "citation_chain"
    description: ClassVar[str] = (
        "Builds the citation chain so every factual claim in the rationale points "
        "to either a clinical evidence resource or a policy excerpt."
    )

    input_schema: ClassVar[type] = CitationLinkerInput
    output_schema: ClassVar[type] = CitationLinkerOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 2500
    estimated_output_tokens: ClassVar[int] = 1200
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [
        SchemaGuardrail(CitationLinkerOutput),
        CitationCompletenessGuardrail(),
    ]


citation_linker = CitationLinkerAgent()
