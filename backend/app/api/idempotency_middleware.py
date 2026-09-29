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
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import db

log = structlog.get_logger()


_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", str(24 * 3600)))
_ELIGIBLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PATH_PREFIX = "/api/v1/"
_BYPASS_PATHS = frozenset({"/api/v1/auth/login", "/api/v1/auth/signup"})

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


def _bearer(headers: list[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and token:
                return token
    return None


class IdempotencyMiddleware:
    """Authenticate before replay; atomically reserve each bounded request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, path = scope.get("method", "GET").upper(), scope.get("path", "")
        headers = scope.get("headers", [])
        key = next(
            (v.decode("latin-1").strip() for k, v in headers if k.lower() == b"idempotency-key"), ""
        )
        if (
            not key
            or method not in _ELIGIBLE_METHODS
            or not path.startswith(_PATH_PREFIX)
            or path in _BYPASS_PATHS
        ):
            await self.app(scope, receive, send)
            return
        if len(key) > 255:
            await self._respond(send, 400, "idempotency_key_too_long")
            return

        # Signature checking alone is insufficient: deleted users and changed roles
        # must take effect before a cached response can disclose protected data.
        from fastapi import HTTPException, Request
        from fastapi.security import HTTPAuthorizationCredentials

        from app.auth.dependencies import get_current_user

        token = _bearer(headers)
        if token is None:
            await self._respond(send, 401, "authentication_required")
            return
        try:
            user = await get_current_user(
                Request(scope), HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            )
        except HTTPException as exc:
            await self._respond(
                send,
                exc.status_code,
                "authentication_unavailable" if exc.status_code == 503 else "invalid_session",
            )
            return
        org_id = user["organization_id"]
        # Prevent same-tenant users/roles from replaying one another's responses.
        scoped_key = hashlib.sha256(
            json.dumps([user["id"], user["role"], key]).encode()
        ).hexdigest()
        chunks: list[bytes] = []
        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 8 * 1024 * 1024:
                await self._respond(send, 413, "request_too_large")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        request_hash = hashlib.sha256(
            method.encode()
            + b"\0"
            + path.encode()
            + b"\0"
            + scope.get("query_string", b"")
            + b"\0"
            + b"".join(chunks)
        ).hexdigest()
        try:
            # Expired keys may be reused. Only the winner of this INSERT/UPDATE
            # owns the slot; losers must never execute the downstream mutation.
            reserved = await db.fetchrow(
                """INSERT INTO idempotency_keys
                   (organization_id, key, method, path, request_hash, in_flight, expires_at)
                   VALUES ($1,$2,$3,$4,$5,TRUE,NOW() + ($6 * INTERVAL '1 second'))
                   ON CONFLICT (organization_id,key) DO UPDATE SET
                     method=EXCLUDED.method,path=EXCLUDED.path,request_hash=EXCLUDED.request_hash,
                     in_flight=TRUE,expires_at=EXCLUDED.expires_at,created_at=NOW(),
                     response_status=NULL,response_body=NULL,response_headers=NULL,completed_at=NULL
                   WHERE idempotency_keys.expires_at <= NOW()
                   RETURNING key""",
                org_id,
                scoped_key,
                method,
                path,
                request_hash,
                _TTL_SECONDS,
            )
            if reserved is None:
                row = await db.fetchrow(
                    "SELECT * FROM idempotency_keys WHERE organization_id=$1 AND key=$2",
                    org_id,
                    scoped_key,
                )
                if row is None or row["in_flight"]:
                    await self._respond(send, 409, "idempotency_key_in_flight")
                    return
                if (
                    row["request_hash"] != request_hash
                    or row["method"] != method
                    or row["path"] != path
                ):
                    await self._respond(send, 409, "idempotency_key_request_mismatch")
                    return
                saved_headers = row["response_headers"] or {}
                if isinstance(saved_headers, str):
                    saved_headers = json.loads(saved_headers)
                replay_headers = [
                    (k.encode("latin-1"), str(v).encode("latin-1"))
                    for k, v in saved_headers.items()
                ]
                replay_headers.append((b"idempotency-replayed", b"true"))
                await send(
                    {
                        "type": "http.response.start",
                        "status": int(row["response_status"]),
                        "headers": replay_headers,
                    }
                )
                await send(
                    {"type": "http.response.body", "body": bytes(row["response_body"] or b"")}
                )
                return
        except Exception as exc:
            log.warning("idempotency.storage_unavailable", error_type=type(exc).__name__)
            await self._respond(send, 503, "idempotency_storage_unavailable")
            return

        captured: dict[str, Any] = {
            "status": 500,
            "headers": [],
            "body": bytearray(),
            "complete": False,
        }

        async def replay_receive() -> Message:
            return messages.pop(0) if messages else await receive()

        async def capture_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                captured["body"].extend(message.get("body", b""))
                captured["complete"] = not message.get("more_body", False)
            await send(message)

        try:
            await self.app(scope, replay_receive, capture_send)
        finally:
            # Retain an interrupted reservation until expiry: the mutation may
            # have committed before a transport failure. Never blindly rerun it.
            if captured["complete"]:
                try:
                    safe_headers = {
                        k.decode("latin-1"): v.decode("latin-1")
                        for k, v in captured["headers"]
                        if k.lower() in {b"content-type", b"location"}
                    }
                    await db.execute(
                        """UPDATE idempotency_keys SET in_flight=FALSE,response_status=$1,
                           response_body=$2,response_headers=$3::jsonb,completed_at=NOW()
                           WHERE organization_id=$4 AND key=$5 AND request_hash=$6""",
                        captured["status"],
                        bytes(captured["body"]),
                        json.dumps(safe_headers),
                        org_id,
                        scoped_key,
                        request_hash,
                    )
                except Exception as exc:
                    log.error("idempotency.persist_failed", error_type=type(exc).__name__)

    async def _respond(self, send: Send, status: int, code: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": json.dumps({"error": code}).encode()})
