"""GET /api/v1/authz/policies — auditor inspection of the Cedar policy library.

Auditors at Cognizant TriZetto / payer security teams want to read
*every authorization rule* before authorizing a customer pilot. This
endpoint is the read-only window into that library.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_role
from app.authz import policy_snapshot

router = APIRouter(prefix="/authz", tags=["authz"])


@router.get("/policies")
async def get_policies(
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    """Return the Cedar-shape policy library. Admin-only."""
    return policy_snapshot()
