"""CitationLinker — Decision Composer sub-agent.

LLM-backed (Haiku). Builds the citation chain so every factual claim in the
rationale points to either a clinical evidence resource or a policy excerpt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from pydantic import ValidationError

from app.agents.decision_composer.schemas import CitationLinkerInput, CitationLinkerOutput
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    CitationCompletenessGuardrail,
    SchemaGuardrail,
)
from app.agents.framework.json_text import extract_json_text

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts"
    / "decision_composer"
    / "sub_agents"
    / "citation_linker.txt"
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

    def _parse_response(self, text: str) -> CitationLinkerOutput:
        try:
            return super()._parse_response(text)
        except ValidationError as exc:
            if not any(e.get("type") == "too_long" for e in exc.errors()):
                raise
        # Some models repeat citations past the schema cap: drop exact duplicates, keep the first 10.
        data = json.loads(extract_json_text(text), strict=False)
        seen: set[tuple[str, str, str]] = set()
        unique = []
        for c in data.get("citations") or []:
            key = (str(c.get("kind")), str(c.get("pointer", "")).strip(), str(c.get("text", "")).strip())
            if key not in seen:
                seen.add(key)
                unique.append(c)
        data["citations"] = unique[:10]
        return CitationLinkerOutput.model_validate(data)


citation_linker = CitationLinkerAgent()
