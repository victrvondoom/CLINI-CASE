"""Kiro IDE export API (IMPACT-4).

Lets the demo show "regenerate Kiro specs from the live manifest" with one
button, and lets a developer show one example spec without leaving the UI.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_role
from app.integrations.kiro import export_kiro_specs, kiro_spec_for_agent

router = APIRouter(prefix="/integrations/kiro", tags=["integrations:kiro"])


@router.post("/export")
async def export_specs(
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    """Materialize `.kiro/specs/` on disk. Admin-only — touches the working tree."""
    summary = export_kiro_specs()
    return {
        "ok": True,
        "summary": summary,
        "next_step": (
            "Open the repo in Kiro IDE; specs auto-load. "
            "Edit a requirements.md; Hook regenerates the agent skeleton."
        ),
    }


@router.get("/spec/{parent}")
async def get_parent_spec(
    parent: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer", "coordinator")),  # noqa: ARG001
) -> dict[str, Any]:
    """Return one parent agent's three spec files (no disk write)."""
    from app.agents.manifest import AGENT_MANIFEST
    match = next((p for p in AGENT_MANIFEST if p["name"] == parent), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Parent agent {parent!r} not found")
    return {
        "agent": parent,
        "files": kiro_spec_for_agent(match),
    }


@router.get("/spec/{parent}/{sub}")
async def get_sub_spec(
    parent: str,
    sub: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer", "coordinator")),  # noqa: ARG001
) -> dict[str, Any]:
    """Return one sub-agent's three spec files."""
    from app.agents.manifest import AGENT_MANIFEST
    parent_match = next((p for p in AGENT_MANIFEST if p["name"] == parent), None)
    if parent_match is None:
        raise HTTPException(status_code=404, detail=f"Parent {parent!r} not found")
    sub_match = next((s for s in parent_match.get("sub_agents", []) if s["name"] == sub), None)
    if sub_match is None:
        raise HTTPException(status_code=404, detail=f"Sub-agent {parent}.{sub} not found")
    return {
        "agent": f"{parent}.{sub}",
        "files": kiro_spec_for_agent(sub_match),
    }
