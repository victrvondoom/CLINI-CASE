"""LangGraph node + legacy compatibility shims for policy_retriever."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from datetime import date

from app.graph.state import get_or_init_agent_context
from app.agents.policy_retriever.orchestrator import policy_retriever
from app.agents.policy_retriever.schemas import *  # noqa: F401,F403
from app.graph.state import ClinCaseState
from app.models import (  # noqa: F401
    AppealDraft, ClinicalSnapshot, Decision, NecessityAssessment, PolicyExcerpt,
)

# ----------------------------------------------------------------------------
# LangGraph node wrapper + legacy shim
# ----------------------------------------------------------------------------


async def retrieve_policies(state: ClinCaseState) -> ClinCaseState:
    """Backwards-compat shim — runs the agent and writes excerpts to state."""
    from app.graph.state import get_or_init_agent_context

    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before policy_retriever")

    ctx = get_or_init_agent_context(state)
    result = await policy_retriever.invoke(
        PolicyRetrieverInput(payer_id=state.payer_id, snapshot=state.clinical_snapshot),
        ctx=ctx,
    )
    state.policy_excerpts = result.output.excerpts
    return state


async def policy_retriever_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node."""
    out = await retrieve_policies(state)
    return {"policy_excerpts": out.policy_excerpts}


# Legacy helper still imported by tests/agents/test_policy_retriever.py
def _candidate_sections(payer_id: str, treatment_name: str) -> list[dict[str, Any]]:
    """Legacy shape — used by tests. Wraps the keyword_filter output into the
    historical {"policy": ..., "section": ...} dict shape."""
    from app.agents.policy_retriever.sub_agents.keyword_filter import _POLICIES

    treatment_lc = treatment_name.lower().strip()
    out: list[dict[str, Any]] = []
    for policy in _POLICIES:
        if policy["payer_id"] != payer_id:
            continue
        keywords = [k.lower() for k in policy.get("treatment_keywords", [])]
        if not any(kw in treatment_lc or treatment_lc in kw for kw in keywords):
            continue
        for section in policy["sections"]:
            out.append({"policy": policy, "section": section})
    return out
