"""Live compliance scorecard endpoints (IMPACT-2).

  GET /api/v1/compliance/case/{case_id}      — per-case clause-by-clause scorecard
  GET /api/v1/compliance/org                  — org-level rollup with deadlines
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.compliance.cms_0057f import case_scorecard, org_scorecard

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/case/{case_id}")
async def get_case_scorecard(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the per-case CMS-0057-F + state-law scorecard.

    Org-scoped: case must belong to the caller's organization."""
    try:
        sc = await case_scorecard(case_id, organization_id=user["organization_id"])
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    except PermissionError:
        # Don't leak existence cross-org
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return sc.to_dict()


@router.get("/org")
async def get_org_scorecard(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the org-level compliance rollup. DB-less deploys (no RDS) get
    a zeroed scorecard rather than a 500 — clauses + deadlines still render
    because they're hard-coded regulatory data."""
    from datetime import datetime, timezone
    try:
        return await org_scorecard(user["organization_id"])
    except Exception:
        return {
            "organization_id": user["organization_id"],
            "asof_iso": datetime.now(timezone.utc).isoformat(),
            "totals": {"cases_total": 0, "cases_decided": 0, "denies": 0, "denies_with_review": 0, "audit_complete_cases": 0},
            "headline_metrics": {
                "tat_compliance_pct": 0, "sb1120_compliance_pct": 0,
                "audit_completeness_pct": 0, "mean_tat_seconds": 0, "max_tat_seconds": 0,
            },
            "clauses": [],
            "deadlines": {},
            "db_unavailable": True,
        }
