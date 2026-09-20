"""LangGraph node + legacy compatibility shims for appeals_drafter."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.agents.appeals_drafter.orchestrator import appeals_drafter
from app.agents.appeals_drafter.schemas import *  # noqa: F401,F403
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


async def draft_appeal(state: ClinCaseState, *, patient_initials: str = "JD") -> ClinCaseState:

    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before appeals_drafter")
    has_denial = (
        state.decision is not None and state.decision.verdict == "DENY"
    ) or bool(state.external_denial_letter)
    if not has_denial:
        raise ValueError(
            "appeals_drafter requires either a DENY decision or external_denial_letter"
        )
    if state.necessity_assessment is None or state.decision is None:
        raise ValueError("appeals_drafter requires necessity_assessment + decision")

    ctx = get_or_init_agent_context(state)
    result = await appeals_drafter.invoke(
        AppealsDrafterInput(
            snapshot=state.clinical_snapshot,
            excerpts=state.policy_excerpts,
            assessment=state.necessity_assessment,
            decision=state.decision,
            payer_id=state.payer_id,
            patient_initials=patient_initials,
            external_denial_letter=state.external_denial_letter,
        ),
        ctx=ctx,
    )
    state.appeal_draft = result.output.appeal
    return state


async def appeals_drafter_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node — invoked via the conditional edge after the Forecaster."""
    out = await draft_appeal(state)
    return {"appeal_draft": out.appeal_draft}


# Legacy test shims
from pathlib import Path as _Path  # noqa: E402

from app.models import (  # noqa: E402
    ClinicalSnapshot as _CS,
)
from app.models import (
    Decision as _D,
)
from app.models import (
    PolicyExcerpt as _PE,
)

_PROMPT = (_Path(__file__).resolve().parents[2] / "prompts" / "appeals_drafter" / "orchestrator.txt").read_text(
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
    snapshot: _CS,
    excerpts: list[_PE],
    decision: _D | None,
    external_denial_letter: str | None,
    payer_id: str,
    patient_initials: str,
) -> str:
    parts = [
        f"PAYER_ID: {payer_id}",
        f"PATIENT_INITIALS: {patient_initials}",
        f"TODAY: {date.today().isoformat()}",
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
    if decision is not None:
        parts += ["", "DENIAL_DECISION (ClinCase-generated):", decision.model_dump_json(indent=2)]
    if external_denial_letter:
        parts += ["", "EXTERNAL_DENIAL_LETTER:", external_denial_letter]
    parts += ["", "Output the AppealDraft JSON object now."]
    return "\n".join(parts)
