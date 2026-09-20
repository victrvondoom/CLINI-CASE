"""LangGraph node + legacy compatibility shims for denial_forecaster."""
from __future__ import annotations

from typing import Any

from app.agents.denial_forecaster.orchestrator import denial_forecaster
from app.agents.denial_forecaster.schemas import *  # noqa: F401,F403
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


async def forecast_denial(state: ClinCaseState) -> ClinCaseState:

    if state.necessity_assessment is None:
        raise ValueError("necessity_assessment must be set before denial_forecaster")
    if state.clinical_snapshot is None:
        raise ValueError("clinical_snapshot must be set before denial_forecaster")
    if state.decision is None:
        raise ValueError("decision must be set before denial_forecaster")

    ctx = get_or_init_agent_context(state)
    result = await denial_forecaster.invoke(
        DenialForecasterInput(
            snapshot=state.clinical_snapshot,
            excerpts=state.policy_excerpts,
            assessment=state.necessity_assessment,
            decision=state.decision,
            payer_id=state.payer_id,
        ),
        ctx=ctx,
    )
    state.denial_forecast = result.output.forecast
    return state


async def denial_forecaster_node(state: ClinCaseState) -> dict[str, Any]:
    """LangGraph node."""
    out = await forecast_denial(state)
    return {"denial_forecast": out.denial_forecast}
