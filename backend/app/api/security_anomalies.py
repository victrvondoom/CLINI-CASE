"""GET /api/v1/security/anomalies — admin-only SOC inspection endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import is_platform_admin, require_role
from app.security.breach_detector import recent_anomalies

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/anomalies")
async def list_anomalies(
    user: dict[str, Any] = Depends(require_role("admin")),
    limit: int = Query(default=100, ge=1, le=1000),
    same_org_only: bool = Query(default=True),
) -> dict[str, Any]:
    if not same_org_only and not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Global view requires platform administrator")
    org = user["organization_id"] if same_org_only else None
    rows = await recent_anomalies(organization_id=org, limit=limit)
    return {
        "scope": "same-org" if same_org_only else "global (admin)",
        "count": len(rows),
        "anomalies": rows,
    }
