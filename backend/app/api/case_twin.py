"""GET /api/v1/cases/{case_id}/twin — the case's derived digital twin."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import db
from app.identity import case_intelligence_id
from app.runs import list_runs
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


@router.get("/cases/{case_id}/runs")
async def case_runs(
    case_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    """Every execution of the case (initial, reruns, human-review resumes), oldest first."""
    try:
        exists = await db.fetchval(
            "SELECT 1 FROM cases WHERE id = $1 AND organization_id = $2",
            case_id,
            user["organization_id"],
        )
        rows = await list_runs(user["organization_id"], case_id) if exists is not None else []
    except Exception as exc:  # noqa: BLE001
        log.warning("case_runs.db_unavailable", error=str(exc)[:200])
        raise HTTPException(
            503, "Run history needs the case database, which is unavailable."
        ) from exc
    if exists is None:
        raise HTTPException(404, f"Case {case_id} not found")
    return {
        "case_id": case_id,
        "case_intelligence_id": case_intelligence_id(user["organization_id"], case_id),
        "runs": [
            {
                **r,
                "job_id": str(r["job_id"]) if r.get("job_id") else None,
                "created_at": r["created_at"].isoformat(),
                "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            }
            for r in rows
        ],
    }
