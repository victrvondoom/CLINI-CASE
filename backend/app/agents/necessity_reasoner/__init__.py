"""Necessity Reasoner — parent agent #3 of 7.

Self-contained package. Public surface (drop-in / drop-out — no other
package needs to know about anything inside).

Public exports:
  • necessity_reasoner            — the parent Agent[I, O] instance
  • NecessityReasonerAgent        — the parent Agent class
  • SUB_AGENTS                    — list of 3 sub-agent instances
  • necessity_reasoner_node       — LangGraph node wrapper
  • reason_necessity              — sync helper that runs the agent against ClinCaseState
  • Schemas (NecessityReasonerInput / Output)
  • Sub-agent instances (criterion_splitter, evidence_matcher, confidence_calibrator)

Layout:
    necessity_reasoner/
    ├── __init__.py        ← you are here
    ├── README.md          ← agent-specific docs
    ├── orchestrator.py    ← NecessityReasonerAgent (the parent class)
    ├── node.py            ← LangGraph wrapper + legacy shims
    ├── schemas.py         ← orchestrator + sub-agent I/O schemas
    └── sub_agents/
        ├── criterion_splitter.py
        ├── evidence_matcher.py
        └── confidence_calibrator.py
"""
from app.agents.necessity_reasoner.node import (
    # Legacy shims — re-exported for tests written pre-refactor
    _PROMPT,
    _build_user_message,
    _strip_code_fence,
    necessity_reasoner_node,
    reason_necessity,
)
from app.agents.necessity_reasoner.orchestrator import (
    SUB_AGENTS,
    NecessityReasonerAgent,
    necessity_reasoner,
)
from app.agents.necessity_reasoner.schemas import (
    NecessityReasonerInput,
    NecessityReasonerOutput,
)
from app.agents.necessity_reasoner.sub_agents import (
    confidence_calibrator,
    criterion_splitter,
    evidence_matcher,
)

__all__ = [
    # Parent agent
    "NecessityReasonerAgent",
    "necessity_reasoner",
    # Schemas
    "NecessityReasonerInput",
    "NecessityReasonerOutput",
    # Sub-agents
    "SUB_AGENTS",
    "criterion_splitter",
    "evidence_matcher",
    "confidence_calibrator",
    # LangGraph + legacy
    "necessity_reasoner_node",
    "reason_necessity",
    "_PROMPT",
    "_build_user_message",
    "_strip_code_fence",
]
