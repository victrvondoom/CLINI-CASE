"""Human-review pause and resume — pure behaviour (no database)."""

from __future__ import annotations

import pytest

from app.graph.build import build_resume_graph, review_gate_node
from app.graph.state import ClinCaseState
from app.models import Decision
from app.review.human import STATUS_FOR_VERDICT, HumanReview, build_human_decision
from app.review.pause_state import (
    STATE_VERSION,
    PauseStateError,
    dump_pause_state,
    restore_pause_outputs,
)
from tests.runs.helpers import FakeResumeNodes, sample_outputs


def _state(**kw) -> ClinCaseState:
    base = {
        "case_id": "c",
        "fhir_bundle": {},
        "requested_treatment": {"name": "x"},
        "payer_id": "aetna",
    }
    return ClinCaseState(**{**base, **kw})


def _review(verdict="DENY", **kw) -> dict:
    base = {
        "verdict": verdict,
        "reviewer_id": "u1",
        "reviewer_email": "r@x.test",
        "reviewer_role": "reviewer",
    }
    return HumanReview(**{**base, **kw}).model_dump()


# ---- the gate ------------------------------------------------------------------------------
async def test_review_gate_records_why_the_run_stopped():
    low = await review_gate_node(_state(**sample_outputs()))
    assert low["paused_for_review"] is True and low["pause_kind"] == "low_confidence"
    assert "below the HITL threshold" in low["pause_reason"]
    missing = await review_gate_node(_state())
    assert missing["pause_kind"] == "missing_assessment"


# ---- durable pause state -------------------------------------------------------------------
def test_pause_state_round_trips_every_output_the_remaining_agents_need():
    out = sample_outputs()
    blob = dump_pause_state(_state(**out))
    restored = restore_pause_outputs(blob, STATE_VERSION)
    assert restored["clinical_snapshot"] == out["clinical_snapshot"]
    assert restored["policy_excerpts"] == out["policy_excerpts"]
    assert restored["necessity_assessment"] == out["necessity_assessment"]


def test_pause_state_with_missing_outputs_round_trips_as_empty():
    restored = restore_pause_outputs(dump_pause_state(_state()), STATE_VERSION)
    assert restored == {
        "clinical_snapshot": None,
        "policy_excerpts": [],
        "necessity_assessment": None,
    }


def test_unknown_version_and_corrupt_state_are_refused_not_guessed():
    blob = dump_pause_state(_state(**sample_outputs()))
    with pytest.raises(PauseStateError, match="version"):
        restore_pause_outputs(blob, STATE_VERSION + 1)
    with pytest.raises(PauseStateError, match="invalid"):
        restore_pause_outputs({**blob, "assessment": {"criteria": "nope"}}, STATE_VERSION)


# ---- the human decision --------------------------------------------------------------------
@pytest.mark.parametrize("verdict", ["APPROVE", "DENY", "REFER"])
def test_the_human_decision_is_a_valid_decision_that_cites_the_reviewer(verdict):
    d = build_human_decision(
        HumanReview.model_validate(_review(verdict, note="n", pause_kind="low_confidence"))
    )
    assert isinstance(d, Decision) and d.verdict == verdict and d.confidence == 1.0
    assert (
        d.citations[0].kind == "human_override" and d.citations[0].pointer == "reviewer_action:u1"
    )
    assert (
        "HUMAN REVIEWER OVERRIDE" in d.rationale
        and "low Necessity Reasoner confidence" in d.rationale
    )
    assert STATUS_FOR_VERDICT[verdict] in ("approved", "denied", "referred")


def test_a_verifier_pause_is_worded_as_such():
    d = build_human_decision(
        HumanReview.model_validate(_review(pause_kind="verification_disagreement"))
    )
    assert "verification disagreement" in d.rationale


# ---- the remaining graph -------------------------------------------------------------------
def _resume_graph(nodes: FakeResumeNodes):
    return build_resume_graph(
        denial_forecaster=nodes.forecaster,
        appeals_drafter=nodes.appeals,
        patient_communicator=nodes.communicator,
    )


async def test_deny_runs_forecast_then_appeal_then_patient_letter():
    nodes = FakeResumeNodes(spans=False)
    final = await _resume_graph(nodes).ainvoke(
        _state(human_review=_review("DENY"), **sample_outputs())
    )
    assert nodes.order == ["denial_forecaster", "appeals_drafter", "patient_communicator"]
    assert (
        final["decision"].verdict == "DENY"
        and final["decision"].citations[0].kind == "human_override"
    )
    assert final["appeal_draft"] is not None and final["patient_communication"] is not None


@pytest.mark.parametrize("verdict", ["APPROVE", "REFER"])
async def test_non_deny_skips_the_appeal(verdict):
    nodes = FakeResumeNodes(spans=False)
    final = await _resume_graph(nodes).ainvoke(
        _state(human_review=_review(verdict), **sample_outputs())
    )
    assert nodes.order == ["denial_forecaster", "patient_communicator"]
    assert final.get("appeal_draft") is None and final["decision"].verdict == verdict


async def test_the_resume_graph_refuses_to_run_without_a_human_decision():
    with pytest.raises(ValueError, match="human_review"):
        await _resume_graph(FakeResumeNodes(spans=False)).ainvoke(_state(**sample_outputs()))


async def test_a_failing_agent_stops_the_continuation():
    nodes = FakeResumeNodes(boom=RuntimeError("provider down"), spans=False)
    with pytest.raises(RuntimeError, match="provider down"):
        await _resume_graph(nodes).ainvoke(_state(human_review=_review(), **sample_outputs()))
    assert nodes.order == ["denial_forecaster"]


def test_the_real_resume_graph_has_the_expected_topology():
    g = build_resume_graph().get_graph()
    assert {
        "human_decision",
        "denial_forecaster",
        "appeals_drafter",
        "patient_communicator",
    } <= set(g.nodes)
    edges = {(e.source, e.target) for e in g.edges}
    assert ("__start__", "human_decision") in edges and (
        "human_decision",
        "denial_forecaster",
    ) in edges
    assert ("appeals_drafter", "patient_communicator") in edges


async def test_a_pause_without_a_run_identity_is_refused_not_silently_skipped():
    from app.review.pause_state import save_pause_state

    class _Conn:
        async def execute(self, *a):  # pragma: no cover - must not be reached
            raise AssertionError("nothing may be written without a run identity")

    with pytest.raises(PauseStateError, match="run identity"):
        await save_pause_state(_Conn(), _state(**sample_outputs()), organization_id="org")
