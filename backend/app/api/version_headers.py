"""API version + deprecation header middleware.

Every response gets:
  X-API-Version: v1   (or v2)
  X-ClinCase-Build-Sha: <short SHA>   (set by request_id middleware on response)

When the V1_SUNSET_DATE env is set (RFC 8594 sunset format), v1 endpoints
ALSO get:
  Sunset: Sat, 01 Aug 2026 00:00:00 GMT
  Deprecation: true
  Link: </api/v2/...>; rel="successor-version"

These are the standards Stripe/Twilio/AWS use.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from email.utils import format_datetime

from starlette.types import ASGIApp, Receive, Scope, Send

_V1_SUNSET_DATE = os.getenv("V1_SUNSET_DATE")  # ISO-8601 date e.g. "2026-08-01"
_V1_SUCCESSOR_PREFIX = os.getenv("V1_SUCCESSOR_PREFIX", "/api/v2")


def _format_sunset(iso_date: str) -> str:
    """Convert ISO date to RFC 8594-required HTTP-date format."""
    try:
        dt = datetime.fromisoformat(iso_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return format_datetime(dt, usegmt=True)
    except (ValueError, TypeError):
        return ""


class VersionHeadersMiddleware:
    """ASGI middleware. Stamps version + (when configured) deprecation headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_v1 = path.startswith("/api/v1/")
        is_v2 = path.startswith("/api/v2/")

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if is_v1:
                    headers.append((b"x-api-version", b"v1"))
                    if _V1_SUNSET_DATE:
                        sunset_http = _format_sunset(_V1_SUNSET_DATE)
                        if sunset_http:
                            headers.append((b"sunset", sunset_http.encode()))
                            headers.append((b"deprecation", b"true"))
                            successor_path = path.replace("/api/v1/", _V1_SUCCESSOR_PREFIX + "/", 1)
                            headers.append((
                                b"link",
                                f'<{successor_path}>; rel="successor-version"'.encode(),
                            ))
                elif is_v2:
                    headers.append((b"x-api-version", b"v2"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
