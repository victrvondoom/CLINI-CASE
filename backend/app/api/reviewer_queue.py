"""GET /api/v1/reviewer/queue — REFER cases awaiting a human, for the caller's organisation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.review.queue import PRIORITY_RULE, fetch_review_queue

log = structlog.get_logger()
router = APIRouter(prefix="/reviewer", tags=["review"])


@router.get("/queue")
async def review_queue(
    limit: int = Query(default=50, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        items = await fetch_review_queue(user["organization_id"], limit)
    except Exception as exc:  # noqa: BLE001 - a clinical queue must never be faked when the DB is down
        log.warning("reviewer.queue_db_unavailable", error=str(exc)[:200])
        raise HTTPException(
            503, "The reviewer queue needs the case database, which is unavailable."
        ) from exc
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total": len(items),
        "priority_rule": PRIORITY_RULE,
        "counts": {
            p: sum(1 for i in items if i["priority"] == p) for p in ("high", "medium", "low")
        },
        "items": items,
    }
