"""GenAI Gateway introspection endpoints.

  GET /api/v1/llm-gateway/usage           — caller's tenant 24h rolling usage
  GET /api/v1/llm-gateway/policy           — caller's tenant policy (model allowlist + caps)
  GET /api/v1/llm-gateway/usage/{org_id}    — admin-only cross-org inspection (same-org only)

These endpoints power the SRE + customer-CISO views of model invocation
patterns. The actual enforcement happens inside `app/llm/gateway.py`.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user, require_role
from app.llm.circuit_breaker import all_breaker_snapshots
from app.llm.gateway import get_tenant_policy, tenant_usage

router = APIRouter(prefix="/llm-gateway", tags=["llm-gateway"])


@router.get("/usage")
async def my_usage(
    hours: int = Query(default=24, ge=1, le=168),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Caller's organization rolling usage."""
    return await tenant_usage(user["organization_id"], hours=hours)


@router.get("/policy")
async def my_policy(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Caller's organization Gateway policy (model allowlist + caps + guardrail id)."""
    p = await get_tenant_policy(user["organization_id"])
    return {
        "organization_id": p.organization_id,
        "allowed_model_ids": p.allowed_model_ids,
        "daily_input_token_cap": p.daily_input_token_cap,
        "daily_output_token_cap": p.daily_output_token_cap,
        "daily_usd_cap": p.daily_usd_cap,
        "bedrock_guardrail_id": p.bedrock_guardrail_id,
    }


@router.get("/circuit-breakers")
async def circuit_breakers(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: ARG001
) -> dict[str, Any]:
    """Per-model circuit breaker state. SRE + judge introspection.

    Each breaker tracks: model_id · state (CLOSED/OPEN/HALF_OPEN) · samples
    · current failure rate · cooldown remaining. When a breaker is OPEN,
    Bedrock InvokeModel is fast-failed before any TPM is consumed.
    """
    return {
        "breakers": all_breaker_snapshots(),
        "summary": "Per-model 3-state circuit breaker (CLOSED → OPEN on >=50% failure in 50-call window; HALF_OPEN after 30s cooldown)",
    }


@router.get("/usage/{organization_id}")
async def org_usage(
    organization_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Admin-only cross-org usage. Restricted to caller's own org for safety
    (cross-tenant inspection is intentionally NOT supported)."""
    if organization_id != user["organization_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cross-org Gateway usage is not permitted; use /usage for your own org.",
        )
    return await tenant_usage(organization_id, hours=hours)
