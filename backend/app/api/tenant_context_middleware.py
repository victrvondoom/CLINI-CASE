"""Bind the verified JWT organization claim to request-local context.

The current database layer does not consume this context and PostgreSQL RLS
policies are not installed. Tenant isolation is therefore enforced by the
explicit ``organization_id`` predicates in API queries. The context variable
is reserved for tracing and a future, separately tested RLS implementation;
it must not be treated as a database security boundary today.
"""

from __future__ import annotations

import contextvars
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

# Bound for the lifetime of a request for tracing/future RLS work.
current_organization_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "clincase.organization_id", default=None
)


def _decode_jwt_unsafe(token: str) -> dict[str, Any] | None:
    """Compatibility helper; verifies signatures and expiry before using claims."""
    from app.auth.jwt_helpers import decode_access_token

    return decode_access_token(token)


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
                    payload.get("org") or payload.get("organization_id") or payload.get("org_id")
                )
        token_marker = current_organization_id.set(org_id)
        try:
            await self.app(scope, receive, send)
        finally:
            current_organization_id.reset(token_marker)
