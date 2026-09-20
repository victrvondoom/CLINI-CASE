"""LangGraph node + legacy compatibility shims for clinical_extractor."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.clinical_extractor.orchestrator import clinical_extractor
from app.agents.clinical_extractor.schemas import *  # noqa: F401,F403
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


async def extract_clinical_snapshot(state: ClinCaseState) -> ClinCaseState:
    """Backwards-compat shim — runs the agent and writes the snapshot to state."""

    ctx = get_or_init_agent_context(state)
    result = await clinical_extractor.invoke(
        ClinicalExtractorInput(
            fhir_bundle=state.fhir_bundle,
            physician_note=state.physician_note,
            requested_treatment=state.requested_treatment,
        ),
        ctx=ctx,
    )
    state.clinical_snapshot = result.output.snapshot
    return state


async def clinical_extractor_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node — returns the dict of state updates."""
    out = await extract_clinical_snapshot(state)
    return {"clinical_snapshot": out.clinical_snapshot}


# Backwards-compat exports for existing tests
import json  # noqa: E402

SYSTEM_PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "clinical_extractor" / "orchestrator.txt"
).read_text(encoding="utf-8")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def _build_user_message(state: ClinCaseState, redacted_note: str | None = None) -> str:
    """Legacy helper — used by tests/agents/test_clinical_extractor.py."""
    note = redacted_note if redacted_note is not None else state.physician_note
    parts = [
        "FHIR_BUNDLE:",
        json.dumps(state.fhir_bundle, indent=2),
    ]
    if note:
        parts += ["", "PHYSICIAN_NOTE:", note]
    parts += [
        "",
        "REQUESTED_TREATMENT:",
        json.dumps(state.requested_treatment, indent=2),
        "",
        "Output the ClinicalSnapshot JSON object now.",
    ]
    return "\n".join(parts)
