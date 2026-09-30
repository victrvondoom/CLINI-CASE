"""Policy catalog endpoints: the searchable corpus with computed stats, and per-policy detail with matched changes
and the caller's affected open cases."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app import policy_catalog
from app.auth import get_current_user

log = structlog.get_logger()
router = APIRouter(prefix="/policy-catalog", tags=["policies"])


@router.get("")
async def list_catalog(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return policy_catalog.catalog()


@router.get("/{policy_id}")
async def policy_detail(
    policy_id: str, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    policy = policy_catalog.find_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy {policy_id!r} is not in the corpus")
    out = policy_catalog.detail(policy)
    try:
        out["open_cases"] = await policy_catalog.open_cases_for(user["organization_id"], policy)
        out["open_cases_available"] = True
    except Exception as exc:  # noqa: BLE001 - the policy itself is still valid without the case database
        log.warning("policy_catalog.cases_unavailable", error=str(exc)[:200])
        out["open_cases"] = []
        out["open_cases_available"] = False
    return out
