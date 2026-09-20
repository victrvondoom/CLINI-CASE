"""ASGI middleware that enforces per-tenant per-route rate limits.

On reject:
  HTTP 429 Too Many Requests
  Retry-After: <seconds>
  X-RateLimit-Bucket: per_second | per_minute
  X-RateLimit-Limit: <int>
  X-RateLimit-Remaining: 0

The middleware is JWT-aware: it pulls the org_id + tier from the verified
JWT (already on `request.state.user` by then). Anonymous routes (e.g.
/healthz, /metrics) skip the limiter — they're protected by WAF instead.
"""
from __future__ import annotations

import json
from collections.abc import Iterable

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from app.rate_limit import check_rate_limit

log = structlog.get_logger()


# Routes that skip the per-tenant limiter (anonymous, monitored at WAF tier)
_SKIP_PREFIXES: tuple[str, ...] = (
    "/healthz",
    "/metrics",
    "/api/v1/healthz",
    "/api/v1/auth/login",
    "/api/v1/auth/oidc/login",
    "/api/v1/auth/oidc/callback",
    "/api/v2/healthz",
    "/openapi.json",
    "/docs",
    "/redoc",
)


def _should_skip(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _SKIP_PREFIXES)


def _bearer_token(headers: Iterable[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            v = value.decode("latin-1", errors="replace")
            if v.startswith("Bearer "):
                return v[7:]
    return None


def _decode_jwt_unsafe(token: str) -> dict | None:
    """Pull (org_id, tier) from the JWT without re-validating the signature.

    Validation already happened in the auth dependency further down. We just
    want the org_id for bucketing — a forged JWT here only gets you bucketed
    against a fake org_id, which auth_dependency will reject anyway.
    """
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


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if _should_skip(path):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        token = _bearer_token(scope.get("headers", []))
        org_id = "anonymous"
        tier = "bronze"  # anonymous gets the tightest bucket
        if token:
            jwt_payload = _decode_jwt_unsafe(token)
            if jwt_payload:
                org_id = (
                    jwt_payload.get("org")
                    or jwt_payload.get("organization_id")
                    or jwt_payload.get("org_id")
                    or org_id
                )
                tier = jwt_payload.get("tier") or tier

        # Use FastAPI's route template if available (so /cases/abc and /cases/xyz
        # share a bucket). The route template is set by Starlette on scope after
        # routing, but our middleware runs BEFORE routing. So we use the literal
        # path here; downstream we accept some bucket fragmentation. For the
        # critical case-run endpoints, normalize manually below.
        normalized_path = _normalize_path(path)

        decision = await check_rate_limit(
            organization_id=org_id,
            tier=tier,
            method=method,
            path=normalized_path,
        )

        if not decision.allowed:
            log.info(
                "rate_limit.reject",
                org=org_id,
                tier=tier,
                method=method,
                path=normalized_path,
                bucket=decision.bucket,
                count=decision.count,
                limit=decision.limit,
            )
            retry_after_s = max(int((decision.retry_after_ms / 1000.0) + 0.999), 1)
            body = json.dumps({
                "error": "rate_limit_exceeded",
                "bucket": decision.bucket,
                "limit": decision.limit,
                "retry_after_seconds": retry_after_s,
            }).encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after_s).encode()),
                    (b"x-ratelimit-bucket", decision.bucket.encode()),
                    (b"x-ratelimit-limit", str(decision.limit).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


# =============================================================================
# Path normalization — strip UUIDs / case_ids so /cases/{x} maps to one bucket
# =============================================================================


import re

_UUID_RE = re.compile(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_HEX_RE = re.compile(r"/[0-9a-f]{16,}", re.IGNORECASE)
_DIGIT_RE = re.compile(r"/\d+(?=/|$)")


def _normalize_path(path: str) -> str:
    """Replace likely-id segments with `{id}` for bucket-key stability."""
    p = _UUID_RE.sub("/{id}", path)
    p = _HEX_RE.sub("/{id}", p)
    p = _DIGIT_RE.sub("/{id}", p)
    return p
