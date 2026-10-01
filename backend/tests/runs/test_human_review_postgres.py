"""Real HITL pause + resume against PostgreSQL: pause → persist → wait → human action → remaining graph → decision."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.api import cases as cases_api
from app.api import jobs as jobs_api
from app.db import db
from app.graph.build import build_resume_graph
from app.jobs import queue as jq
from app.review.pause_state import load_pause_state, restore_pause_outputs
from app.runs import list_runs
from app.streaming import subscribe, unsubscribe
from app.workers import case_runner
from tests.runs.helpers import FakeGraph, FakeResumeNodes, _case, _drain, _h, _isolate_queue, _org

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _wire(monkeypatch, *, resume_nodes: FakeResumeNodes | None = None, paused: bool = True):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph(paused=paused))
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph(paused=paused))
    nodes = resume_nodes or FakeResumeNodes()
    monkeypatch.setattr(
        case_runner,
        "_RESUME_GRAPH",
        build_resume_graph(
            denial_forecaster=nodes.forecaster,
            appeals_drafter=nodes.appeals,
            patient_communicator=nodes.communicator,
        ),
    )
    return nodes


async def _pause(client, a) -> tuple[str, str]:
    """Run a case through the async path until it stops at the review gate. Returns (case_id, paused_run_id)."""
    await _isolate_queue()
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    await case_runner._process_job(await jq.claim_next(worker_id="w1"), "w1")
    return cid, j["run_id"]


async def _resume(client, a, cid, verdict="DENY", note="reviewed"):
    return await client.post(
        f"/api/v1/cases/{cid}/resume",
        headers=_h(a["token"]),
        json={"verdict": verdict, "reviewer_note": note},
    )


async def _run_continuation() -> None:
    await case_runner._process_job(await jq.claim_next(worker_id="w2"), "w2")


# ---------------------------------------------------------------------------------------- pause
async def test_pause_persists_the_state_a_resume_needs_together_with_the_status(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org()
    cid, run_id = await _pause(client, a)
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "awaiting_review"
    stored = await load_pause_state(db, run_id)
    assert stored is not None and stored["pause_kind"] == "low_confidence"
    outputs = restore_pause_outputs(stored["state"], stored["version"])
    assert outputs["clinical_snapshot"].primary_diagnosis.source_resource_id == "cond-1"
    assert (
        outputs["necessity_assessment"].overall_confidence == 0.4
        and len(outputs["policy_excerpts"]) == 1
    )
    assert (await list_runs(a["org"], cid))[0]["status"] == "paused"


async def test_a_synchronous_pause_persists_state_too(client, monkeypatch):
    _wire(monkeypatch)
    a = await _org()
    cid = await _case(a["org"])
    r = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
    assert r["paused_for_review"] is True
    assert await load_pause_state(db, r["run_id"]) is not None
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "awaiting_review"


# ---------------------------------------------------------------------------------------- resume
async def test_resume_records_the_decision_durably_then_runs_the_remaining_graph(
    client, monkeypatch
):
    nodes = _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    # a human decision must not depend on the LLM being available
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: "LLM down")
    q = subscribe(cid)
    try:
        r = await _resume(client, a, cid, "DENY")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["continuation"]["queued"] is True and body["status"] == "denied"
        resume_run = body["run_id"]

        # --- committed before any agent has run ---
        dec = await db.fetchrow(
            "SELECT verdict, run_id, citations_json FROM decisions WHERE case_id=$1", cid
        )
        assert dec["verdict"] == "DENY" and dec["run_id"] == resume_run
        assert json.loads(dec["citations_json"])[0]["kind"] == "human_override"
        assert (
            await db.fetchval("SELECT action FROM reviewer_actions WHERE case_id=$1", cid)
            == "resume_with_deny"
        )
        assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "denied"
        runs = {x["run_id"]: x for x in await list_runs(a["org"], cid)}
        assert runs[paused_run]["status"] == "completed" and runs[resume_run]["status"] == "running"
        assert (
            runs[resume_run]["trigger"] == "resume"
            and runs[resume_run]["parent_run_id"] == paused_run
        )
        assert (
            nodes.order == []
            and await db.fetchval("SELECT count(*) FROM appeals WHERE case_id=$1", cid) == 0
        )
        job = await db.fetchrow(
            "SELECT job_type, status FROM case_jobs WHERE id=$1::uuid",
            body["continuation"]["job_id"],
        )
        assert (job["job_type"], job["status"]) == ("resume_after_review", "queued")

        # --- the worker runs what the pause skipped ---
        await _run_continuation()
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    assert nodes.order == ["denial_forecaster", "appeals_drafter", "patient_communicator"]
    appeal = await db.fetchrow(
        "SELECT run_id, case_intelligence_id FROM appeals WHERE case_id=$1", cid
    )
    assert appeal["run_id"] == resume_run
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "appealed"
    runs = {x["run_id"]: x for x in await list_runs(a["org"], cid)}
    assert runs[resume_run]["status"] == "completed" and runs[resume_run]["finished_at"] is not None
    agents = await db.fetch(
        "SELECT agent_name, run_id FROM agent_runs WHERE case_id=$1 AND run_id=$2", cid, resume_run
    )
    assert sorted(x["agent_name"] for x in agents) == [
        "appeals_drafter",
        "denial_forecaster",
        "patient_communicator",
    ]
    types = [e["type"] for e in events]
    assert types[0] == "hitl_resume" and types[-1] == "done" and "agent_finished" in types
    assert all(e.get("run_id") == resume_run for e in events)
    # exactly one human decision; the decided event says a human was involved
    assert await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 1
    decided = await db.fetchrow(
        "SELECT payload_json FROM event_outbox WHERE aggregate_id=$1 AND event_type LIKE '%decided%'",
        cid,
    )
    payload = (
        decided["payload_json"]
        if isinstance(decided["payload_json"], dict)
        else json.loads(decided["payload_json"])
    )
    assert payload["triggered_hitl"] is True and payload["decision_run_id"] == resume_run


async def test_an_approval_skips_the_appeal(client, monkeypatch):
    nodes = _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    assert (await _resume(client, a, cid, "APPROVE")).status_code == 200
    await _run_continuation()
    assert nodes.order == ["denial_forecaster", "patient_communicator"]
    assert await db.fetchval("SELECT count(*) FROM appeals WHERE case_id=$1", cid) == 0
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "approved"


async def test_a_case_paused_before_pause_state_existed_still_gets_its_decision(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid = await _case(a["org"], status="awaiting_review")  # legacy: no run, no stored state
    r = await _resume(client, a, cid, "APPROVE")
    assert r.status_code == 200 and r.json()["continuation"] == {
        "queued": False,
        "job_id": None,
        "reason": "no_pause_state",
    }
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "approved"
    assert [x["status"] for x in await list_runs(a["org"], cid)] == ["completed"]
    assert await db.fetchval("SELECT count(*) FROM case_jobs WHERE case_id=$1", cid) == 0


# ---------------------------------------------------------------------------------------- duplicates
async def test_a_second_review_of_a_resolved_case_is_refused_and_writes_nothing(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    assert (await _resume(client, a, cid, "DENY")).status_code == 200
    again = await _resume(client, a, cid, "APPROVE")
    assert again.status_code == 400 and "only 'awaiting_review'" in again.json()["detail"]
    assert await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 1
    assert await db.fetchval("SELECT count(*) FROM reviewer_actions WHERE case_id=$1", cid) == 1
    assert (
        await db.fetchval(
            "SELECT count(*) FROM case_jobs WHERE case_id=$1 AND job_type='resume_after_review'",
            cid,
        )
        == 1
    )
    assert len([r for r in await list_runs(a["org"], cid) if r["trigger"] == "resume"]) == 1


async def test_two_simultaneous_reviews_produce_exactly_one_decision(client, monkeypatch):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    r1, r2 = await asyncio.gather(
        _resume(client, a, cid, "DENY"), _resume(client, a, cid, "APPROVE")
    )
    assert sorted([r1.status_code, r2.status_code]) == [200, 400]
    assert await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 1
    assert (
        await db.fetchval(
            "SELECT count(*) FROM case_jobs WHERE case_id=$1 AND job_type='resume_after_review'",
            cid,
        )
        == 1
    )


async def test_a_review_note_does_not_consume_the_pause(client, monkeypatch):
    nodes = _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    note = await client.post(
        f"/api/v1/cases/{cid}/review",
        headers=_h(a["token"]),
        json={"action": "add_note", "note": "n"},
    )
    assert note.status_code == 200
    assert (
        await db.fetchval("SELECT run_id FROM reviewer_actions WHERE case_id=$1", cid) == paused_run
    )
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "awaiting_review"
    assert (await _resume(client, a, cid, "DENY")).status_code == 200  # still resumable
    await _run_continuation()
    assert nodes.order[0] == "denial_forecaster"


# ---------------------------------------------------------------------------------------- reruns
async def test_a_rerun_that_completes_supersedes_the_pause_and_makes_a_resume_invalid(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    monkeypatch.setattr(
        cases_api, "_FULL_GRAPH", FakeGraph(paused=False)
    )  # the rerun approves outright
    rerun = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
    runs = {x["run_id"]: x for x in await list_runs(a["org"], cid)}
    assert (
        runs[paused_run]["status"] == "superseded"
        and runs[rerun["run_id"]]["status"] == "completed"
    )
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "approved"
    stale = await _resume(client, a, cid, "DENY")  # review after rerun: the pause no longer exists
    assert stale.status_code == 400
    assert (
        await db.fetchval(
            "SELECT count(*) FROM case_jobs WHERE job_type='resume_after_review' AND case_id=$1",
            cid,
        )
        == 0
    )


async def test_a_rerun_that_pauses_again_is_the_one_a_review_resolves(client, monkeypatch):
    nodes = _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, first_pause = await _pause(client, a)
    rerun = (
        await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))
    ).json()  # pauses again
    runs = {x["run_id"]: x for x in await list_runs(a["org"], cid)}
    assert (
        runs[first_pause]["status"] == "superseded" and runs[rerun["run_id"]]["status"] == "paused"
    )
    body = (await _resume(client, a, cid, "DENY")).json()
    resume = next(x for x in await list_runs(a["org"], cid) if x["run_id"] == body["run_id"])
    assert (
        resume["parent_run_id"] == rerun["run_id"]
    )  # resolves the LATEST pause, not the stale one
    await _run_continuation()
    assert nodes.order == ["denial_forecaster", "appeals_drafter", "patient_communicator"]
    after = {x["run_id"]: x["status"] for x in await list_runs(a["org"], cid)}
    assert after[rerun["run_id"]] == "completed" and after[first_pause] == "superseded"


async def test_a_resume_run_never_supersedes_anything(client, monkeypatch):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    await _resume(client, a, cid, "APPROVE")
    await _run_continuation()
    assert "superseded" not in [x["status"] for x in await list_runs(a["org"], cid)]


# ---------------------------------------------------------------------------------------- failure
async def test_a_failing_continuation_never_undoes_the_human_decision(client, monkeypatch):
    nodes = _wire(monkeypatch, resume_nodes=FakeResumeNodes(boom=RuntimeError("provider down")))
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    body = (await _resume(client, a, cid, "DENY")).json()
    for expected in ("queued", "queued", "failed"):  # max_attempts = 3
        await case_runner._process_job(await jq.claim_next(worker_id="w2"), "w2")
        status = next(
            x["status"] for x in await list_runs(a["org"], cid) if x["run_id"] == body["run_id"]
        )
        assert status == expected
    assert nodes.order == ["denial_forecaster"] * 3
    # the decision, reviewer action and case status stand; nothing half-written
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "denied"
    assert await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 1
    assert await db.fetchval("SELECT count(*) FROM appeals WHERE case_id=$1", cid) == 0


async def test_a_corrupt_pause_state_is_dead_lettered_at_once_not_retried(client, monkeypatch):
    nodes = _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    await db.execute("UPDATE case_run_states SET schema_version = 99 WHERE run_id=$1", paused_run)
    body = (await _resume(client, a, cid, "DENY")).json()
    q = subscribe(cid)
    try:
        await case_runner._process_job(await jq.claim_next(worker_id="w2"), "w2")  # ONE attempt
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    run = next(x for x in await list_runs(a["org"], cid) if x["run_id"] == body["run_id"])
    assert run["status"] == "failed" and nodes.order == []  # no paid agent ran
    assert (
        await db.fetchval(
            "SELECT status FROM case_jobs WHERE id=$1::uuid", body["continuation"]["job_id"]
        )
        == "dead"
    )
    assert [e["type"] for e in events][-2:] == [
        "continuation_failed",
        "done",
    ]  # the stream does not hang
    assert (
        await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "denied"
    )  # the decision stands


async def test_a_pause_without_the_agent_outputs_records_the_decision_but_queues_nothing(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    await db.execute(
        "UPDATE case_run_states SET state_json = state_json - 'assessment' WHERE run_id=$1",
        paused_run,
    )
    r = (await _resume(client, a, cid, "DENY")).json()
    assert r["continuation"] == {
        "queued": False,
        "job_id": None,
        "reason": "incomplete_pause_state",
    }
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "denied"
    run = next(x for x in await list_runs(a["org"], cid) if x["run_id"] == r["run_id"])
    assert (
        run["status"] == "completed"
        and await db.fetchval(
            "SELECT count(*) FROM case_jobs WHERE job_type='resume_after_review' AND case_id=$1",
            cid,
        )
        == 0
    )


async def test_a_dead_lettered_continuation_can_be_retried_and_then_completes(client, monkeypatch):
    _wire(monkeypatch, resume_nodes=FakeResumeNodes(boom=RuntimeError("provider down")))
    a, b = await _org(role="reviewer"), await _org("other", role="reviewer")
    cid, _ = await _pause(client, a)
    body = (await _resume(client, a, cid, "DENY")).json()
    retry = f"/api/v1/cases/{cid}/resume/retry"
    # nothing to retry yet: the continuation is still queued
    assert (await client.post(retry, headers=_h(a["token"]))).status_code == 409
    q = subscribe(cid)
    try:
        for _ in range(3):
            await case_runner._process_job(await jq.claim_next(worker_id="w2"), "w2")
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    assert [e["type"] for e in events][-2:] == ["continuation_failed", "done"]
    assert (await client.post(retry, headers=_h(b["token"]))).status_code == 404  # another tenant

    working = FakeResumeNodes()
    monkeypatch.setattr(
        case_runner,
        "_RESUME_GRAPH",
        build_resume_graph(
            denial_forecaster=working.forecaster,
            appeals_drafter=working.appeals,
            patient_communicator=working.communicator,
        ),
    )
    r = await client.post(retry, headers=_h(a["token"]))
    assert (
        r.status_code == 200
        and r.json()["run_id"] == body["run_id"]
        and r.json()["status"] == "queued"
    )
    assert (
        await client.post(retry, headers=_h(a["token"]))
    ).status_code == 409  # already re-queued
    await _run_continuation()
    assert working.order == ["denial_forecaster", "appeals_drafter", "patient_communicator"]
    run = next(x for x in await list_runs(a["org"], cid) if x["run_id"] == body["run_id"])
    assert run["status"] == "completed" and run["finished_at"] is not None
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "appealed"
    assert (
        await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 1
    )  # decision never redone
    # attempts continue (4..) instead of restarting at 1: the retry's rows are never confused with the dead ones
    attempts = await db.fetch(
        "SELECT job_attempt, bool_or(error_text IS NOT NULL) AS failed FROM agent_runs "
        "WHERE run_id=$1 GROUP BY job_attempt ORDER BY job_attempt",
        body["run_id"],
    )
    assert [(x["job_attempt"], x["failed"]) for x in attempts] == [
        (1, True),
        (2, True),
        (3, True),
        (4, False),
    ]
    twin = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert [x["error"] for x in twin["continuation"]["agent_history"]] == [
        None,
        None,
        None,
    ]  # only the retry


async def test_a_stale_continuation_cannot_be_retried_after_a_newer_run(client, monkeypatch):
    _wire(monkeypatch, resume_nodes=FakeResumeNodes(boom=RuntimeError("down")))
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    await _resume(client, a, cid, "DENY")
    for _ in range(3):
        await case_runner._process_job(await jq.claim_next(worker_id="w2"), "w2")
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph(paused=False))
    await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))  # a newer execution
    r = await client.post(f"/api/v1/cases/{cid}/resume/retry", headers=_h(a["token"]))
    assert r.status_code == 409 and "newer run" in r.json()["detail"]


# ---------------------------------------------------------------------------------------- twin
async def test_the_twin_shows_the_human_outcome_and_the_continuation(client, monkeypatch):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, paused_run = await _pause(client, a)
    body = (await _resume(client, a, cid, "DENY")).json()
    await _run_continuation()
    twin = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert twin["headline_run_id"] == paused_run  # the execution that paused, not the resume
    assert (
        twin["outcome"]["last_verdict"] == "DENY"
        and twin["outcome"]["latest_decision_run_id"] == body["run_id"]
    )
    cont = twin["continuation"]
    assert (
        cont["run_id"] == body["run_id"]
        and cont["parent_run_id"] == paused_run
        and cont["status"] == "completed"
    )
    assert [x["agent"] for x in cont["agent_history"]] == [
        "denial_forecaster",
        "appeals_drafter",
        "patient_communicator",
    ]
    assert [s["stage"] for s in twin["trace"]["stages"]].count("human_review") == 1
    review = next(s for s in twin["trace"]["stages"] if s["stage"] == "human_review")
    assert review["status"] == "ok" and review["duration_ms"] is not None


async def test_the_twin_counts_the_appeal_drafted_by_the_continuation(client, monkeypatch):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    await _resume(client, a, cid, "DENY")
    await _run_continuation()
    twin = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert (
        twin["outcome"]["appeal_drafted"] is True
    )  # the appeal lives under the resume run, not the paused one


async def test_an_older_resume_is_not_presented_as_the_continuation_of_a_newer_execution(
    client, monkeypatch
):
    _wire(monkeypatch)
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    await _resume(client, a, cid, "APPROVE")
    await _run_continuation()
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph(paused=False))
    rerun = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
    twin = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert twin["headline_run_id"] == rerun["run_id"] and twin["continuation"] is None


async def test_concurrent_schema_bootstraps_do_not_race(client):
    from app.runs import ensure_schema

    await asyncio.gather(*(ensure_schema() for _ in range(6)))  # API + workers starting together


async def test_a_reaped_continuation_still_tells_the_stream(client, monkeypatch):
    _wire(monkeypatch)
    await _isolate_queue()
    await case_runner.sweep_dead_runs()  # the sweep is global: clear what other tests left behind
    a = await _org(role="reviewer")
    cid, _ = await _pause(client, a)
    body = (await _resume(client, a, cid, "DENY")).json()
    # the worker dies mid-attempt and the janitor dead-letters the job: no worker is left to publish anything
    await db.execute(
        "UPDATE case_jobs SET status='dead' WHERE id=$1::uuid", body["continuation"]["job_id"]
    )
    q = subscribe(cid)
    try:
        assert await case_runner.sweep_dead_runs() == 1
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    assert [e["type"] for e in events] == ["continuation_failed", "done"] and events[0][
        "run_id"
    ] == body["run_id"]
    assert await case_runner.sweep_dead_runs() == 0  # idempotent: announced once
