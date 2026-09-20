"""Quota inspection + admin endpoints (SCALE-8).

  • GET  /api/v1/quotas/me           — any authenticated user inspects their org
  • PUT  /api/v1/quotas/{org_id}     — admin role only; tune caps for an org

The actual gate (atomic increment + 429 response) lives in `app/quotas.py`
and is called from `app/api/cases.py:run_full` and `app/api/jobs.py:run_full_async`.
This router is for visibility/operations only — it does not enforce.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_role
from app.quotas import get_quota, set_org_limits

router = APIRouter(prefix="/quotas", tags=["quotas"])


class QuotaResponse(BaseModel):
    organization_id: str
    daily_case_limit: int
    monthly_case_limit: int
    current_day_count: int
    current_month_count: int
    daily_remaining: int
    monthly_remaining: int


def _to_response(state: dict[str, Any]) -> QuotaResponse:
    daily_limit = state.get("daily_case_limit", 0)
    monthly_limit = state.get("monthly_case_limit", 0)
    return QuotaResponse(
        organization_id=state["organization_id"],
        daily_case_limit=daily_limit,
        monthly_case_limit=monthly_limit,
        current_day_count=state.get("current_day_count", 0),
        current_month_count=state.get("current_month_count", 0),
        daily_remaining=max(0, daily_limit - state.get("current_day_count", 0)),
        monthly_remaining=max(0, monthly_limit - state.get("current_month_count", 0)),
    )


@router.get("/me", response_model=QuotaResponse)
async def get_my_org_quota(
    user: dict[str, Any] = Depends(get_current_user),
) -> QuotaResponse:
    """Return the caller's org quota state. Available to all authenticated users."""
    return _to_response(await get_quota(user["organization_id"]))


class UpdateQuotaRequest(BaseModel):
    daily_case_limit: int | None = Field(default=None, ge=0)
    monthly_case_limit: int | None = Field(default=None, ge=0)


@router.put("/{organization_id}", response_model=QuotaResponse)
async def update_org_quota(
    organization_id: str,
    req: UpdateQuotaRequest,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> QuotaResponse:
    """Admin-only: tune an org's daily/monthly caps.

    Authorization: admins are scoped to their own org. Cross-org admin is
    intentionally NOT supported — separate platform-admin role would be
    required and we don't ship one for the hackathon.
    """
    if organization_id != user["organization_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cross-org quota administration is not permitted.",
        )
    state = await set_org_limits(
        organization_id,
        daily_case_limit=req.daily_case_limit,
        monthly_case_limit=req.monthly_case_limit,
    )
    return _to_response(state)
