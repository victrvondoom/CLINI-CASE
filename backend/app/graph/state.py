"""LangGraph state schema — the typed object that flows through the 7-agent DAG.

Source of truth: PROPOSAL.md §8.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.models import (
    AppealDraft,
    ClinicalSnapshot,
    Decision,
    DenialForecast,
    NecessityAssessment,
    PatientCommunication,
    PolicyExcerpt,
)

if TYPE_CHECKING:
    from app.agents.framework import AgentContext


class ClinCaseState(BaseModel):
    """Accumulator state for the LangGraph DAG. Each agent appends its output.

    Carries `organization_id` (replaces the hardcoded "org_demo" sprinkled
    across every node) and a SINGLE shared `agent_context` (replaces the
    7 separate `new_agent_context()` calls — meaning the per-case budget
    ceiling actually means something).
    """

    # Allow the AgentContext (a non-Pydantic dataclass) to live as a private
    # runtime-only attr; it's NOT serialized into the LangGraph checkpoint.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- Input (immutable) ----------------------------------------------
    case_id: str
    organization_id: str = "org_demo"
    fhir_bundle: dict
    physician_note: str | None = None
    requested_treatment: dict  # {name, hcpcs_code, j_code, dose, frequency}
    payer_id: str

    # --- Per-case AgentContext (shared budget + trace_sink) -------------
    # Set ONCE at case entry by `_get_or_init_agent_context(state)`. Every
    # parent's node reads it instead of calling `new_agent_context()`.
    # `Any` here to avoid Pydantic forward-ref pain; runtime type is
    # `app.agents.framework.AgentContext`.
    _agent_context: Any = PrivateAttr(default=None)

    # --- Accumulated outputs (filled by each agent in sequence) --------
    clinical_snapshot: ClinicalSnapshot | None = None
    policy_excerpts: list[PolicyExcerpt] = Field(default_factory=list)
    necessity_assessment: NecessityAssessment | None = None
    decision: Decision | None = None
    denial_forecast: DenialForecast | None = None      # 6th agent — runs on every case
    appeal_draft: AppealDraft | None = None
    patient_communication: PatientCommunication | None = None  # 7th agent — terminal

    # --- Optional inputs (alternative entry points) --------------------
    external_denial_letter: str | None = None  # appeals-only flow

    # --- HITL pause flag -----------------------------------------------
    # Set true by the review_gate node when necessity confidence is below
    # the org's threshold. While true, the graph terminates before
    # decision_composer; a human reviewer must call /cases/{id}/resume to
    # supply the verdict and continue the workflow.
    paused_for_review: bool = False
    pause_reason: str | None = None

    # --- Routing / trace -----------------------------------------------
    next_route: Literal["approve_done", "refer_done", "denial_path"] | None = None
    trace_events: list[dict] = Field(default_factory=list)


def get_or_init_agent_context(state: ClinCaseState) -> AgentContext:
    """Return the shared per-case AgentContext, creating it lazily on first use.

    Every parent agent's node calls this — guaranteeing ALL parents in a single
    case share one budget tracker, one trace_sink, one trace tree. Without this,
    each parent's `new_agent_context()` would create a fresh $5 budget per
    parent and the per-case ceiling claim is fake.
    """
    from app.agents.framework import new_agent_context  # lazy: avoid circular

    if state._agent_context is None:
        state._agent_context = new_agent_context(
            case_id=state.case_id,
            organization_id=state.organization_id,
        )
    return state._agent_context
