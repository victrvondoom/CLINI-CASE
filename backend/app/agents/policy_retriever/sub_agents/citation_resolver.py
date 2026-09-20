"""CitationResolver — Policy Retriever sub-agent.

Deterministic. Maps the ranks from LLMReranker (or a default 0..N
pass-through when no rerank fired) onto the candidate list and produces
fully-pointered PolicyExcerpt objects with relevance scores.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.framework import Agent, AgentContext
from app.agents.policy_retriever.schemas import (
    CitationResolverInput,
    CitationResolverOutput,
)
from app.models import PolicyExcerpt


class CitationResolverAgent(Agent[CitationResolverInput, CitationResolverOutput]):
    name: ClassVar[str] = "citation_resolver"
    parent: ClassVar[str] = "policy_retriever"
    role: ClassVar[str] = "citation_pointer_resolution"
    description: ClassVar[str] = (
        "Deterministic mapping from ranked candidate indices to fully-pointered "
        "PolicyExcerpt objects (source URL, page number, section heading, "
        "decreasing relevance score). No LLM."
    )

    input_schema: ClassVar[type] = CitationResolverInput
    output_schema: ClassVar[type] = CitationResolverOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: CitationResolverInput,
        ctx: AgentContext,
    ) -> CitationResolverOutput:
        excerpts: list[PolicyExcerpt] = []
        for rank_position, idx in enumerate(input.ranks):
            if idx < 0 or idx >= len(input.candidates):
                continue
            c = input.candidates[idx]
            score = round(1.0 - rank_position * 0.1, 3)
            excerpts.append(
                PolicyExcerpt(
                    payer_id=c.payer_id,
                    policy_id=c.policy_id,
                    policy_title=c.policy_title,
                    section_heading=c.section_heading,
                    excerpt_text=c.section_text,
                    source_url=c.source_url,
                    page_number=c.page_number,
                    relevance_score=max(score, 0.1),
                )
            )
        return CitationResolverOutput(excerpts=excerpts)


citation_resolver = CitationResolverAgent()
