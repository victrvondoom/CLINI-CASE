"""Regressions for access-control and reviewer audit boundaries."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import jobs, llm_ping, stream
from app.api.cases import ReviewActionRequest, submit_review
from app.auth.dependencies import get_current_user
from app.db import db


@pytest.mark.asyncio
async def test_case_stream_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(stream.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/cases/case-1/stream?token=legacy-query-token")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_case_stream_hides_cross_tenant_case(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(stream.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "reviewer-1",
        "organization_id": "org-1",
        "role": "reviewer",
    }
    monkeypatch.setattr(stream.db, "fetchval", AsyncMock(return_value=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/cases/case-other/stream")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_case_owner_can_receive_stream(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(stream.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "reviewer-1",
        "organization_id": "org-1",
        "role": "reviewer",
    }
    monkeypatch.setattr(stream.db, "fetchval", AsyncMock(return_value=1))
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    queue.put_nowait({"type": "done", "case_id": "case-1"})
    monkeypatch.setattr(stream, "subscribe", lambda _case_id: queue)
    unsubscribe = Mock()
    monkeypatch.setattr(stream, "unsubscribe", unsubscribe)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/cases/case-1/stream?token=ignored-by-override")
    assert response.status_code == 200
    assert "event: done" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "router,path", [(llm_ping.router, "/llm/ping"), (jobs.router, "/jobs/queue/depth")]
)
async def test_metered_and_global_operational_routes_require_auth(router, path: str) -> None:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 401


class _Transaction(AbstractAsyncContextManager):
    def __init__(self) -> None:
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.rolled_back = exc_type is not None
        return False


class _Acquire(AbstractAsyncContextManager):
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.tx = _Transaction()

    def transaction(self) -> _Transaction:
        return self.tx

    async def fetchrow(self, _query: str, *_args: Any) -> dict[str, str]:
        return {"id": "case-1", "status": "awaiting_review"}

    async def fetchval(self, _query: str, *_args: Any) -> str:
        return "run-latest"  # latest_run_id(): the run a review action is attributed to

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append((query, args))
        return "INSERT 1"


class _Pool:
    def __init__(self, conn: _Connection) -> None:
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


@pytest.mark.asyncio
async def test_review_uses_authenticated_identity_and_one_transaction(monkeypatch) -> None:
    conn = _Connection()
    monkeypatch.setattr(db, "_pool", _Pool(conn))
    result = await submit_review(
        "case-1",
        ReviewActionRequest(
            action="override_to_approve",
            reviewer_id="forged-reviewer",
            note="reviewed",
        ),
        {"id": "real-reviewer", "organization_id": "org-1", "role": "reviewer"},
    )
    audit_args = next(args for query, args in conn.calls if "reviewer_actions" in query)
    assert audit_args[1] == "real-reviewer"
    assert audit_args[4] == "run-latest"  # attributed to the case's latest run
    assert audit_args[5].startswith("CI-")  # and to the case's stable intelligence id
    assert result["reviewer_id"] == "real-reviewer"
    assert conn.tx.rolled_back is False


@pytest.mark.asyncio
async def test_review_rolls_back_when_status_update_fails(monkeypatch) -> None:
    conn = _Connection()
    original_execute = conn.execute

    async def fail_status_update(query: str, *args: Any) -> str:
        if "UPDATE cases" in query:
            raise RuntimeError("database write failed")
        return await original_execute(query, *args)

    conn.execute = fail_status_update  # type: ignore[method-assign]
    monkeypatch.setattr(db, "_pool", _Pool(conn))

    with pytest.raises(Exception) as exc_info:
        await submit_review(
            "case-1",
            ReviewActionRequest(action="override_to_deny"),
            {"id": "reviewer-1", "organization_id": "org-1", "role": "reviewer"},
        )

    assert getattr(exc_info.value, "status_code", None) == 503
    assert conn.tx.rolled_back is True
