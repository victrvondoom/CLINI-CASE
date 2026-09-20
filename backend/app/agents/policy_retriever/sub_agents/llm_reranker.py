"""LLMReranker — Policy Retriever sub-agent.

LLM-backed (Sonnet). Cross-encoder reranks candidate sections; fires only
when keyword_filter returns more than 5 candidates. Uses the existing
rerank prompt at `app/prompts/policy_retriever_rerank.txt`.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import (
    SONNET_REASONING,
    Agent,
    SchemaGuardrail,
)
from app.agents.policy_retriever.schemas import LLMRerankerInput, LLMRerankerOutput

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "policy_retriever" / "sub_agents" / "llm_reranker.txt"
).read_text(encoding="utf-8")


class LLMRerankerAgent(Agent[LLMRerankerInput, LLMRerankerOutput]):
    name: ClassVar[str] = "llm_reranker"
    parent: ClassVar[str] = "policy_retriever"
    role: ClassVar[str] = "relevance_rerank"
    description: ClassVar[str] = (
        "Cross-encoder LLM rerank — fires only when keyword_filter returns >5 "
        "candidates. Outputs the top-K most-relevant indices for the case."
    )

    input_schema: ClassVar[type] = LLMRerankerInput
    output_schema: ClassVar[type] = LLMRerankerOutput

    primary_model: ClassVar = SONNET_REASONING
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 1500
    estimated_output_tokens: ClassVar[int] = 200
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(LLMRerankerOutput)]

    def _build_user_message(self, input: LLMRerankerInput) -> str:
        ctx = input.clinical_context
        bio = ", ".join(
            f"{b.get('name', '?')}={b.get('value', '?')}" for b in ctx.biomarkers
        ) or "(none)"
        parts = [
            "CLINICAL_CASE:",
            f"  Diagnosis: {ctx.diagnosis_icd10} - {ctx.diagnosis_description}",
            f"  Stage: {ctx.stage or 'unknown'}",
            f"  Biomarkers: {bio}",
            f"  Performance status: ECOG {ctx.performance_status or 'unknown'}",
            f"  Requested treatment: {ctx.requested_treatment}",
            "",
            "CANDIDATE_EXCERPTS:",
        ]
        for i, c in enumerate(input.candidates):
            snippet = c.section_text[:300].replace("\n", " ")
            parts.append(
                f"  [{i}] {c.policy_title} | {c.section_heading}: {snippet}..."
            )
        parts += [
            "",
            f"Return at most {min(input.top_k, len(input.candidates))} indices, most relevant first.",
            'Output strict JSON: {"top_indices": [...]}.',
        ]
        return "\n".join(parts)


llm_reranker = LLMRerankerAgent()
