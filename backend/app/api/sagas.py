"""Saga inspection + replay endpoints.

  GET  /api/v1/sagas/me                       caller's recent sagas
  GET  /api/v1/sagas/me?status=failed         filter by status
  GET  /api/v1/sagas/{saga_id}                detail
  POST /api/v1/sagas/{saga_id}/replay         operator-driven replay
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user, require_role
from app.saga import get_saga, list_sagas, replay_saga

router = APIRouter(prefix="/sagas", tags=["sagas"])


def _saga_to_dict(saga: Any) -> dict[str, Any]:
    return {
        "saga_id": saga.saga_id,
        "case_id": saga.case_id,
        "organization_id": saga.organization_id,
        "saga_type": saga.saga_type,
        "status": saga.status,
        "error": saga.error,
        "steps": [s.__dict__ for s in saga.steps],
        "created_at": saga.created_at,
        "updated_at": saga.updated_at,
    }


@router.get("/me")
async def my_sagas(
    user: dict[str, Any] = Depends(get_current_user),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    sagas = await list_sagas(
        organization_id=user["organization_id"],
        status=status,
        limit=limit,
    )
    return {
        "organization_id": user["organization_id"],
        "filter_status": status,
        "count": len(sagas),
        "sagas": [_saga_to_dict(s) for s in sagas],
    }


@router.get("/{saga_id}")
async def get_one(
    saga_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    saga = await get_saga(saga_id)
    if saga is None:
        raise HTTPException(status_code=404, detail="saga not found")
    if saga.organization_id != user["organization_id"]:
        raise HTTPException(status_code=403, detail="cross-tenant saga access forbidden")
    return _saga_to_dict(saga)


@router.post("/{saga_id}/replay")
async def replay(
    saga_id: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    saga = await get_saga(saga_id)
    if saga is None:
        raise HTTPException(status_code=404, detail="saga not found")
    if saga.organization_id != user["organization_id"]:
        raise HTTPException(status_code=403, detail="cross-tenant saga replay forbidden")
    try:
        replayed = await replay_saga(saga_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _saga_to_dict(replayed)
