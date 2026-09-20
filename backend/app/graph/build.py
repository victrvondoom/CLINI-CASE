"""LangGraph DAG builders for ClinCase.

build_partial_graph()  - 3 agents (Day 3 carry-over): Extractor -> Retriever -> Reasoner.
build_full_graph()     - 7 agents with THREE conditional edges:
                         (a) HITL gate: after the Necessity Reasoner, if overall
                             confidence is below `HITL_CONFIDENCE_THRESHOLD`,
                             route to review_gate (terminal) instead of
                             decision_composer. Per CMS-0057-F § IV.C and state
                             AI-denial laws (CA SB 1120, TX, IL), adverse
                             determinations made under low-confidence conditions
                             must have human clinician sign-off.
                         (b) Appeal gate: after denial_forecaster, if verdict is
                             DENY, route to appeals_drafter; else skip directly
                             to patient_communicator.
                         (c) Patient Communicator runs on every successful end
                             of graph (APPROVE / DENY+appeal-drafted / REFER).

Topology:
    extractor -> retriever -> reasoner --(HITL)-> decision_composer
                                                       |
                                                       v
                                              denial_forecaster
                                                       |
                                          --(DENY?)----+----(else)---
                                          |                          |
                                          v                          v
                                     appeals_drafter --> patient_communicator
                                          |                          |
                                          +----(APPROVE/REFER path)--+
                                                       |
                                                       v
                                                      END
"""
from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents import (
    appeals_drafter_node,
    clinical_extractor_node,
    decision_composer_node,
    denial_forecaster_node,
    necessity_reasoner_node,
    patient_communicator_node,
    policy_retriever_node,
)
from app.config import settings
from app.graph.state import ClinCaseState

# Default threshold; can be overridden by an org-specific config in production.
DEFAULT_HITL_THRESHOLD = 0.75


def _route_after_reasoner(
    state: ClinCaseState,
) -> Literal["decision_composer", "review_gate"]:
    """Conditional edge — HITL gate.

    If the Necessity Reasoner's overall confidence is below the threshold, the
    graph pauses for human review. The reviewer's POST /cases/{id}/resume
    response then supplies the verdict; the rest of the graph (decision +
    appeals) runs server-side at that point.
    """
    threshold = getattr(settings, "HITL_CONFIDENCE_THRESHOLD", DEFAULT_HITL_THRESHOLD)
    if state.necessity_assessment is None:
        return "decision_composer"  # let downstream complain if it's None
    if state.necessity_assessment.overall_confidence < threshold:
        return "review_gate"
    return "decision_composer"


def _route_after_forecaster(
    state: ClinCaseState,
) -> Literal["appeals_drafter", "patient_communicator"]:
    """Conditional edge: if verdict is DENY, draft an appeal first; otherwise
    skip straight to the Patient Communicator. Per Phase-1 deck Page 3 flow.
    """
    if state.decision is None:
        return "patient_communicator"
    return "appeals_drafter" if state.decision.verdict == "DENY" else "patient_communicator"


async def review_gate_node(state: ClinCaseState) -> dict[str, Any]:
    """Terminal node that flips the paused-for-review flag and stops the graph.

    No LLM call. The Reviewer queue surfaces this case; a reviewer's verdict
    arrives via POST /cases/{id}/resume, which writes the Decision row directly
    and (if DENY) runs the Appeals Drafter out-of-graph.
    """
    threshold = getattr(settings, "HITL_CONFIDENCE_THRESHOLD", DEFAULT_HITL_THRESHOLD)
    overall = (
        state.necessity_assessment.overall_confidence
        if state.necessity_assessment
        else 0.0
    )
    return {
        "paused_for_review": True,
        "pause_reason": (
            f"Necessity Reasoner overall_confidence {overall:.2f} is below the "
            f"HITL threshold {threshold:.2f}. Per CMS-0057-F § IV.C and CA SB 1120, "
            f"adverse-determination-eligible decisions require human clinician sign-off."
        ),
    }


def build_partial_graph():
    """3-agent DAG. Used by POST /cases/{id}/run-partial."""
    g = StateGraph(ClinCaseState)
    g.add_node("clinical_extractor", clinical_extractor_node)
    g.add_node("policy_retriever", policy_retriever_node)
    g.add_node("necessity_reasoner", necessity_reasoner_node)

    g.set_entry_point("clinical_extractor")
    g.add_edge("clinical_extractor", "policy_retriever")
    g.add_edge("policy_retriever", "necessity_reasoner")
    g.add_edge("necessity_reasoner", END)

    return g.compile()


def build_full_graph():
    """Full 7-agent DAG with three conditional edges. See module docstring.

    Edges:
      extractor          -> retriever
      retriever          -> reasoner
      reasoner           --(HITL gate)--> { decision_composer | review_gate(END) }
      decision_composer  -> denial_forecaster
      denial_forecaster  --(verdict)--> { appeals_drafter | patient_communicator }
      appeals_drafter    -> patient_communicator
      patient_communicator -> END
      review_gate        -> END
    """
    g = StateGraph(ClinCaseState)
    g.add_node("clinical_extractor", clinical_extractor_node)
    g.add_node("policy_retriever", policy_retriever_node)
    g.add_node("necessity_reasoner", necessity_reasoner_node)
    g.add_node("decision_composer", decision_composer_node)
    g.add_node("denial_forecaster", denial_forecaster_node)
    g.add_node("appeals_drafter", appeals_drafter_node)
    g.add_node("patient_communicator", patient_communicator_node)
    g.add_node("review_gate", review_gate_node)

    g.set_entry_point("clinical_extractor")
    g.add_edge("clinical_extractor", "policy_retriever")
    g.add_edge("policy_retriever", "necessity_reasoner")

    # Conditional edge — HITL gate
    g.add_conditional_edges(
        "necessity_reasoner",
        _route_after_reasoner,
        {"decision_composer": "decision_composer", "review_gate": "review_gate"},
    )

    # Decision Composer always feeds the Denial Forecaster
    g.add_edge("decision_composer", "denial_forecaster")

    # Conditional edge — Denial Forecaster -> { Appeals if DENY, else Patient Communicator }
    g.add_conditional_edges(
        "denial_forecaster",
        _route_after_forecaster,
        {
            "appeals_drafter": "appeals_drafter",
            "patient_communicator": "patient_communicator",
        },
    )
    g.add_edge("appeals_drafter", "patient_communicator")
    g.add_edge("patient_communicator", END)

    # review_gate is terminal (HITL pause; resume endpoint runs the rest manually)
    g.add_edge("review_gate", END)

    return g.compile()
