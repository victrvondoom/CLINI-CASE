from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.jobs import queue


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
    job = await queue.enqueue(
        case_id="case-1", organization_id="org-1", idempotency_key="same-key"
    )
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
    updated = await queue.mark_done(
        job_id, {"verdict": "REFER"}, worker_id="worker-new", attempt=2
    )
    assert updated is False
    assert captured is not None
    query, args = captured
    assert "claimed_by=$3" in query and "attempts=$4" in query
    assert args[2:] == ("worker-new", 2)
