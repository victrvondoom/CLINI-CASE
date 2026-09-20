"""Prompt-versioning admin endpoints.

  GET  /api/v1/prompts                                list all prompt versions
  GET  /api/v1/prompts/{agent_name}                   list one agent's versions
  POST /api/v1/prompts                                add a new version (draft)
  POST /api/v1/prompts/{agent_name}/{version}/activate  activate this version
  POST /api/v1/prompts/{agent_name}/traffic-split     set A/B split
  POST /api/v1/prompts/{agent_name}/assign            pin a tenant to a version
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_role
from app.prompts_versioning import (
    activate_prompt,
    add_prompt,
    assign_to_tenant,
    list_prompts,
    set_traffic_split,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


class AddPromptBody(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=64)
    version:    str = Field(..., min_length=1, max_length=32)
    body:       str = Field(..., min_length=1)
    description: str | None = None
    status:     str = Field(default="draft", pattern="^(draft|shadow|active|retired)$")


class TrafficSplitBody(BaseModel):
    weights: dict[str, float]


class AssignBody(BaseModel):
    organization_id: str
    version:         str


@router.get("")
async def list_all(
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    rows = await list_prompts()
    return {"count": len(rows), "prompts": rows}


@router.get("/{agent_name}")
async def list_by_agent(
    agent_name: str,
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    rows = await list_prompts(agent_name=agent_name)
    return {"agent_name": agent_name, "count": len(rows), "versions": rows}


@router.post("")
async def post_prompt(
    body: AddPromptBody,
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    await add_prompt(
        agent_name=body.agent_name,
        version=body.version,
        body=body.body,
        description=body.description,
        status=body.status,
    )
    return {"status": "added", "agent_name": body.agent_name, "version": body.version}


@router.post("/{agent_name}/{version}/activate")
async def activate(
    agent_name: str,
    version: str,
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    await activate_prompt(agent_name=agent_name, version=version)
    return {"status": "active", "agent_name": agent_name, "version": version}


@router.post("/{agent_name}/traffic-split")
async def post_traffic_split(
    agent_name: str,
    body: TrafficSplitBody,
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    try:
        await set_traffic_split(agent_name=agent_name, weights=body.weights)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "agent_name": agent_name, "weights": body.weights}


@router.post("/{agent_name}/assign")
async def post_assign(
    agent_name: str,
    body: AssignBody,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    if body.organization_id != user["organization_id"]:
        raise HTTPException(status_code=403, detail="cross-tenant assignment forbidden")
    await assign_to_tenant(
        organization_id=body.organization_id,
        agent_name=agent_name,
        version=body.version,
    )
    return {"status": "assigned", "organization_id": body.organization_id, "agent_name": agent_name, "version": body.version}
