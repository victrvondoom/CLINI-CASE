"""LangGraph node + legacy compatibility shims for Necessity Reasoner.

Isolated here so the canonical `orchestrator.py` stays focused on the agent
class itself. This file holds:
  • the LangGraph node wrapper that wires the orchestrator into the DAG
  • backwards-compat function shims used by older test fixtures
  • the legacy `_PROMPT` / `_build_user_message` / `_strip_code_fence`
    exports needed by tests written before the parent-as-package refactor

When tests stop referencing the legacy shims, this file collapses to just
the LangGraph node.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.necessity_reasoner.orchestrator import necessity_reasoner
from app.agents.necessity_reasoner.schemas import NecessityReasonerInput
from app.graph.state import ClinCaseState, get_or_init_agent_context
from app.models import ClinicalSnapshot, PolicyExcerpt

# ----------------------------------------------------------------------------
# LangGraph node wrapper (the canonical integration point with the DAG)
# ----------------------------------------------------------------------------


async def reason_necessity(state: ClinCaseState) -> ClinCaseState:
    """Run the Necessity Reasoner against an ClinCaseState; mutate the state in place."""
    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before necessity_reasoner")
    if not state.policy_excerpts:
        raise ValueError("policy_excerpts must be non-empty before necessity_reasoner")

    ctx = get_or_init_agent_context(state)
    result = await necessity_reasoner.invoke(
        NecessityReasonerInput(
            snapshot=state.clinical_snapshot,
            excerpts=state.policy_excerpts,
        ),
        ctx=ctx,
    )
    state.necessity_assessment = result.output.assessment
    return state


async def necessity_reasoner_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node — returns a dict of state updates for the graph reducer."""
    out = await reason_necessity(state)
    return {"necessity_assessment": out.necessity_assessment}


# ----------------------------------------------------------------------------
# Legacy compatibility shims (consumed by tests written pre-refactor)
# ----------------------------------------------------------------------------


_PROMPT = (
    Path(__file__).resolve().parents[2]
    / "prompts" / "necessity_reasoner" / "orchestrator.txt"
).read_text(encoding="utf-8")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def _build_user_message(snapshot: ClinicalSnapshot, excerpts: list[PolicyExcerpt]) -> str:
    parts = ["CLINICAL_SNAPSHOT:", snapshot.model_dump_json(indent=2), "", "POLICY_EXCERPTS:"]
    for i, e in enumerate(excerpts):
        parts.append(
            f"\n--- index {i} ({e.payer_id}/{e.policy_id} | {e.policy_title} | {e.section_heading}) ---"
        )
        parts.append(e.excerpt_text)
    parts += ["", "Output the NecessityAssessment JSON object now."]
    return "\n".join(parts)
