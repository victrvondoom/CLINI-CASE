"""QBusinessRetriever — Policy Retriever sub-agent (alternative backend).

Drop-in replacement for `keyword_filter` when `USE_AMAZON_Q=true`. Same
input/output schemas, so the orchestrator picks between them transparently.

Why both exist:
  • `keyword_filter`         — static `policies.json` corpus; fast, deterministic,
                                ideal for development + offline demo
  • `q_business_retriever`   — Amazon Q Business semantic search over a
                                customer's existing M365/SharePoint/Confluence
                                policy library; production-realistic for a
                                Cognizant TriZetto customer who already runs
                                Q Business

ClinCase's policy_retriever orchestrator routes between them based on
`settings.USE_AMAZON_Q`. From the rest of the DAG's perspective the swap is
invisible — both produce the same `KeywordFilterOutput` shape.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.framework import Agent, AgentContext
from app.agents.policy_retriever.schemas import (
    CandidateSection,
    KeywordFilterInput,
    KeywordFilterOutput,
)
from app.integrations.amazon_q import AmazonQClient


class QBusinessRetrieverAgent(Agent[KeywordFilterInput, KeywordFilterOutput]):
    name: ClassVar[str] = "q_business_retriever"
    parent: ClassVar[str] = "policy_retriever"
    role: ClassVar[str] = "candidate_selection"
    description: ClassVar[str] = (
        "Amazon Q Business semantic-search backend for policy candidate selection. "
        "Same input/output as keyword_filter; engaged when USE_AMAZON_Q=true. "
        "Surfaces ranked passages from the customer's existing M365 / SharePoint / "
        "Confluence policy library — no separate vector index required."
    )

    input_schema: ClassVar[type] = KeywordFilterInput
    output_schema: ClassVar[type] = KeywordFilterOutput

    # Pure-Python orchestration of an external retrieval API; no LLM call here.
    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    # Q Business has its own response cache; per-agent cache off here so we
    # don't double-cache.
    cache_enabled: ClassVar[bool] = False

    async def _execute_deterministic(
        self,
        input: KeywordFilterInput,
        ctx: AgentContext,
    ) -> KeywordFilterOutput:
        client = AmazonQClient()
        snippets = await client.retrieve(
            query=(
                f"Prior authorization criteria for {input.treatment_name} "
                f"under {input.payer_id} oncology medical policy"
            ),
            top_k=8,
            payer_id=input.payer_id,
        )

        candidates: list[CandidateSection] = []
        for s in snippets:
            md = s.metadata or {}
            candidates.append(
                CandidateSection(
                    policy_id=str(md.get("policy_id") or "Q-RETRIEVED"),
                    policy_title=str(s.title or "Untitled"),
                    section_heading=str(md.get("section_heading") or "Coverage Criteria"),
                    section_text=s.text,
                    page_number=int(md.get("page_number") or 1),
                    source_url=s.source_uri,
                    payer_id=str(md.get("payer_id") or input.payer_id),
                )
            )
        return KeywordFilterOutput(candidates=candidates)


q_business_retriever = QBusinessRetrieverAgent()
