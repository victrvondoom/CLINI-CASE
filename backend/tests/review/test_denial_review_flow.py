"""Mandatory denial review at the synchronous/worker boundary, with no LLM or database."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api import cases as cases_api
from app.graph.build import build_resume_graph
from app.graph.state import state_for_run
from app.identity import RunIdentity
from app.jobs import queue as jq
from app.models import Decision
from app.review.human import public_run_outputs, require_denial_review
from app.review.pause_state import STATE_VERSION, dump_pause_state
from app.workers import case_runner
from tests.runs.helpers import FakeResumeNodes, sample_outputs

USER = {
    "id": "reviewer-1",
    "email": "reviewer@example.test",
    "role": "reviewer",
    "organization_id": "org",
}


def identity(trigger="initial", parent=None):
    return RunIdentity(
        case_id="case",
        organization_id="org",
        case_intelligence_id="ciid",
        run_id=f"run-{trigger}",
        trace_id="trace",
        attempt_no=1,
        trigger=trigger,
        parent_run_id=parent,
    )


async def proposed_denial():
    state = state_for_run(
        identity(),
        fhir_bundle={},
        requested_treatment={"name": "Drug"},
        payer_id="aetna",
        **sample_outputs(),
    )
    decision = Decision(
        verdict="DENY", rationale="criterion not met", citations=[], confidence=0.99, risk_flags=[]
    )
    nodes = FakeResumeNodes(spans=False)
    state = state.model_copy(update={"decision": decision})
    state = state.model_copy(update=await nodes.appeals(state))
    state = state.model_copy(update=await nodes.communicator(state))
    return state


class MemoryConnection:
    """Records transaction-scoped SQL and the durable job state needed by the real worker."""

    def __init__(self, status="awaiting_review"):
        self.status = status
        self.writes = []
        self.transactions = 0
        self.active = False
        self.job = None

    @asynccontextmanager
    async def transaction(self):
        self.transactions += 1
        self.active = True
        try:
            yield self
        finally:
            self.active = False

    @asynccontextmanager
    async def acquire(self):
        yield self

    async def fetchrow(self, sql, *args):
        if "FROM cases" in sql:
            assert args == ("case", "org")
            return {
                "id": "case",
                "status": self.status,
                "payer_id": "aetna",
                "fhir_bundle": {},
                "physician_note": "note",
                "requested_treatment_name": "Drug",
                "requested_j_code": None,
            }
        raise AssertionError(sql)

    async def execute(self, sql, *args):
        assert self.active, "clinical writes must share a transaction"
        self.writes.append((sql, args))
        if "UPDATE cases SET status = $1" in sql:
            self.status = args[0]
        elif "SET status='awaiting_review'" in sql or "SET status = 'awaiting_review'" in sql:
            self.status = "awaiting_review"
        elif "SET status='appealed'" in sql:
            self.status = "appealed"

    async def fetchval(self, sql, *args):
        assert self.active
        if "SELECT 1 FROM case_jobs" in sql:
            return 1
        self.writes.append((sql, args))
        if "INSERT INTO appeals" in sql:
            return 1
        if "UPDATE case_jobs SET status='done'" in sql:
            self.job.status = "done"
            self.job.result = json.loads(args[1])
            return self.job.id
        raise AssertionError(sql)


def wire_db(monkeypatch, conn):
    stub = SimpleNamespace(pool=conn, fetchrow=conn.fetchrow)
    monkeypatch.setattr(cases_api, "db", stub)
    monkeypatch.setattr(case_runner, "db", stub)
    for name in ("emit_case_decided", "emit_appeal_drafted"):
        monkeypatch.setattr(f"app.events.outbox.{name}", AsyncMock())
    for module in (cases_api, case_runner):
        monkeypatch.setattr(module, "publish", AsyncMock())
        monkeypatch.setattr(module, "mark_run", AsyncMock())
    monkeypatch.setattr(cases_api, "settle_execution_run", AsyncMock())
    monkeypatch.setattr(case_runner, "settle_execution_run", AsyncMock())


async def test_high_confidence_ai_deny_is_provisional_and_documents_stay_visible():
    final = require_denial_review(await proposed_denial())
    public = public_run_outputs(final)
    assert final.paused_for_review and final.pause_kind == "ai_denial"
    assert public["decision"] is None and public["provisional_decision"]["verdict"] == "DENY"
    assert public["documents_draft"] and public["human_review_required"]
    assert public["appeal_draft"]["appeal_body"] == "letter"
    assert public["patient_communication"]["body"] == "b"
    saved = dump_pause_state(final)
    assert saved["draft_outputs"] == public and saved["snapshot"] and saved["assessment"]


async def test_sync_deny_persists_only_pause_and_no_authoritative_event(monkeypatch):
    final = await proposed_denial()
    conn = MemoryConnection(status="pending")
    wire_db(monkeypatch, conn)
    monkeypatch.setattr(cases_api, "_require_llm", lambda: None)
    monkeypatch.setattr(cases_api, "consume_case_quota", AsyncMock())
    monkeypatch.setattr(cases_api, "start_run", AsyncMock(return_value=identity()))
    monkeypatch.setattr(
        cases_api, "_FULL_GRAPH", SimpleNamespace(ainvoke=AsyncMock(return_value=final))
    )
    output = await cases_api.run_full("case", USER)
    assert conn.status == "awaiting_review" and conn.transactions == 1
    assert output["decision"] is None and output["provisional_decision"]["verdict"] == "DENY"
    assert output["appeal_draft"] and output["patient_communication"]
    assert not any(
        "INSERT INTO decisions" in sql or "INSERT INTO appeals" in sql for sql, _ in conn.writes
    )
    pause = next(args for sql, args in conn.writes if "INSERT INTO case_run_states" in sql)
    assert json.loads(pause[-1])["draft_outputs"]["documents_draft"]
    from app.events.outbox import emit_case_decided

    emit_case_decided.assert_not_awaited()


def job_for(conn, job_type="run_full"):
    job = jq.Job(
        uuid4(),
        "case",
        "org",
        job_type,
        "running",
        {},
        None,
        None,
        1,
        1,
        datetime.now(UTC),
        None,
        None,
    )
    conn.job = job
    return job


async def test_worker_deny_cannot_write_decision_even_with_older_graph(monkeypatch):
    conn = MemoryConnection(status="pending")
    wire_db(monkeypatch, conn)
    job = job_for(conn)
    result = {"verdict": "DENY"}
    assert await case_runner._commit_run(job, "worker", await proposed_denial(), result)
    assert conn.status == "awaiting_review" and conn.transactions == 1
    assert result["verdict"] is None and result["decision"] is None
    assert result["documents_draft"] and result["appeal_draft"]
    assert not any(
        "INSERT INTO decisions" in sql or "INSERT INTO appeals" in sql for sql, _ in conn.writes
    )


@pytest.mark.parametrize("verdict", ["DENY", "APPROVE", "REFER"])
async def test_vercel_review_finishes_remaining_agents_in_request_without_worker(
    monkeypatch, verdict
):
    monkeypatch.setenv("VERCEL", "1")
    conn = MemoryConnection()
    wire_db(monkeypatch, conn)
    paused = require_denial_review(await proposed_denial())
    stored = {
        "state": dump_pause_state(paused),
        "version": STATE_VERSION,
        "pause_kind": "ai_denial",
        "pause_reason": paused.pause_reason,
    }
    resumed_identity = identity("resume", "run-initial")
    monkeypatch.setattr(cases_api, "paused_run_id", AsyncMock(return_value="run-initial"))
    monkeypatch.setattr(cases_api, "load_pause_state", AsyncMock(return_value=stored))
    monkeypatch.setattr(case_runner, "load_pause_state", AsyncMock(return_value=stored))
    monkeypatch.setattr(cases_api, "start_run", AsyncMock(return_value=resumed_identity))
    monkeypatch.setattr(case_runner, "_resolve_identity", AsyncMock(return_value=resumed_identity))
    monkeypatch.setattr(jq, "heartbeat", AsyncMock(return_value=True))
    nodes = FakeResumeNodes(spans=False)
    monkeypatch.setattr(
        case_runner,
        "_RESUME_GRAPH",
        build_resume_graph(
            denial_forecaster=nodes.forecaster,
            appeals_drafter=nodes.appeals,
            patient_communicator=nodes.communicator,
        ),
    )

    async def enqueue(**kwargs):
        assert conn.active and kwargs["conn"] is conn
        assert kwargs["max_attempts"] == 1
        job = job_for(conn, "resume_after_review")
        job.payload = kwargs["payload"]
        return job

    async def claim_job(job_id, *, worker_id, conn):
        assert conn.active and job_id == conn.job.id
        return conn.job

    monkeypatch.setattr(jq, "enqueue", enqueue)
    monkeypatch.setattr(jq, "claim_job", claim_job)
    monkeypatch.setattr(jq, "get_job", AsyncMock(side_effect=lambda _: conn.job))
    output = await cases_api.resume_after_review(
        "case", cases_api.ResumeRequest(verdict=verdict, reviewer_note="clinician reviewed"), USER
    )
    assert output["continuation"]["mode"] == "inline" and output["continuation"]["completed"]
    assert not output["continuation"]["queued"]
    assert output["result"]["decision"]["verdict"] == verdict
    assert not output["result"]["documents_draft"]
    assert output["result"]["patient_communication"]
    assert nodes.order == (
        ["denial_forecaster", "appeals_drafter", "patient_communicator"]
        if verdict == "DENY"
        else ["denial_forecaster", "patient_communicator"]
    )
    decisions = [args for sql, args in conn.writes if "INSERT INTO decisions" in sql]
    assert len(decisions) == 1 and decisions[0][1] == verdict
    assert json.loads(decisions[0][3])[0]["pointer"] == "reviewer_action:reviewer-1"
    assert bool(output["result"]["appeal_draft"]) == (verdict == "DENY")
    assert conn.status == {"DENY": "appealed", "APPROVE": "approved", "REFER": "referred"}[verdict]


async def test_pending_status_only_review_uses_authoritative_resume(monkeypatch):
    conn = MemoryConnection()
    wire_db(monkeypatch, conn)
    resume = AsyncMock(return_value={"status": "denied", "reviewer_id": USER["id"]})
    monkeypatch.setattr(cases_api, "resume_after_review", resume)
    result = await cases_api.submit_review(
        "case", cases_api.ReviewActionRequest(action="override_to_deny", reviewer_id="forged"), USER
    )
    assert result["old_status"] == "awaiting_review" and result["new_status"] == "denied"
    args = resume.await_args.args
    assert args[1].verdict == "DENY" and args[2] is USER


def test_inline_execution_is_specific_to_vercel_or_explicit_request(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert not cases_api._inline_continuation()
    assert cases_api._inline_continuation("inline")
    monkeypatch.setenv("VERCEL", "1")
    assert cases_api._inline_continuation()
    assert cases_api._inline_continuation(None)
    assert not cases_api._inline_continuation("worker")


@pytest.mark.parametrize("verdict", ["DENY", "APPROVE", "REFER"])
async def test_completed_review_readback_uses_only_latest_owned_job(monkeypatch, verdict):
    current = public_run_outputs(await proposed_denial())
    current.update({"decision": {"verdict": verdict}, "documents_draft": False})
    if verdict != "DENY":
        current["appeal_draft"] = None

    async def fetchrow(sql, *args):
        assert args == ("case", "org")
        if "FROM cases WHERE" in sql:
            return {
                "id": "case",
                "payer_id": "aetna",
                "patient_initials": "A.P.",
                "status": "approved" if verdict == "APPROVE" else "denied",
                "physician_note": "note",
                "requested_treatment_name": "Drug",
                "requested_j_code": None,
                "created_at": datetime.now(UTC),
            }
        assert "ORDER BY r.attempt_no DESC LIMIT 1" in sql
        assert "r.organization_id = $2" in sql and "j.organization_id = r.organization_id" in sql
        return {"run_status": "completed", "job_status": "done", "result_json": json.dumps(current)}

    monkeypatch.setattr(cases_api, "db", SimpleNamespace(fetchrow=fetchrow))
    result = await cases_api.get_case("case", USER)
    assert result["pending_review"] is None
    assert result["latest_result"]["decision"]["verdict"] == verdict
    assert bool(result["latest_result"]["appeal_draft"]) == (verdict == "DENY")


async def test_failed_latest_review_does_not_reload_previous_denial_drafts(monkeypatch):
    async def fetchrow(sql, *args):
        if "FROM cases WHERE" in sql:
            return {
                "id": "case",
                "payer_id": "aetna",
                "patient_initials": "A.P.",
                "status": "approved",
                "physician_note": None,
                "requested_treatment_name": "Drug",
                "requested_j_code": None,
                "created_at": None,
            }
        return {
            "run_status": "failed",
            "trigger": "resume",
            "job_status": "dead",
            "result_json": {"decision": {"verdict": "DENY"}},
            "lease_expired": True,
        }

    monkeypatch.setattr(cases_api, "db", SimpleNamespace(fetchrow=fetchrow))
    result = await cases_api.get_case("case", USER)
    assert result["latest_result"] is None and result["pending_review"] is None
    assert result["continuation"] == {"status": "failed", "can_retry": True}


@pytest.mark.parametrize("expired", [False, True])
async def test_inline_retry_recovers_expired_current_lease_but_preserves_live_attempt(
    monkeypatch, expired
):
    from fastapi import HTTPException

    monkeypatch.setenv("VERCEL", "1")

    class RetryConnection(MemoryConnection):
        async def fetchrow(self, sql, *args):
            if "FROM case_runs" in sql:
                return {
                    "run_id": "resume-current",
                    "status": "running",
                    "job_id": self.job.id,
                    "attempt_no": 2,
                }
            return await super().fetchrow(sql, *args)

        async def fetchval(self, sql, *args):
            assert self.active
            self.writes.append((sql, args))
            if "SELECT 1 FROM case_runs" in sql:
                return None
            if "Inline continuation lease expired" in sql:
                assert "organization_id=$3" in sql and "interval '60 seconds'" in sql
                return self.job.id if expired else None
            assert "max_attempts = attempts + $2" in sql and args[1] == 1
            assert "attempts = 0" not in sql
            return self.job.id

    conn = RetryConnection(status="denied")
    wire_db(monkeypatch, conn)
    job_for(conn, "resume_after_review")
    claim = AsyncMock(return_value=conn.job)
    monkeypatch.setattr(jq, "claim_job", claim)
    monkeypatch.setattr(jq, "get_job", AsyncMock(return_value=conn.job))

    async def process(job, worker_id, *, timeout_seconds):
        assert timeout_seconds == 240 and worker_id.startswith("review-retry-inline:")
        job.status = "done"

    monkeypatch.setattr(case_runner, "_process_job", process)
    if not expired:
        with pytest.raises(HTTPException) as caught:
            await cases_api.retry_continuation("case", USER)
        assert caught.value.status_code == 409
        claim.assert_not_awaited()
    else:
        result = await cases_api.retry_continuation("case", USER)
        assert result["status"] == "done" and result["run_id"] == "resume-current"
        claim.assert_awaited_once()
