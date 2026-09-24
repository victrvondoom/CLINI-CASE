"""OncoTwin LangGraph — nine twin agents, two conditional edges, then ClinCase.

    data_quality_agent → twin_state_agent → trajectory_intelligence_agent → temporal_intelligence_agent
      → deterioration_prediction_agent
          --(tier ≥ WATCH or simulation requested)--> simulation_agent → clinical_evidence_agent
          --(otherwise)-----------------------------------------------→ clinical_evidence_agent
      clinical_evidence_agent
          --(tier ≥ WATCH)--> clinical_context_agent → explanation_agent → END
          --(otherwise)-----------------------------→ explanation_agent → END

i.e. Event → Data Validation → Twin State Update → Feature/Trajectory Update →
Temporal Analysis → Risk Prediction → (Simulation) → Evidence → Clinical
Context → Explanation; the alert decision and the clinician HITL follow in
runtime.commit_evaluation. Every agent except the (opt-in) LLM path of the
Explanation Agent is deterministic — quantitative work is code, not prompts.

Downstream, a clinician-accepted alert is handed to the EXISTING ClinCase
7-agent graph (app/graph/build.py) as a new prior-auth case — see
app/oncotwin/handoff.py. The ClinCase graph itself is unchanged.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from app.agents.framework import InMemoryTraceSink, new_agent_context
from app.oncotwin.agents.twin_agents import (
    WM_BUNDLE,
    WM_DRIFT,
    WM_KEY,
    WM_LLM_TRACES,
    TwinAgentInput,
    clinical_context_agent,
    clinical_evidence_agent,
    data_quality_agent,
    deterioration_prediction_agent,
    explanation_agent,
    simulation_agent,
    temporal_intelligence_agent,
    trajectory_intelligence_agent,
    twin_state_agent,
)
from app.oncotwin.ml.model import DeteriorationModel, load_model
from app.oncotwin.observability import METRICS
from app.oncotwin.records import PatientRecord
from app.oncotwin.service import TwinComputation

TOPOLOGY = {
    "nodes": ["data_quality_agent", "twin_state_agent", "trajectory_intelligence_agent", "temporal_intelligence_agent",
              "deterioration_prediction_agent", "simulation_agent", "clinical_evidence_agent",
              "clinical_context_agent", "explanation_agent"],
    "edges": [
        ["data_quality_agent", "twin_state_agent"],
        ["twin_state_agent", "trajectory_intelligence_agent"],
        ["trajectory_intelligence_agent", "temporal_intelligence_agent"],
        ["temporal_intelligence_agent", "deterioration_prediction_agent"],
        ["deterioration_prediction_agent", "simulation_agent", "if tier ≥ WATCH or simulation requested"],
        ["deterioration_prediction_agent", "clinical_evidence_agent", "otherwise"],
        ["simulation_agent", "clinical_evidence_agent"],
        ["clinical_evidence_agent", "clinical_context_agent", "if tier ≥ WATCH"],
        ["clinical_evidence_agent", "explanation_agent", "otherwise"],
        ["clinical_context_agent", "explanation_agent"],
        ["explanation_agent", "END"],
    ],
    "after_graph": "alert decision (tier escalation ≥ EARLY WARNING) → clinician HITL → optional ClinCase handoff",
    "handoff": ("clinician-accepted alert → ClinCase case → existing 7-agent ClinCase graph "
                "(Clinical Extractor → Policy Retriever → Necessity Reasoner → Decision Composer → "
                "Denial Forecaster → Appeals Drafter → Patient Communicator) → HITL → audit"),
}

# In-flight runs: LangGraph state stays JSON-serialisable; heavy numpy objects
# live here, keyed by run_id, for the duration of one graph invocation.
_RUNS: dict[str, tuple[Any, TwinComputation]] = {}


class TwinGraphState(BaseModel):
    run_id: str
    patient_id: str
    organization_id: str
    as_of_day: int
    force_simulation: bool = False
    quality_summary: dict[str, Any] | None = None
    state_summary: dict[str, Any] | None = None
    trajectory_summary: dict[str, Any] | None = None
    temporal_summary: dict[str, Any] | None = None
    prediction_summary: dict[str, Any] | None = None
    simulation_summary: dict[str, Any] | None = None
    evidence_summary: dict[str, Any] | None = None
    context_summary: dict[str, Any] | None = None
    explanation_summary: dict[str, Any] | None = None


async def _invoke(agent, state: TwinGraphState) -> dict[str, Any]:
    ctx, _ = _RUNS[state.run_id]
    res = await agent.invoke(
        TwinAgentInput(patient_id=state.patient_id, organization_id=state.organization_id,
                       as_of_day=state.as_of_day, run_id=state.run_id),
        ctx=ctx,
    )
    return res.output.model_dump()


async def _quality_node(s: TwinGraphState) -> dict[str, Any]:
    return {"quality_summary": await _invoke(data_quality_agent, s)}


async def _state_node(s: TwinGraphState) -> dict[str, Any]:
    return {"state_summary": await _invoke(twin_state_agent, s)}


async def _trajectory_node(s: TwinGraphState) -> dict[str, Any]:
    return {"trajectory_summary": await _invoke(trajectory_intelligence_agent, s)}


async def _temporal_node(s: TwinGraphState) -> dict[str, Any]:
    return {"temporal_summary": await _invoke(temporal_intelligence_agent, s)}


async def _context_node(s: TwinGraphState) -> dict[str, Any]:
    return {"context_summary": await _invoke(clinical_context_agent, s)}


async def _explanation_node(s: TwinGraphState) -> dict[str, Any]:
    return {"explanation_summary": await _invoke(explanation_agent, s)}


async def _prediction_node(s: TwinGraphState) -> dict[str, Any]:
    return {"prediction_summary": await _invoke(deterioration_prediction_agent, s)}


async def _simulation_node(s: TwinGraphState) -> dict[str, Any]:
    return {"simulation_summary": await _invoke(simulation_agent, s)}


async def _evidence_node(s: TwinGraphState) -> dict[str, Any]:
    return {"evidence_summary": await _invoke(clinical_evidence_agent, s)}


_ELEVATED = ("WATCH", "EARLY WARNING", "HIGH PRIORITY")


def _route_after_prediction(s: TwinGraphState) -> Literal["simulation_agent", "clinical_evidence_agent"]:
    tier = (s.prediction_summary or {}).get("tier", "NORMAL")
    if s.force_simulation or tier in _ELEVATED:
        return "simulation_agent"
    return "clinical_evidence_agent"


def _route_after_evidence(s: TwinGraphState) -> Literal["clinical_context_agent", "explanation_agent"]:
    tier = (s.prediction_summary or {}).get("tier", "NORMAL")
    return "clinical_context_agent" if tier in _ELEVATED else "explanation_agent"


def build_twin_graph():
    g = StateGraph(TwinGraphState)
    g.add_node("data_quality_agent", _quality_node)
    g.add_node("twin_state_agent", _state_node)
    g.add_node("trajectory_intelligence_agent", _trajectory_node)
    g.add_node("temporal_intelligence_agent", _temporal_node)
    g.add_node("deterioration_prediction_agent", _prediction_node)
    g.add_node("simulation_agent", _simulation_node)
    g.add_node("clinical_evidence_agent", _evidence_node)
    g.add_node("clinical_context_agent", _context_node)
    g.add_node("explanation_agent", _explanation_node)
    g.set_entry_point("data_quality_agent")
    g.add_edge("data_quality_agent", "twin_state_agent")
    g.add_edge("twin_state_agent", "trajectory_intelligence_agent")
    g.add_edge("trajectory_intelligence_agent", "temporal_intelligence_agent")
    g.add_edge("temporal_intelligence_agent", "deterioration_prediction_agent")
    g.add_conditional_edges(
        "deterioration_prediction_agent", _route_after_prediction,
        {"simulation_agent": "simulation_agent", "clinical_evidence_agent": "clinical_evidence_agent"},
    )
    g.add_edge("simulation_agent", "clinical_evidence_agent")
    g.add_conditional_edges(
        "clinical_evidence_agent", _route_after_evidence,
        {"clinical_context_agent": "clinical_context_agent", "explanation_agent": "explanation_agent"},
    )
    g.add_edge("clinical_context_agent", "explanation_agent")
    g.add_edge("explanation_agent", END)
    return g.compile()


_GRAPH = build_twin_graph()


async def _run(record: PatientRecord, as_of_day: int, organization_id: str, history: list[dict[str, Any]],
               force_simulation: bool, model: DeteriorationModel, bundle: tuple | None, drift: dict | None,
               llm_traces: list | None) -> tuple[TwinComputation, dict[str, Any]]:
    run_id = uuid.uuid4().hex
    comp = TwinComputation(record=record, as_of_day=as_of_day, model=model, history=history)
    ctx = new_agent_context(case_id=f"oncotwin:{record.profile.patient_id}:d{as_of_day}",
                            organization_id=organization_id, trace_sink=InMemoryTraceSink())
    if bundle is None:
        # Direct callers (tests, CLI) may pass only the history: derive the per-day facts + states.
        from app.oncotwin.intel.state import build_states
        from app.oncotwin.service import compute_history_bundle
        b = compute_history_bundle(record, as_of_day, model)
        bundle = (b.snapshots, b.day_facts, build_states(record, b.snapshots, b.day_facts))
    ctx.working_memory[WM_KEY] = comp
    ctx.working_memory[WM_BUNDLE] = bundle
    ctx.working_memory[WM_DRIFT] = drift
    ctx.working_memory[WM_LLM_TRACES] = llm_traces
    _RUNS[run_id] = (ctx, comp)
    try:
        with METRICS.timed("oncotwin_twin_graph"):
            await _GRAPH.ainvoke(TwinGraphState(
                run_id=run_id, patient_id=record.profile.patient_id, organization_id=organization_id,
                as_of_day=as_of_day, force_simulation=force_simulation,
            ))
    finally:
        _RUNS.pop(run_id, None)
    trace = [{"agent": s.agent_name, "status": s.status, "latency_ms": s.latency_ms, "error": s.error}
             for s in ctx.trace_sink.spans]
    for sp in trace:
        METRICS.observe_ms("oncotwin_agent", float(sp["latency_ms"] or 0.0), agent=sp["agent"], status=sp["status"])
    return comp, {"run_id": run_id, "agent_trace": trace, "topology": "oncotwin-twin-graph-v2"}


def run_twin_graph(record: PatientRecord, as_of_day: int, organization_id: str, *,
                   history: list[dict[str, Any]], force_simulation: bool = False,
                   model: DeteriorationModel | None = None, bundle: tuple | None = None,
                   drift: dict | None = None, llm_traces: list | None = None) -> tuple[TwinComputation, dict[str, Any]]:
    """Synchronous entry point (call from a worker thread; owns its own event loop)."""
    return asyncio.run(_run(record, as_of_day, organization_id, history, force_simulation, model or load_model(),
                            bundle, drift, llm_traces))
