"""GET /api/v1/cases/{case_id}/twin — the case's derived digital twin."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.twin import fetch_twin

log = structlog.get_logger()
router = APIRouter(tags=["case-twin"])


@router.get("/cases/{case_id}/twin")
async def case_twin(
    case_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    try:
        twin = await fetch_twin(user["organization_id"], case_id)
    except Exception as exc:  # noqa: BLE001 - a clear 503, never a fabricated twin
        log.warning("case_twin.db_unavailable", error=str(exc)[:200])
        raise HTTPException(
            503, "The case twin needs the case database, which is unavailable."
        ) from exc
    if twin is None:
        raise HTTPException(404, f"Case {case_id} not found")
    return twin
