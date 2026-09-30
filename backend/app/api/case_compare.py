"""Multi-payer comparison endpoints — see app/review/compare.py."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.review.compare import PAYERS, compare_case, create_comparison_case, policy_for

log = structlog.get_logger()
router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/{case_id}/compare")
async def compare(case_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        out = await compare_case(user["organization_id"], case_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("compare.db_unavailable", error=str(exc)[:200])
        raise HTTPException(
            503, "Comparison needs the case database, which is unavailable."
        ) from exc
    if out is None:
        raise HTTPException(404, f"Case {case_id} not found")
    return out


@router.post("/{case_id}/compare/{payer_id}")
async def create_sibling(
    case_id: str, payer_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    if payer_id not in PAYERS:
        raise HTTPException(422, f"Unknown payer {payer_id!r}; expected one of {sorted(PAYERS)}")
    try:
        current = await compare_case(user["organization_id"], case_id)
        if current is None:
            raise HTTPException(404, f"Case {case_id} not found")
        if payer_id == current["payer_id"]:
            raise HTTPException(409, "This case is already submitted to that payer.")
        if policy_for(payer_id, current["treatment"]) is None:
            raise HTTPException(
                409, f"{PAYERS[payer_id]} has no policy on file for {current['treatment']}."
            )
        res = await create_comparison_case(user["organization_id"], user["id"], case_id, payer_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("compare.create_failed", error=str(exc)[:200])
        raise HTTPException(503, "The comparison case was not saved. Please retry.") from exc
    new_id, created = res  # type: ignore[misc]
    return {"case_id": new_id, "created": created, "payer_id": payer_id}
