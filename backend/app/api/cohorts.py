"""GET /api/v1/cohorts — cross-case analytics for the caller's organisation."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics.cohorts import compute_cohorts, fetch_cohort_rows
from app.auth import get_current_user

log = structlog.get_logger()
router = APIRouter(prefix="/cohorts", tags=["analytics"])


@router.get("")
async def cohorts(
    days: int = Query(default=90, ge=1, le=730, description="Look-back window in days."),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        rows = await fetch_cohort_rows(user["organization_id"], days)
    except Exception as exc:  # noqa: BLE001 - surface as a clear 503, never fabricate numbers
        log.warning("cohorts.db_unavailable", error=str(exc)[:200])
        raise HTTPException(
            503, "Cohort analytics need the case database, which is unavailable."
        ) from exc
    return compute_cohorts(rows, days=days)
