"""Tenant-context middleware — pairs the RLS migration (round 12).

Sets `SET LOCAL clincase.organization_id = '<org>'` once per request, so the
RLS policies on multi-tenant tables fire automatically. Every SELECT/UPDATE
against a tenant-scoped table from this point onward is filtered by Postgres.

Without this middleware, the RLS policies still exist but `current_setting()`
returns NULL and every query returns 0 rows — so misconfiguration fails
SAFELY (closed by default).

How it interacts with asyncpg:
  • asyncpg connections are checked out per-call from the pool.
  • `SET LOCAL` only persists to the end of the txn — perfect for a per-call
    setting since each statement is implicitly txn'd.
  • For multi-statement work, the caller wraps in `async with conn.transaction()`
    and re-issues SET LOCAL inside the txn.

Today's implementation: wraps `db.execute / fetchrow / fetch / fetchval` so
every call SETs the org_id BEFORE the user query, then runs the user query.
Implementation lives in `app/db_tenant.py` (lighter than monkey-patching).
"""
from __future__ import annotations

import contextvars
import json

from starlette.types import ASGIApp, Receive, Scope, Send

# Bound for the lifetime of a request; consumed by app.db_tenant helpers.
current_organization_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "clincase.organization_id", default=None
)


def _decode_jwt_unsafe(token: str) -> dict | None:
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _bearer(headers) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            v = value.decode("latin-1", errors="replace")
            if v.startswith("Bearer "):
                return v[7:]
    return None


class TenantContextMiddleware:
    """Bind organization_id from JWT to a contextvar for the duration of the request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _bearer(scope.get("headers", []))
        org_id: str | None = None
        if token:
            payload = _decode_jwt_unsafe(token)
            if payload:
                org_id = (
                    payload.get("org")
                    or payload.get("organization_id")
                    or payload.get("org_id")
                )
        token_marker = current_organization_id.set(org_id)
        try:
            await self.app(scope, receive, send)
        finally:
            current_organization_id.reset(token_marker)
