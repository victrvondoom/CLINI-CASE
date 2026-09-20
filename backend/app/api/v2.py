"""/api/v2 scaffold — concrete proof-of-life for the v2 deprecation pipeline.

Today /api/v2 is "co-existence" mode: every endpoint mirrors /api/v1 with
a small set of breaking-change improvements that v2 explicitly fixes:

  • Standardized error envelope (RFC 7807 Problem Details for HTTP APIs)
  • Pagination shape standardization (cursor-based, not offset)
  • Versioning headers explicit on every response

When customers cut over, they hit /api/v2 endpoints. /api/v1 stays for the
deprecation runway documented in `ops/architecture/API_VERSIONING.md`.

Today /api/v2 ships ONE endpoint as the proof-of-life: /api/v2/healthz. It
returns the same payload as /api/v1/healthz wrapped in the new envelope.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response

router = APIRouter(prefix="/api/v2", tags=["v2"])


# =============================================================================
# Standard v2 response envelope (RFC 7807-aligned for errors)
# =============================================================================


def _v2_envelope(data: Any, *, links: dict[str, str] | None = None) -> dict[str, Any]:
    """Standard v2 success envelope. All v2 responses use this shape.

    Breaking change vs v1: v1 returned the data object directly; v2 wraps it
    in `data` + adds `links` + `meta`.
    """
    return {
        "data": data,
        "links": links or {},
        "meta": {
            "api_version": "v2",
            "served_at": datetime.now(UTC).isoformat(),
        },
    }


# =============================================================================
# /api/v2/healthz — the proof-of-life endpoint
# =============================================================================


@router.get("/healthz")
async def healthz(response: Response) -> dict[str, Any]:
    """v2 healthz — same liveness signal as v1, in the new envelope."""
    response.headers["X-API-Version"] = "v2"
    return _v2_envelope({"status": "ok"})


# =============================================================================
# /api/v2/version — same data as v1 in the new envelope
# =============================================================================


@router.get("/version")
async def version(response: Response) -> dict[str, Any]:
    """v2 version — wraps the v1 payload in the new envelope."""
    response.headers["X-API-Version"] = "v2"
    from app.api.ops import version as v1_version
    payload = await v1_version()
    return _v2_envelope(payload)
