"""Pure identity behaviour — no database."""

from __future__ import annotations

import asyncio

import pytest
from langgraph.graph import END, StateGraph

from app.agents.framework import run_registry
from app.graph.state import ClinCaseState, get_or_init_agent_context, run_identity_of, state_for_run
from app.identity import RunIdentity, case_intelligence_id, new_run_id, new_trace_id


def _identity(attempt: int = 1, **kw) -> RunIdentity:
    base = {
        "case_id": "case_1",
        "organization_id": "org_a",
        "case_intelligence_id": case_intelligence_id("org_a", "case_1"),
        "run_id": new_run_id(),
        "attempt_no": attempt,
        "trigger": "initial",
        "trace_id": new_trace_id(),
    }
    return RunIdentity(**{**base, **kw})


def test_payload_round_trip_and_legacy_is_none():
    i = _identity(parent_run_id="run_x").with_job_attempt(3)
    assert RunIdentity.from_payload(i.to_payload()) == i
    for bad in (None, {}, {"run_id": "r"}, "x", {**i.to_payload(), "attempt_no": "NaN"}):
        assert RunIdentity.from_payload(bad) is None  # a legacy/malformed payload must not raise


def test_trace_id_is_32_hex_and_run_ids_are_unique():
    assert len(new_trace_id()) == 32 and int(new_trace_id(), 16) >= 0
    assert len({new_run_id() for _ in range(500)}) == 500


def test_event_fields_carry_exactly_the_correlation_ids():
    i = _identity()
    assert set(i.event_fields()) == {"case_intelligence_id", "run_id", "trace_id"}
    assert i.baggage()["job_attempt"] == "1"


def test_state_carries_identity_and_round_trips():
    i = _identity(trigger="rerun", attempt=2, parent_run_id="run_prev").with_job_attempt(2)
    st = state_for_run(i, fhir_bundle={}, requested_treatment={}, payer_id="aetna")
    assert run_identity_of(st) == i
    assert (
        run_identity_of(
            ClinCaseState(case_id="c", fhir_bundle={}, requested_treatment={}, payer_id="p")
        )
        is None
    )


async def test_every_graph_node_shares_one_context_budget_and_identity():
    """Regression for the audit finding: LangGraph rebuilds state per node, so each parent used to get a fresh
    budget and request id. With a run identity the registry hands every node the SAME context."""
    seen = []

    async def node(state):
        ctx = get_or_init_agent_context(state)
        seen.append(ctx)
        return {"pause_reason": f"n{len(seen)}"}

    g = StateGraph(ClinCaseState)
    g.add_node("a", node)
    g.add_node("b", node)
    g.add_node("c", node)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", END)
    ident = _identity()
    try:
        await g.compile().ainvoke(
            state_for_run(ident, fhir_bundle={}, requested_treatment={}, payer_id="p")
        )
        assert len(seen) == 3
        assert seen[0] is seen[1] is seen[2]
        assert seen[0].budget is seen[2].budget and seen[0].request_id == seen[2].request_id
        assert seen[0].identity == ident and seen[0].correlation["run_id"] == ident.run_id
        assert run_registry.peek(ident) is seen[0]
    finally:
        run_registry.release(ident)
    assert run_registry.peek(ident) is None


def test_contexts_of_different_runs_and_job_attempts_never_mix():
    a, b = _identity(), _identity()
    try:
        ca, cb = run_registry.get_or_create(a), run_registry.get_or_create(b)
        assert ca is not cb and ca.budget is not cb.budget
        retry = run_registry.get_or_create(a.with_job_attempt(2))  # crash-retry of the same run
        assert retry is not ca and retry.identity.run_id == a.run_id
    finally:
        for i in (a, b, a.with_job_attempt(2)):
            run_registry.release(i)
    assert run_registry.active_count() == 0


def test_legacy_state_without_identity_still_gets_a_context():
    st = ClinCaseState(case_id="c", fhir_bundle={}, requested_treatment={}, payer_id="p")
    assert get_or_init_agent_context(st) is get_or_init_agent_context(st)
    assert run_registry.active_count() == 0


def test_child_contexts_inherit_identity():
    from app.agents.framework.types import AgentTrace, SpanKind

    ident = _identity()
    try:
        ctx = run_registry.get_or_create(ident)
        child = ctx.child_for(AgentTrace(case_id="case_1", name="x", kind=SpanKind.AGENT))
        assert child.identity == ident and child.budget is ctx.budget
    finally:
        run_registry.release(ident)


@pytest.mark.parametrize("n", [1, 25])
async def test_registry_is_task_safe(n):
    ids = [_identity() for _ in range(n)]
    try:
        ctxs = await asyncio.gather(
            *(asyncio.to_thread(run_registry.get_or_create, i) for i in ids)
        )
        assert len({id(c) for c in ctxs}) == n
    finally:
        for i in ids:
            run_registry.release(i)
