from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.jobs import queue
from app.workers import case_runner


def _row(job_id, key: str) -> dict:
    return {
        "id": job_id,
        "case_id": "case-1",
        "organization_id": "org-1",
        "idempotency_key": key,
        "job_type": "run_full",
        "status": "queued",
        "payload_json": {},
        "result_json": None,
        "error_text": None,
        "attempts": 0,
        "max_attempts": 3,
        "created_at": datetime.now(UTC),
        "claimed_at": None,
        "finished_at": None,
    }


@pytest.mark.asyncio
async def test_enqueue_recovers_atomic_idempotency_conflict(monkeypatch) -> None:
    existing = _row(uuid4(), "same-key")
    calls = 0

    async def fetchrow(query: str, *args):
        nonlocal calls
        calls += 1
        assert "ON CONFLICT" in query if calls == 1 else "SELECT" in query
        return None if calls == 1 else existing

    monkeypatch.setattr(queue.db, "fetchrow", fetchrow)
    job = await queue.enqueue(case_id="case-1", organization_id="org-1", idempotency_key="same-key")
    assert job.id == existing["id"]
    assert calls == 2


@pytest.mark.asyncio
async def test_completion_is_fenced_by_worker_and_attempt(monkeypatch) -> None:
    captured: tuple[str, tuple] | None = None

    async def execute(query: str, *args):
        nonlocal captured
        captured = (query, args)
        return "UPDATE 0"

    monkeypatch.setattr(queue.db, "execute", execute)
    job_id = uuid4()
    updated = await queue.mark_done(job_id, {"verdict": "REFER"}, worker_id="worker-new", attempt=2)
    assert updated is False
    assert captured is not None
    query, args = captured
    assert "claimed_by=$3" in query and "attempts=$4" in query
    assert args[2:] == ("worker-new", 2)


@pytest.mark.asyncio
async def test_lease_loss_cancels_expensive_handler(monkeypatch) -> None:
    cancelled = asyncio.Event()

    async def slow_handler(_job):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def lose_lease(_job, _worker_id, stop):
        stop.set()

    job = queue.Job(
        id=uuid4(),
        case_id="case-1",
        organization_id="org-1",
        job_type="run_full",
        status="running",
        payload={},
        result=None,
        error=None,
        attempts=1,
        max_attempts=3,
        created_at=datetime.now(UTC),
        claimed_at=datetime.now(UTC),
        finished_at=None,
    )
    monkeypatch.setitem(case_runner.JOB_HANDLERS, "run_full", slow_handler)
    monkeypatch.setattr(case_runner, "_heartbeat_loop", lose_lease)
    monkeypatch.setattr(case_runner, "_commit_run", AsyncMock())
    mark_error = AsyncMock(return_value=True)
    monkeypatch.setattr(case_runner.jq, "mark_error", mark_error)

    await case_runner._process_job(job, "worker-old")

    assert cancelled.is_set()
    case_runner._commit_run.assert_not_awaited()
    mark_error.assert_awaited_once()


@pytest.mark.parametrize("cancel_request", [False, True])
async def test_inline_deadline_or_cancellation_stops_model_work_and_allows_retry(
    monkeypatch, cancel_request
):
    started, stopped = asyncio.Event(), asyncio.Event()

    async def handler(_job):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def heartbeat(_job, _worker, stop):
        await stop.wait()

    job = queue._row_to_job(_row(uuid4(), "inline"))
    job.status, job.attempts, job.max_attempts = "running", 1, 1
    job.job_type = "resume_after_review"
    monkeypatch.setitem(case_runner.JOB_HANDLERS, job.job_type, handler)
    commit = AsyncMock()
    monkeypatch.setitem(case_runner.JOB_COMMITTERS, job.job_type, commit)
    monkeypatch.setattr(case_runner, "_heartbeat_loop", heartbeat)
    mark_error, settle = AsyncMock(return_value=True), AsyncMock()
    monkeypatch.setattr(queue, "mark_error", mark_error)
    monkeypatch.setattr(case_runner, "settle_runs_for_job", settle)
    monkeypatch.setattr(case_runner, "_publish_continuation_failed", AsyncMock())
    task = asyncio.create_task(
        case_runner._process_job(job, "review-inline:test", timeout_seconds=0.05)
    )
    await started.wait()
    if cancel_request:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        await task
    assert stopped.is_set()
    commit.assert_not_awaited()
    mark_error.assert_awaited_once()
    settle.assert_awaited_once_with(job.id, "failed")
