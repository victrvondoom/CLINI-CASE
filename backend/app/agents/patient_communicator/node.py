"""LangGraph node + legacy compatibility shims for patient_communicator."""
from __future__ import annotations

from typing import Any

from app.agents.patient_communicator.orchestrator import patient_communicator
from app.agents.patient_communicator.schemas import *  # noqa: F401,F403
from app.graph.state import ClinCaseState, get_or_init_agent_context
from app.models import (  # noqa: F401
    AppealDraft,
    ClinicalSnapshot,
    Decision,
    NecessityAssessment,
    PolicyExcerpt,
)

# ----------------------------------------------------------------------------
# LangGraph node wrapper + legacy shim
# ----------------------------------------------------------------------------


async def communicate_to_patient(state: ClinCaseState) -> ClinCaseState:

    if state.decision is None:
        raise ValueError("decision must be set before patient_communicator")
    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before patient_communicator")

    ctx = get_or_init_agent_context(state)
    result = await patient_communicator.invoke(
        PatientCommunicatorInput(
            snapshot=state.clinical_snapshot,
            decision=state.decision,
            appeal=state.appeal_draft,
            payer_id=state.payer_id,
        ),
        ctx=ctx,
    )
    state.patient_communication = result.output.communication
    return state


async def patient_communicator_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node."""
    out = await communicate_to_patient(state)
    return {"patient_communication": out.patient_communication}
