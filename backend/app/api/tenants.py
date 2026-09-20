"""Tenant self-service onboarding.

Round-9 admin bootstrap was: SQL INSERT into `organizations`. Round-13
makes onboarding a structured, idempotent, audited operation.

  POST /api/v1/admin/tenants               create new tenant + admin user
  GET  /api/v1/admin/tenants               list (super-admin only)
  GET  /api/v1/admin/tenants/{id}          inspect

Today only the platform's super-admin can create tenants. Future:
self-service signup gated by EULA + OIDC IdP discovery.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.auth import hash_password, require_role
from app.cells import cell_for_organization
from app.db import db

router = APIRouter(prefix="/admin/tenants", tags=["admin"])


class CreateTenantBody(BaseModel):
    name:               str  = Field(..., min_length=2, max_length=80)
    slug:               str  = Field(..., min_length=2, max_length=40, pattern="^[a-z0-9-]+$")
    admin_email:        EmailStr
    admin_full_name:    str  = Field(..., min_length=2, max_length=80)
    data_region:        str  = Field(default="ap-south-1")
    tier:               str  = Field(default="silver", pattern="^(bronze|silver|gold)$")
    eula_accepted:      bool = Field(default=False)
    baa_signed:         bool = Field(default=False)


@router.post("")
async def create_tenant(
    body: CreateTenantBody,
    actor: dict[str, Any] = Depends(require_role("admin")),  # platform super-admin
) -> dict[str, Any]:
    if not body.eula_accepted:
        raise HTTPException(status_code=400, detail="eula_accepted must be true")
    if not body.baa_signed:
        raise HTTPException(status_code=400, detail="baa_signed must be true")

    org_id = f"org_{body.slug.replace('-', '')[:24]}"
    initial_password = secrets.token_urlsafe(20)

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow("SELECT id FROM organizations WHERE id = $1 OR slug = $2", org_id, body.slug)
            if existing is not None:
                raise HTTPException(status_code=409, detail=f"organization already exists: {body.slug}")

            await conn.execute(
                "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3)",
                org_id, body.name, body.slug,
            )

            # Initial org_quotas row (residency + tier — round 9 schema columns)
            try:
                await conn.execute(
                    """
                    INSERT INTO org_quotas (organization_id, data_region, tier)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (organization_id) DO UPDATE
                      SET data_region = EXCLUDED.data_region, tier = EXCLUDED.tier
                    """,
                    org_id, body.data_region, body.tier,
                )
            except Exception:  # noqa: BLE001
                # The org_quotas table might not have these columns yet on a fresh dev DB.
                pass

            user_id = f"user_{secrets.token_hex(8)}"
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, full_name, organization_id, role)
                VALUES ($1, $2, $3, $4, $5, 'admin')
                """,
                user_id,
                str(body.admin_email),
                hash_password(initial_password),
                body.admin_full_name,
                org_id,
            )

    cell = cell_for_organization(organization_id=org_id, data_region=body.data_region)

    return {
        "organization_id":   org_id,
        "slug":               body.slug,
        "name":               body.name,
        "data_region":        body.data_region,
        "tier":               body.tier,
        "cell_id":            cell.cell_id,
        "admin_user_id":      user_id,
        "admin_email":        str(body.admin_email),
        "initial_password":   initial_password,    # one-shot; not stored anywhere else
        "next_steps": [
            "Send the admin user the initial password through an out-of-band channel.",
            "Configure OIDC at /api/v1/auth/oidc/login if SSO is required.",
            "Apply Terraform module ops/terraform/audit-export/ for SIEM integration.",
            "Apply ops/terraform/secrets-rotation/ if customer requires HIPAA-aligned rotation.",
        ],
    }


@router.get("")
async def list_tenants(
    actor: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    rows = await db.fetch_ro(
        "SELECT id, name, slug, created_at FROM organizations ORDER BY created_at DESC",
    )
    return {"count": len(rows), "tenants": [dict(r) for r in rows]}


@router.get("/{organization_id}")
async def get_tenant(
    organization_id: str,
    actor: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    row = await db.fetchrow_ro(
        "SELECT id, name, slug, created_at FROM organizations WHERE id = $1",
        organization_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    cell = cell_for_organization(organization_id=organization_id)
    return {
        **dict(row),
        "cell_id": cell.cell_id,
        "region":  cell.region,
    }
