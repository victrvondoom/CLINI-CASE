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
from langgraph.graph.state import CompiledStateGraph

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
        return "review_gate"
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
    """Flip the paused-for-review flag and stop this execution of the graph.

    No LLM call. The caller persists the pause (case status, run status and the durable pause state — see
    `app.review.pause_state`); the Reviewer queue surfaces the case; the reviewer's verdict arrives via
    POST /cases/{id}/resume, which records the human decision and queues a continuation that runs the
    remaining agents through `build_resume_graph()`.
    """
    threshold = getattr(settings, "HITL_CONFIDENCE_THRESHOLD", DEFAULT_HITL_THRESHOLD)
    overall = state.necessity_assessment.overall_confidence if state.necessity_assessment else 0.0
    return {
        "paused_for_review": True,
        "pause_kind": "low_confidence" if state.necessity_assessment else "missing_assessment",
        "pause_reason": (
            f"Necessity Reasoner overall_confidence {overall:.2f} is below the "
            f"HITL threshold {threshold:.2f}. Per CMS-0057-F § IV.C and CA SB 1120, "
            f"adverse-determination-eligible decisions require human clinician sign-off."
        ),
    }


async def verifier_node(state: ClinCaseState) -> dict[str, Any]:
    """Independently verify the composed decision; escalate to a human on disagreement/conflict."""
    from app.verification.verifier import persist, verify

    if state.decision is None:
        return {}
    v = verify(state.decision, state.necessity_assessment, state.fhir_bundle)
    try:
        await persist(
            v, case_id=state.case_id, run_id=state.run_id, ciid=state.case_intelligence_id
        )
    except Exception:  # noqa: BLE001 - the result is also returned in state; never lose the run over it
        import structlog

        structlog.get_logger().warning("verification.persist_failed", case_id=state.case_id)
    if v.pause_kind:
        return {
            "paused_for_review": True,
            "pause_kind": v.pause_kind,
            "pause_reason": "Independent verification: " + "; ".join(v.issues),
        }
    return {}


def _route_after_composer(state: ClinCaseState) -> Literal["verifier", "denial_forecaster"]:
    return "verifier" if getattr(settings, "VERIFIER_ENABLED", False) else "denial_forecaster"


def _route_after_verifier(state: ClinCaseState) -> Literal["denial_forecaster", "__end__"]:
    return "__end__" if state.paused_for_review else "denial_forecaster"


async def human_decision_node(state: ClinCaseState) -> dict[str, Any]:
    """First node of the resume graph: the reviewer's verdict becomes the Decision (no LLM, no re-derivation)."""
    from app.review.human import HumanReview, build_human_decision

    if not state.human_review:
        raise ValueError("resume graph requires state.human_review")
    return {"decision": build_human_decision(HumanReview.model_validate(state.human_review))}


def build_resume_graph(
    *,
    denial_forecaster: Any = denial_forecaster_node,
    appeals_drafter: Any = appeals_drafter_node,
    patient_communicator: Any = patient_communicator_node,
) -> CompiledStateGraph:
    """The REMAINING graph after a human review: the part of the full DAG the pause skipped.

      human_decision -> denial_forecaster --(DENY)--> appeals_drafter -> patient_communicator -> END
                                          +--(else)------------------> patient_communicator -> END

    Built from the same node functions and the same routing as the full graph. The node arguments exist so
    tests can exercise the real topology without an LLM.
    """
    g = StateGraph(ClinCaseState)
    g.add_node("human_decision", human_decision_node)
    g.add_node("denial_forecaster", denial_forecaster)
    g.add_node("appeals_drafter", appeals_drafter)
    g.add_node("patient_communicator", patient_communicator)

    g.set_entry_point("human_decision")
    g.add_edge("human_decision", "denial_forecaster")
    g.add_conditional_edges(
        "denial_forecaster",
        _route_after_forecaster,
        {"appeals_drafter": "appeals_drafter", "patient_communicator": "patient_communicator"},
    )
    g.add_edge("appeals_drafter", "patient_communicator")
    g.add_edge("patient_communicator", END)
    return g.compile()


def build_partial_graph() -> CompiledStateGraph:
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


def build_full_graph() -> CompiledStateGraph:
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

    # Decision Composer -> (optional independent verifier) -> Denial Forecaster
    g.add_node("verifier", verifier_node)
    g.add_conditional_edges(
        "decision_composer",
        _route_after_composer,
        {"verifier": "verifier", "denial_forecaster": "denial_forecaster"},
    )
    g.add_conditional_edges(
        "verifier",
        _route_after_verifier,
        {"denial_forecaster": "denial_forecaster", "__end__": END},
    )

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
