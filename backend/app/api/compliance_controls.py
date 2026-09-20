"""Compliance control library endpoints (round 12)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.compliance.control_library import (
    all_controls,
    by_framework,
    get,
    summary,
    to_dict,
)

router = APIRouter(prefix="/compliance/control-library", tags=["compliance"])


@router.get("")
async def list_all() -> dict[str, Any]:
    return {
        "summary": summary(),
        "controls": [to_dict(c) for c in all_controls()],
    }


@router.get("/{framework}")
async def list_by_framework(framework: str) -> dict[str, Any]:
    controls = by_framework(framework)
    if not controls:
        raise HTTPException(status_code=404, detail=f"unknown framework: {framework}")
    return {
        "framework": framework,
        "count": len(controls),
        "controls": [to_dict(c) for c in controls],
    }


@router.get("/{framework}/{clause_id}")
async def get_one(framework: str, clause_id: str) -> dict[str, Any]:
    c = get(framework, clause_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"unknown control: {framework}/{clause_id}")
    return to_dict(c)
