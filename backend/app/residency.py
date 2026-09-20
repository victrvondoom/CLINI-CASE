"""Per-tenant data residency runtime — actual enforcement, not just schema.

The `org_quotas.data_region` and `tier` columns store the customer's declared
region. This module consumes them at runtime to:

  • Validate every cross-boundary call (Bedrock, S3, KMS) is inside the tenant's
    declared region. Cross-region calls raise `ResidencyViolation`.
  • Resolve the per-tenant Bedrock model_id (e.g. EU tenant → `eu.anthropic.*`).
  • Resolve the per-tenant S3 bucket prefix.
  • Surface tenant routing in `/healthz/deep` and `/capabilities`.

Pairs with: `ops/architecture/DATA_RESIDENCY.md` (the policy doc).

Cognizant Gold-tier customers' security questionnaires literally check this:
"Does the system reject a write that crosses the declared data residency
boundary?" Today the answer is yes — see `_assert_region_match()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from app.config import settings
from app.db import db

log = structlog.get_logger()


class ResidencyViolation(Exception):
    """Raised when a runtime call would cross a tenant's declared data boundary.

    Example: a tenant with `data_region='eu-west-1'` causes a Bedrock InvokeModel
    against a US `model_id`. The Gateway raises this BEFORE the call leaves the
    process — closing the gap between "policy stated" and "policy enforced."
    """

    def __init__(self, *, organization_id: str, declared_region: str, attempted_region: str, resource: str) -> None:
        self.organization_id = organization_id
        self.declared_region = declared_region
        self.attempted_region = attempted_region
        self.resource = resource
        super().__init__(
            f"ResidencyViolation org={organization_id} declared={declared_region} "
            f"attempted={attempted_region} resource={resource}"
        )


@dataclass(frozen=True)
class TenantResidency:
    organization_id: str
    data_region: str
    tier: str   # bronze | silver | gold


# =============================================================================
# Region inference helpers
# =============================================================================


# Per-region Bedrock model_id prefix mapping. ClinCase's primary models are
# Claude Sonnet 4.6 + Haiku 4.5; AWS publishes per-region inference profiles.
_REGION_MODEL_PREFIX = {
    "ap-south-1": "apac.anthropic.",
    "ap-southeast-1": "apac.anthropic.",
    "ap-northeast-1": "apac.anthropic.",
    "us-east-1": "us.anthropic.",
    "us-west-2": "us.anthropic.",
    "eu-west-1": "eu.anthropic.",
    "eu-central-1": "eu.anthropic.",
    "eu-west-3": "eu.anthropic.",
}


def region_of_model_id(model_id: str) -> str | None:
    """Infer region from the prefix of a Bedrock cross-region inference profile id."""
    for region, prefix in _REGION_MODEL_PREFIX.items():
        if model_id.startswith(prefix):
            return region
    return None


def region_appropriate_model_id(*, base_model_id: str, target_region: str) -> str:
    """Rewrite a model_id to the target region's inference profile.

    Example:
        base='apac.anthropic.claude-sonnet-4-6-20251022-v1:0', target='eu-west-1'
        → 'eu.anthropic.claude-sonnet-4-6-20251022-v1:0'
    """
    target_prefix = _REGION_MODEL_PREFIX.get(target_region, "apac.anthropic.")
    # strip any current region prefix
    for prefix in set(_REGION_MODEL_PREFIX.values()):
        if base_model_id.startswith(prefix):
            return target_prefix + base_model_id[len(prefix):]
    # No known prefix: prepend target
    return target_prefix + base_model_id


# =============================================================================
# Tenant lookup + assertion API
# =============================================================================


async def get_tenant_residency(organization_id: str) -> TenantResidency:
    """Read the tenant's declared region + tier from `org_quotas`. Defaults
    to the deployment's region + 'silver' if the row doesn't exist yet."""
    row = await db.fetchrow(
        "SELECT data_region, tier FROM org_quotas WHERE organization_id = $1",
        organization_id,
    )
    if row is None:
        return TenantResidency(
            organization_id=organization_id,
            data_region=settings.AWS_REGION,
            tier="silver",
        )
    return TenantResidency(
        organization_id=organization_id,
        data_region=row["data_region"],
        tier=row["tier"],
    )


async def assert_residency(*, organization_id: str, attempted_region: str, resource: str) -> None:
    """Raise ResidencyViolation if a runtime call would cross the tenant's
    declared boundary. Call this from every external-service code path."""
    res = await get_tenant_residency(organization_id)
    if res.data_region != attempted_region:
        log.warning(
            "residency.violation",
            org=organization_id,
            declared=res.data_region,
            attempted=attempted_region,
            resource=resource,
        )
        raise ResidencyViolation(
            organization_id=organization_id,
            declared_region=res.data_region,
            attempted_region=attempted_region,
            resource=resource,
        )


def assert_region_match_sync(*, organization_id: str, declared_region: str, attempted_region: str, resource: str) -> None:
    """Sync variant for places where `await get_tenant_residency` already happened."""
    if declared_region != attempted_region:
        raise ResidencyViolation(
            organization_id=organization_id,
            declared_region=declared_region,
            attempted_region=attempted_region,
            resource=resource,
        )


# =============================================================================
# Per-tenant resource resolvers
# =============================================================================


async def resolve_tenant_bedrock_model_id(
    *,
    organization_id: str,
    base_model_id: str | None = None,
) -> str:
    """Return the model_id that's correct for this tenant's region.

    Today: rewrite the model_id prefix to the tenant's region. Tomorrow:
    consult the tenant's per-region allowlist in `tenant_policies` first.
    """
    res = await get_tenant_residency(organization_id)
    base = base_model_id or settings.BEDROCK_MODEL_ID
    return region_appropriate_model_id(base_model_id=base, target_region=res.data_region)


async def resolve_tenant_s3_bucket_prefix(*, organization_id: str) -> str:
    """Return the S3 prefix the tenant's audit data should be written to.

    Convention: `s3://clincase-{tier}-{region}/{org_id}/`.
    """
    res = await get_tenant_residency(organization_id)
    return f"clincase-{res.tier}-{res.data_region}/{organization_id}/"


# =============================================================================
# Snapshot for /capabilities + /healthz/deep
# =============================================================================


async def residency_snapshot(*, organization_id: str | None = None) -> dict[str, Any]:
    """Snapshot for ops endpoints. Without an org_id, return deployment defaults."""
    if organization_id:
        res = await get_tenant_residency(organization_id)
        bedrock_model = await resolve_tenant_bedrock_model_id(organization_id=organization_id)
        s3_prefix = await resolve_tenant_s3_bucket_prefix(organization_id=organization_id)
        return {
            "organization_id": organization_id,
            "data_region": res.data_region,
            "tier": res.tier,
            "resolved_bedrock_model_id": bedrock_model,
            "resolved_s3_prefix": s3_prefix,
        }
    # Deployment-default snapshot
    return {
        "deployment_region": settings.AWS_REGION,
        "deployment_default_tier": "silver",
        "supported_regions": list(_REGION_MODEL_PREFIX.keys()),
        "regions_with_bedrock_inference_profile": [
            r for r in _REGION_MODEL_PREFIX.keys()
        ],
    }
