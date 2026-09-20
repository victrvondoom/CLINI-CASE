"""KeywordFilter — Policy Retriever sub-agent.

Deterministic. Iterates the curated 21-policy corpus and emits all
(policy, section) pairs whose payer matches and whose treatment_keywords
fuzzy-match the requested treatment name.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from app.agents.framework import Agent, AgentContext
from app.agents.policy_retriever.schemas import (
    CandidateSection,
    KeywordFilterInput,
    KeywordFilterOutput,
)

_POLICIES_PATH = Path(__file__).resolve().parents[3] / "data" / "policies.json"
_POLICIES: list[dict[str, Any]] = json.loads(
    _POLICIES_PATH.read_text(encoding="utf-8")
)["policies"]


class KeywordFilterAgent(Agent[KeywordFilterInput, KeywordFilterOutput]):
    name: ClassVar[str] = "keyword_filter"
    parent: ClassVar[str] = "policy_retriever"
    role: ClassVar[str] = "candidate_selection"
    description: ClassVar[str] = (
        "Iterates the curated 21-policy corpus and returns all (policy, section) "
        "pairs whose payer matches and whose treatment_keywords fuzzy-match the "
        "requested treatment name. Pure Python, no LLM."
    )

    input_schema: ClassVar[type] = KeywordFilterInput
    output_schema: ClassVar[type] = KeywordFilterOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: KeywordFilterInput,
        ctx: AgentContext,
    ) -> KeywordFilterOutput:
        treatment_lc = input.treatment_name.lower().strip()
        candidates: list[CandidateSection] = []
        for policy in _POLICIES:
            if policy["payer_id"] != input.payer_id:
                continue
            keywords = [k.lower() for k in policy.get("treatment_keywords", [])]
            if not any(kw in treatment_lc or treatment_lc in kw for kw in keywords):
                continue
            for section in policy["sections"]:
                candidates.append(
                    CandidateSection(
                        policy_id=policy["policy_id"],
                        payer_id=policy["payer_id"],
                        policy_title=policy["policy_title"],
                        section_heading=section["heading"],
                        section_text=section["text"],
                        source_url=policy.get("source_url"),
                        page_number=section.get("page_number"),
                    )
                )
        return KeywordFilterOutput(candidates=candidates)


keyword_filter = KeywordFilterAgent()
