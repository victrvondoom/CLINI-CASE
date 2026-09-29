"""decision_composer — parent agent package."""
# node.py is imported for its side effects + legacy shims
from app.agents.decision_composer import node as _node

# Re-export the LangGraph node and key shims
from app.agents.decision_composer.node import (
    _PROMPT,
    _build_user_message,
    _strip_code_fence,
    compose_decision,
    decision_composer_node,
    derive_verdict,
)
from app.agents.decision_composer.orchestrator import (
    SUB_AGENTS,
    DecisionComposerAgent,
    decision_composer,
)
from app.agents.decision_composer.schemas import *  # noqa: F401,F403
from app.agents.decision_composer.sub_agents import *  # noqa: F401,F403

__all__ = [
    "_PROMPT",
    "_build_user_message",
    "_strip_code_fence",
    "compose_decision",
    "decision_composer_node",
    "derive_verdict",
    "SUB_AGENTS",
    "DecisionComposerAgent",
    "decision_composer",
    "Citation",
    "ClinicalSnapshot",
    "Decision",
    "NecessityAssessment",
    "PolicyExcerpt",
    "DecisionComposerInput",
    "DecisionComposerOutput",
    "VerdictSynthesizerInput",
    "VerdictDecisionTrace",
    "VerdictSynthesizerOutput",
    "RationaleWriterInput",
    "RationaleWriterOutput",
    "CitationLinkerInput",
    "CitationLinkerOutput",
    "VerdictSynthesizerAgent",
    "RationaleWriterAgent",
    "CitationLinkerAgent",
    "verdict_synthesizer",
    "rationale_writer",
    "citation_linker",
]
