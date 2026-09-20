"""GET /api/v1/rate-limits/me — caller's declared rate-limit table."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.rate_limit import snapshot_for_tier

router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])


@router.get("/me")
async def my_rate_limits(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the rate-limit table for the caller's tenant tier.

    The caller can use this to size their client-side concurrency. Pairs with
    the 429 + `Retry-After` header response when a bucket is exhausted.
    """
    # Default to silver if tier not yet declared in org_quotas (round-9 schema)
    tier = "silver"
    try:
        from app.db import db
        row = await db.fetchrow(
            "SELECT tier FROM org_quotas WHERE organization_id = $1",
            user["organization_id"],
        )
        if row is not None:
            tier = row["tier"]
    except Exception:  # noqa: BLE001
        pass
    snap = await snapshot_for_tier(tier=tier)
    return {"organization_id": user["organization_id"], **snap}
