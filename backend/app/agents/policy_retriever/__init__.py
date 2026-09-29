"""policy_retriever — parent agent package."""
# node.py is imported for its side effects + legacy shims
from app.agents.policy_retriever import node as _node

# Re-export the LangGraph node and key shims
from app.agents.policy_retriever.node import (
    _candidate_sections,
    policy_retriever_node,
    retrieve_policies,
)
from app.agents.policy_retriever.orchestrator import (
    SUB_AGENTS,
    PolicyRetrieverAgent,
    policy_retriever,
)
from app.agents.policy_retriever.schemas import *  # noqa: F401,F403
from app.agents.policy_retriever.sub_agents import *  # noqa: F401,F403

__all__ = [
    "_candidate_sections",
    "policy_retriever_node",
    "retrieve_policies",
    "SUB_AGENTS",
    "PolicyRetrieverAgent",
    "policy_retriever",
    "ClinicalSnapshot",
    "PolicyExcerpt",
    "PolicyRetrieverInput",
    "PolicyRetrieverOutput",
    "KeywordFilterInput",
    "CandidateSection",
    "KeywordFilterOutput",
    "RerankerClinicalContext",
    "LLMRerankerInput",
    "LLMRerankerOutput",
    "CitationResolverInput",
    "CitationResolverOutput",
    "KeywordFilterAgent",
    "LLMRerankerAgent",
    "CitationResolverAgent",
    "QBusinessRetrieverAgent",
    "keyword_filter",
    "llm_reranker",
    "citation_resolver",
    "q_business_retriever",
]
