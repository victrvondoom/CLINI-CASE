"""Offline regressions for public auth, liveness, and readiness boundaries."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.api import healthz, idempotency_middleware
from app.api.idempotency_middleware import IdempotencyMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/auth/signup"])
async def test_public_auth_bypasses_idempotency_authentication(path: str) -> None:
    calls = 0
    sent: list[dict] = []

    async def public_auth_app(scope, receive, send) -> None:
        nonlocal calls
        calls += 1
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = IdempotencyMiddleware(public_auth_app)

    async def receive() -> dict:
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": b"",
            "headers": [(b"idempotency-key", b"signup-attempt")],
        },
        receive,
        send,
    )

    assert calls == 1
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_idempotency_reservation_executes_once_and_persists_response(monkeypatch) -> None:
    from app.auth import dependencies

    monkeypatch.setattr(
        dependencies,
        "get_current_user",
        AsyncMock(return_value={"id": "user-1", "role": "coordinator", "organization_id": "org-1"}),
    )
    reserve = AsyncMock(return_value={"key": "reserved"})
    persist = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(idempotency_middleware.db, "fetchrow", reserve)
    monkeypatch.setattr(idempotency_middleware.db, "execute", persist)
    downstream_calls = 0
    sent: list[dict] = []

    async def app(scope, receive, send) -> None:
        nonlocal downstream_calls
        downstream_calls += 1
        request = await receive()
        assert request["body"] == b'{"case":"one"}'
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"created":true}'})

    async def receive() -> dict:
        return {"type": "http.request", "body": b'{"case":"one"}', "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    await IdempotencyMiddleware(app)(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/cases",
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer valid-token"),
                (b"idempotency-key", b"create-case-one"),
            ],
        },
        receive,
        send,
    )

    assert downstream_calls == 1
    assert sent[0]["status"] == 201
    reserve.assert_awaited_once()
    persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotency_replay_does_not_execute_mutation(monkeypatch) -> None:
    from app.auth import dependencies

    monkeypatch.setattr(
        dependencies,
        "get_current_user",
        AsyncMock(return_value={"id": "user-1", "role": "coordinator", "organization_id": "org-1"}),
    )
    body = b'{"case":"one"}'
    import hashlib

    request_hash = hashlib.sha256(b"POST\0/api/v1/cases\0\0" + body).hexdigest()
    row = {
        "in_flight": False,
        "request_hash": request_hash,
        "method": "POST",
        "path": "/api/v1/cases",
        "response_status": 201,
        "response_body": b'{"case_id":"case-1"}',
        "response_headers": {"content-type": "application/json"},
    }
    fetchrow = AsyncMock(side_effect=[None, row])
    monkeypatch.setattr(idempotency_middleware.db, "fetchrow", fetchrow)
    downstream_calls = 0
    sent: list[dict] = []

    async def app(scope, receive, send) -> None:
        nonlocal downstream_calls
        downstream_calls += 1

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    await IdempotencyMiddleware(app)(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/cases",
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer valid-token"),
                (b"idempotency-key", b"create-case-one"),
            ],
        },
        receive,
        send,
    )

    assert downstream_calls == 0
    assert sent[0]["status"] == 201
    assert (b"idempotency-replayed", b"true") in sent[0]["headers"]
    assert sent[1]["body"] == b'{"case_id":"case-1"}'


@pytest.mark.asyncio
async def test_healthz_is_process_only(monkeypatch) -> None:
    fetchval = AsyncMock(side_effect=AssertionError("liveness must not query storage"))
    monkeypatch.setattr(healthz.db, "fetchval", fetchval)

    assert await healthz.healthz() == {"status": "ok", "db": "not_checked"}
    fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_readyz_checks_required_database_tables(monkeypatch) -> None:
    fetchval = AsyncMock(return_value=1)
    monkeypatch.setattr(healthz.db, "fetchval", fetchval)

    response = await healthz.readyz()

    assert response.status_code == 200
    assert json.loads(response.body) == {"status": "ready", "database": "ok"}
    assert fetchval.await_count == 2


@pytest.mark.asyncio
async def test_readyz_fails_closed_without_exposing_database_error(monkeypatch) -> None:
    fetchval = AsyncMock(side_effect=RuntimeError("password=secret host=private"))
    monkeypatch.setattr(healthz.db, "fetchval", fetchval)

    response = await healthz.readyz()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "database": "unavailable",
    }
    assert b"secret" not in response.body
