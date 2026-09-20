"""Generalized Idempotency-Key middleware (Stripe-compatible).

Round-9 idempotency was endpoint-local on `POST /cases`. Round-13 generalizes
it to ALL write endpoints. Behavior matches Stripe's documented semantics
(https://stripe.com/docs/api/idempotent_requests):

  • Every POST/PUT/PATCH/DELETE under /api/v1/* is eligible.
  • If the request carries `Idempotency-Key: <opaque>`:
      - First request: execute, persist (key, response_status, response_body)
        in `idempotency_keys`, return response.
      - Subsequent request with same key (within TTL = 24h): return the
        cached response, do NOT re-execute. Add `Idempotency-Replayed: true`
        header.
  • If two requests with the same key arrive concurrently and the body
    differs: return 409 Conflict with reason "idempotency_key_in_flight" /
    "idempotency_key_request_mismatch".
  • TTL governed by `idempotency_keys.expires_at` reaper.

Idempotency is namespaced per tenant (organization_id from JWT) so
two tenants can use the same key without collision.

Pairs with: ops/architecture/IDEMPOTENCY.md
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import db

log = structlog.get_logger()


_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", str(24 * 3600)))
_ELIGIBLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PATH_PREFIX = "/api/v1/"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    organization_id   TEXT NOT NULL,
    key               TEXT NOT NULL,
    method            TEXT NOT NULL,
    path              TEXT NOT NULL,
    request_hash      TEXT NOT NULL,
    response_status   INTEGER,
    response_body     BYTEA,
    response_headers  JSONB,
    in_flight         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (organization_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys (expires_at);
"""


async def ensure_schema() -> None:
    await db.execute(_SCHEMA_SQL)


def _bearer(headers) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            v = value.decode("latin-1", errors="replace")
            if v.startswith("Bearer "):
                return v[7:]
    return None


def _decode_jwt_unsafe(token: str) -> dict | None:
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:  # noqa: BLE001
        return None


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if method not in _ELIGIBLE_METHODS or not path.startswith(_PATH_PREFIX):
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        idem_key: str | None = None
        for name, value in headers:
            if name.lower() == b"idempotency-key":
                idem_key = value.decode("latin-1", errors="replace").strip()
                break
        if not idem_key:
            await self.app(scope, receive, send)
            return

        # Resolve tenant
        token = _bearer(headers)
        org_id = "anonymous"
        if token:
            payload = _decode_jwt_unsafe(token)
            if payload:
                org_id = (
                    payload.get("org")
                    or payload.get("organization_id")
                    or payload.get("org_id")
                    or "anonymous"
                )

        # Buffer body to compute hash
        body = b""
        more_body = True
        receive_messages: list[Message] = []
        while more_body:
            message = await receive()
            receive_messages.append(message)
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
            else:
                break
        request_hash = hashlib.sha256(body).hexdigest()

        # Check existing row
        try:
            row = await db.fetchrow(
                "SELECT * FROM idempotency_keys WHERE organization_id = $1 AND key = $2",
                org_id, idem_key,
            )
        except Exception as e:  # noqa: BLE001
            # If schema isn't up yet, fail-open
            log.warning("idempotency.lookup_failed", error=str(e))
            row = None

        now = time.time()
        if row is not None:
            if row["request_hash"] != request_hash:
                await self._respond_409(send, "idempotency_key_request_mismatch", idem_key)
                return
            if row["in_flight"]:
                # Concurrent in-flight — Stripe says 409 with this code
                await self._respond_409(send, "idempotency_key_in_flight", idem_key)
                return
            # Cached response — replay it
            cached_status = int(row["response_status"] or 200)
            cached_body = bytes(row["response_body"] or b"")
            cached_headers = []
            try:
                stored_h = row["response_headers"] or {}
                if isinstance(stored_h, str):
                    stored_h = json.loads(stored_h)
                for k, v in (stored_h or {}).items():
                    cached_headers.append((k.encode(), str(v).encode()))
            except Exception:  # noqa: BLE001
                pass
            cached_headers.append((b"idempotency-replayed", b"true"))
            await send({
                "type": "http.response.start",
                "status": cached_status,
                "headers": cached_headers,
            })
            await send({"type": "http.response.body", "body": cached_body})
            return

        # Reserve the slot
        try:
            await db.execute(
                """
                INSERT INTO idempotency_keys
                    (organization_id, key, method, path, request_hash, in_flight, expires_at)
                VALUES ($1, $2, $3, $4, $5, TRUE, NOW() + ($6 || ' seconds')::INTERVAL)
                ON CONFLICT (organization_id, key) DO NOTHING
                """,
                org_id, idem_key, method, path, request_hash, str(_TTL_SECONDS),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("idempotency.reserve_failed", error=str(e))

        # Replay the buffered body to downstream + capture response
        captured: dict[str, Any] = {"status": 200, "headers": [], "body": b""}

        async def captured_receive() -> Message:
            if receive_messages:
                return receive_messages.pop(0)
            return await receive()

        async def captured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, captured_receive, captured_send)
        finally:
            # Persist the response for replay (best-effort)
            try:
                hdr_dict = {
                    k.decode("latin-1", errors="replace"):
                        v.decode("latin-1", errors="replace")
                    for k, v in captured["headers"]
                }
                await db.execute(
                    """
                    UPDATE idempotency_keys
                       SET in_flight        = FALSE,
                           response_status  = $1,
                           response_body    = $2,
                           response_headers = $3::jsonb,
                           completed_at     = NOW()
                     WHERE organization_id = $4 AND key = $5
                    """,
                    int(captured["status"]),
                    captured["body"],
                    json.dumps(hdr_dict),
                    org_id, idem_key,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("idempotency.persist_failed", error=str(e))

    async def _respond_409(self, send: Send, code: str, key: str) -> None:
        body = json.dumps({"error": code, "idempotency_key": key}).encode()
        await send({
            "type": "http.response.start",
            "status": 409,
            "headers": [
                (b"content-type", b"application/json"),
                (b"x-idempotency-error", code.encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
