"""Operator endpoints for the outbox dead-letter queue.

  GET  /api/v1/dlq/me                         caller's DLQ events
  GET  /api/v1/dlq/me/stats                   counts by event_type
  POST /api/v1/dlq/{event_id}/replay          push back to event_outbox (admin)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user, require_role
from app.events import dlq

router = APIRouter(prefix="/dlq", tags=["dlq"])


@router.get("/me")
async def my_dlq(
    user: dict[str, Any] = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    rows = await dlq.list_dlq(
        organization_id=user["organization_id"],
        event_type=event_type,
        limit=limit,
    )
    return {
        "organization_id": user["organization_id"],
        "filter_event_type": event_type,
        "count": len(rows),
        "events": rows,
    }


@router.get("/me/stats")
async def my_dlq_stats(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await dlq.dlq_stats(organization_id=user["organization_id"])


@router.post("/{event_id}/replay")
async def replay_event(
    event_id: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    ok = await dlq.replay(event_id=event_id, organization_id=user["organization_id"])
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"DLQ event not found in your tenant: {event_id}",
        )
    return {"replayed": True, "event_id": event_id}
