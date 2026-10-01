"""LangGraph state schema — the typed object that flows through the 7-agent DAG.

Source of truth: PROPOSAL.md §8.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.identity import RunIdentity
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
    fhir_bundle: dict[str, Any]
    physician_note: str | None = None
    requested_treatment: dict[str, Any]  # {name, hcpcs_code, j_code, dose, frequency}
    payer_id: str

    # --- Run identity (propagated into every agent, model call, row and SSE event of this execution) ---
    case_intelligence_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    job_attempt: int = 1
    attempt_no: int | None = None
    run_trigger: str | None = None
    parent_run_id: str | None = None

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
    denial_forecast: DenialForecast | None = None  # 6th agent — runs on every case
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
    # Why the run stopped: low_confidence | missing_assessment today; verification_disagreement and
    # evidence_conflict are reserved for the verifier / evidence checks (see app/review/human.py PAUSE_KINDS).
    pause_kind: str | None = None

    # --- Human review continuation ---------------------------------------
    # Set only on a resume run: the reviewer's decision (app.review.human.HumanReview as a dict). The
    # `human_decision` node turns it into the Decision and the remaining agents run from there.
    human_review: dict[str, Any] | None = None

    # --- Routing / trace -----------------------------------------------
    next_route: Literal["approve_done", "refer_done", "denial_path"] | None = None
    trace_events: list[dict[str, Any]] = Field(default_factory=list)


def run_identity_of(state: ClinCaseState) -> RunIdentity | None:
    """The identity carried by the state (None for legacy callers that never started a run)."""
    if not (state.run_id and state.case_intelligence_id and state.trace_id):
        return None
    return RunIdentity(
        case_id=state.case_id,
        organization_id=state.organization_id,
        case_intelligence_id=state.case_intelligence_id,
        run_id=state.run_id,
        attempt_no=state.attempt_no or 1,
        trigger=state.run_trigger or "initial",
        trace_id=state.trace_id,
        job_attempt=state.job_attempt,
        parent_run_id=state.parent_run_id,
    )


def state_for_run(identity: RunIdentity, **inputs: Any) -> ClinCaseState:
    """Build the initial graph state for a run: inputs plus the run identity."""
    return ClinCaseState(
        case_id=identity.case_id,
        organization_id=identity.organization_id,
        case_intelligence_id=identity.case_intelligence_id,
        run_id=identity.run_id,
        trace_id=identity.trace_id,
        job_attempt=identity.job_attempt,
        attempt_no=identity.attempt_no,
        run_trigger=identity.trigger,
        parent_run_id=identity.parent_run_id,
        **inputs,
    )


def get_or_init_agent_context(state: ClinCaseState) -> AgentContext:
    """Return the shared per-run AgentContext.

    LangGraph rebuilds the state for every node, so the context can NOT live on the state instance (it used
    to, and each parent silently got a fresh $5 budget and request id). When the state carries a run identity
    the context comes from the per-run registry — one budget, one trace sink and one identity for every node
    of the run. States without an identity (legacy callers, unit tests) keep the old lazy per-state context.
    """
    from app.agents.framework import new_agent_context  # lazy: avoid circular
    from app.agents.framework.run_registry import get_or_create

    identity = run_identity_of(state)
    if identity is not None:
        ctx: AgentContext = get_or_create(identity)
        return ctx
    if state._agent_context is None:
        state._agent_context = new_agent_context(
            case_id=state.case_id,
            organization_id=state.organization_id,
        )
    ctx = state._agent_context
    return ctx
