"""LangGraph node + legacy compatibility shims for decision_composer."""
from __future__ import annotations

from typing import Any

from app.agents.decision_composer.orchestrator import decision_composer
from app.agents.decision_composer.schemas import *  # noqa: F401,F403
from app.graph.state import ClinCaseState, get_or_init_agent_context
from app.models import (  # noqa: F401
    AppealDraft,
    ClinicalSnapshot,
    Decision,
    NecessityAssessment,
    PolicyExcerpt,
)

# ----------------------------------------------------------------------------
# LangGraph node wrapper + legacy shims
# ----------------------------------------------------------------------------


def derive_verdict(assessment: NecessityAssessment) -> str:
    """Pure-Python deterministic verdict rule. Mirrors verdict_synthesizer's logic.

    Inlined here (no asyncio) so the legacy synchronous callers don't disturb
    the test event-loop session. The single source of truth for the rule is
    `verdict_synthesizer._execute_deterministic`; this function MUST stay in
    lockstep with it.
    """
    a = assessment
    for c in a.criteria:
        if c.criterion_type == "inclusion" and c.status == "NOT_MET":
            return "DENY"
        if c.criterion_type == "exclusion" and c.status == "MET":
            return "DENY"
    for c in a.criteria:
        if c.status == "AMBIGUOUS":
            return "REFER"
    if a.overall_confidence < 0.75:
        return "REFER"
    return "APPROVE"


async def compose_decision(state: ClinCaseState) -> ClinCaseState:
    """Backwards-compat shim — runs the agent and writes decision to state."""

    if state.necessity_assessment is None:
        raise ValueError("necessity_assessment must be set before decision_composer")
    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before decision_composer")

    ctx = get_or_init_agent_context(state)
    result = await decision_composer.invoke(
        DecisionComposerInput(
            snapshot=state.clinical_snapshot,
            excerpts=state.policy_excerpts,
            assessment=state.necessity_assessment,
        ),
        ctx=ctx,
    )
    state.decision = result.output.decision
    return state


async def decision_composer_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node."""
    out = await compose_decision(state)
    return {"decision": out.decision}


# Legacy test shims
from pathlib import Path as _Path  # noqa: E402

from app.models import ClinicalSnapshot as _CS  # noqa: E402
from app.models import PolicyExcerpt as _PE

_PROMPT = (_Path(__file__).resolve().parents[2] / "prompts" / "decision_composer" / "orchestrator.txt").read_text(
    encoding="utf-8"
)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def _build_user_message(
    verdict: str,
    snapshot: _CS,
    excerpts: list[_PE],
    assessment: NecessityAssessment,
) -> str:
    parts = [
        f"VERDICT (use this exact value): {verdict}",
        "",
        "NECESSITY_ASSESSMENT:",
        assessment.model_dump_json(indent=2),
        "",
        "CLINICAL_SNAPSHOT:",
        snapshot.model_dump_json(indent=2),
        "",
        "POLICY_EXCERPTS:",
    ]
    for i, e in enumerate(excerpts):
        parts.append(
            f"\n--- index {i} ({e.payer_id}/{e.policy_id} | {e.policy_title} | {e.section_heading}) ---"
        )
        parts.append(e.excerpt_text)
    parts += ["", "Output the Decision JSON object now."]
    return "\n".join(parts)
