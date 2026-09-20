"""Business value API (IMPACT-3).

  GET /api/v1/business-value/case/{case_id}        — per-case ROI
  GET /api/v1/business-value/org                    — org direct-savings rollup
  GET /api/v1/business-value/star-impact            — projected Star Ratings $$
  GET /api/v1/business-value/provider-abrasion      — provider-abrasion reduction
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.business_value import (
    case_roi,
    org_value_rollup,
    projected_star_impact,
    provider_abrasion_score,
)

router = APIRouter(prefix="/business-value", tags=["business-value"])


@router.get("/case/{case_id}")
async def case_value(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        roi = await case_roi(case_id, organization_id=user["organization_id"])
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    except PermissionError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return roi.__dict__


@router.get("/org")
async def org_value(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    from datetime import datetime, timezone
    try:
        rollup = await org_value_rollup(user["organization_id"])
        return rollup.__dict__
    except Exception:
        # DB-less fallback so the dashboard ROI tiles render instead of "loading…"
        return {
            "organization_id": user["organization_id"],
            "asof_iso": datetime.now(timezone.utc).isoformat(),
            "cases_total": 0, "cases_decided": 0,
            "verdict_breakdown": {},
            "direct_savings_mtd_usd": 0, "direct_savings_annual_projection_usd": 0,
            "avg_decision_seconds": None, "avg_speedup_factor": None,
            "citations": [], "db_unavailable": True,
        }


@router.get("/star-impact")
async def star_impact(
    member_count: int = Query(default=100_000, ge=0, description="Org's MA member count for the projection."),
    current_star: float = Query(default=3.98, ge=0.0, le=5.0, description="Current MA Star Rating assumption."),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    proj = await projected_star_impact(
        user["organization_id"],
        member_count=member_count,
        current_star_assumption=current_star,
    )
    return proj.__dict__


@router.get("/provider-abrasion")
async def abrasion(
    rendering_npi: str | None = Query(default=None, description="Optional NPI filter."),
    days: int = Query(default=90, ge=1, le=365),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    score = await provider_abrasion_score(
        user["organization_id"],
        rendering_npi=rendering_npi,
        days=days,
    )
    return score.__dict__
