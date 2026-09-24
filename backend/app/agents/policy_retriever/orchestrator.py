"""PolicyRetriever — parent agent (2 of 7).

Orchestrator on the production framework. Composes 3 sub-agents:

  1. keyword_filter      (deterministic) — payer + treatment-keyword candidates
  2. llm_reranker        (LLM, Sonnet)   — fires only when >5 candidates
  3. citation_resolver   (deterministic) — fully-pointered PolicyExcerpts

Each emits its own row in `agent_runs` named `policy_retriever.<sub_name>`.
"""
from __future__ import annotations

from typing import Any, ClassVar

from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.agents.policy_retriever.sub_agents.citation_resolver import citation_resolver
from app.agents.policy_retriever.sub_agents.keyword_filter import keyword_filter
from app.agents.policy_retriever.sub_agents.llm_reranker import llm_reranker
from app.agents.policy_retriever.sub_agents.q_business_retriever import q_business_retriever
from app.config import settings
from app.graph.state import ClinCaseState
from app.agents.policy_retriever.schemas import (
    PolicyRetrieverInput,
    PolicyRetrieverOutput,
)
from app.agents.policy_retriever.schemas import (
    CitationResolverInput,
    KeywordFilterInput,
    LLMRerankerInput,
    RerankerClinicalContext,
)


# All four sub-agents declared. The orchestrator picks between
# `keyword_filter` (default, file-corpus) and `q_business_retriever`
# (Amazon Q Business, USE_AMAZON_Q=true) at runtime per call.
SUB_AGENTS = [keyword_filter, q_business_retriever, llm_reranker, citation_resolver]


class PolicyRetrieverAgent(Agent[PolicyRetrieverInput, PolicyRetrieverOutput]):
    name: ClassVar[str] = "policy_retriever"
    parent: ClassVar = None
    role: ClassVar[str] = "policy_retrieval_orchestration"
    description: ClassVar[str] = (
        "Fetches the top-5 payer-specific PA policy sections relevant to this case "
        "from the 22-policy corpus (Bedrock KB in production)."
    )

    input_schema: ClassVar[type] = PolicyRetrieverInput
    output_schema: ClassVar[type] = PolicyRetrieverOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(PolicyRetrieverOutput)]

    async def _execute_deterministic(
        self,
        input: PolicyRetrieverInput,
        ctx: AgentContext,
    ) -> PolicyRetrieverOutput:
        snap = input.snapshot

        # 1) Candidate selection — pick backend at call time.
        # USE_AMAZON_Q=true   -> Amazon Q Business semantic search over the
        #                        customer's M365/SharePoint/Confluence corpus
        # USE_AMAZON_Q=false  -> in-repo policies.json file-walker
        # Same input/output schema either way; the orchestrator is decoupled
        # from the backend choice.
        retriever = q_business_retriever if settings.USE_AMAZON_Q else keyword_filter
        kw_result = await retriever.invoke(
            KeywordFilterInput(
                payer_id=input.payer_id,
                treatment_name=snap.requested_treatment.name,
            ),
            ctx=ctx,
        )
        candidates = kw_result.output.candidates

        if not candidates:
            return PolicyRetrieverOutput(
                excerpts=[], n_candidates=0, reranked=False
            )

        # 2) Rerank if more than 5 candidates
        if len(candidates) > 5:
            rerank_result = await llm_reranker.invoke(
                LLMRerankerInput(
                    candidates=candidates,
                    clinical_context=RerankerClinicalContext(
                        diagnosis_icd10=snap.primary_diagnosis.icd10_code,
                        diagnosis_description=snap.primary_diagnosis.description,
                        stage=snap.primary_diagnosis.stage,
                        biomarkers=[b.model_dump() for b in snap.biomarkers],
                        performance_status=snap.performance_status,
                        requested_treatment=snap.requested_treatment.name,
                    ),
                    top_k=5,
                ),
                ctx=ctx,
            )
            ranks = [
                i for i in rerank_result.output.top_indices
                if 0 <= i < len(candidates)
            ][:5]
            reranked = True
        else:
            ranks = list(range(len(candidates)))
            reranked = False

        # 3) Citation Resolver (deterministic)
        res_result = await citation_resolver.invoke(
            CitationResolverInput(candidates=candidates, ranks=ranks),
            ctx=ctx,
        )

        return PolicyRetrieverOutput(
            excerpts=res_result.output.excerpts,
            n_candidates=len(candidates),
            reranked=reranked,
        )


policy_retriever = PolicyRetrieverAgent()



