"""Per-tenant data residency introspection endpoint.

  GET /api/v1/residency           — caller's org residency + resolved resources
  GET /api/v1/residency/{org_id}  — admin (same-org only) inspection
  GET /api/v1/residency/regions   — list of supported regions
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_role
from app.residency import residency_snapshot

router = APIRouter(prefix="/residency", tags=["residency"])


@router.get("")
async def my_residency(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Caller's organization data-residency snapshot."""
    return await residency_snapshot(organization_id=user["organization_id"])


@router.get("/regions")
async def supported_regions(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: ARG001
) -> dict[str, Any]:
    """Deployment-level supported regions list."""
    return await residency_snapshot()


@router.get("/{organization_id}")
async def org_residency(
    organization_id: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Admin-only same-org residency inspection. Cross-org is blocked."""
    if organization_id != user["organization_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cross-org residency inspection is not permitted.",
        )
    return await residency_snapshot(organization_id=organization_id)
