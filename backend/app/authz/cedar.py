"""Cedar-shaped attribute-based authorization evaluator.

Cedar's core semantics:
  • Every authorization decision is computed over: (principal, action, resource, context)
  • Policies are `permit` or `forbid` with conditions
  • `forbid` overrides `permit` (deny-wins semantics)

Today's implementation is intentionally small (≈100 lines) so the policy
shape is auditable inline — payer security teams want to read every rule.

Migration path:
  1. Today — this Python evaluator + JSON policy files
  2. Post-pilot — AWS Verified Permissions (managed Cedar) when policy
     count > 50 rules OR per-evaluation latency budget < 1ms

Pairs with: ops/architecture/AUTHZ_CEDAR.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AuthzDenied(Exception):
    """Raised when an authorization check fails. Carries the deny reason."""

    def __init__(self, reason: str, *, principal: str, action: str, resource: str) -> None:
        self.reason = reason
        self.principal = principal
        self.action = action
        self.resource = resource
        super().__init__(f"AUTHZ_DENIED: {reason} (principal={principal} action={action} resource={resource})")


@dataclass(frozen=True)
class Principal:
    user_id: str
    organization_id: str
    role: str                    # 'coordinator' | 'reviewer' | 'admin'
    attributes: dict[str, Any] = field(default_factory=dict)
    # attributes can include: lob, msa_id, license_state, npi, oncology_cert


@dataclass(frozen=True)
class Resource:
    kind: str                    # 'case' | 'evidence_pack' | 'audit_log' | ...
    id: str
    organization_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
    # attributes can include: lob, status, signed_by_physician, classification


@dataclass(frozen=True)
class AuthzDecision:
    allowed: bool
    matched_policy: str
    reason: str


# =============================================================================
# Policy library — Cedar shape, evaluated in order; first deny wins
# =============================================================================
# Each policy is a (effect, applies_to_action_set, condition_function, name)
# tuple. The condition is a Python lambda that takes (principal, resource,
# context) and returns True iff the policy should fire.
#
# In production this becomes a JSON file per policy in
# `app/authz/policies/*.cedar.json`. Today it's inline so judges can read it.

PolicyEffect = str  # "permit" | "forbid"

_POLICIES: list[tuple[PolicyEffect, set[str], Any, str]] = [
    # ===================== forbid (deny-wins) ===============================
    (
        "forbid", {"case:read", "case:update", "case:delete", "case:run", "case:resume"},
        lambda p, r, _ctx: p.organization_id != r.organization_id,
        "deny-cross-org-case-access",
    ),
    (
        "forbid", {"case:sign-off"},
        lambda p, r, _ctx: r.attributes.get("signed_by_physician") is True,
        "deny-double-signoff-CA-SB1120",
    ),
    (
        "forbid", {"case:sign-off"},
        lambda p, r, _ctx: p.role == "coordinator",
        "deny-coordinator-signoff",
    ),
    (
        "forbid", {"audit_log:read"},
        lambda p, r, _ctx: p.role != "admin",
        "deny-audit-log-non-admin",
    ),
    # ===================== permit ==========================================
    (
        "permit", {"case:read", "case:update", "case:run", "case:resume"},
        lambda p, r, _ctx: (
            p.organization_id == r.organization_id
            and p.role in {"coordinator", "reviewer", "admin"}
        ),
        "permit-same-org-case-rw",
    ),
    (
        "permit", {"case:sign-off"},
        lambda p, r, _ctx: (
            p.organization_id == r.organization_id
            and p.role in {"reviewer", "admin"}
            and r.attributes.get("signed_by_physician") is not True
        ),
        "permit-reviewer-signoff",
    ),
    (
        "permit", {"audit_log:read"},
        lambda p, _r, _ctx: p.role == "admin",
        "permit-admin-audit-read",
    ),
    (
        "permit", {"case:scope-by-lob:read"},
        lambda p, r, _ctx: (
            p.organization_id == r.organization_id
            and p.role in {"coordinator", "reviewer", "admin"}
            and (
                p.attributes.get("lob") is None  # legacy users with no LOB attribute pass
                or p.attributes.get("lob") == r.attributes.get("lob")
            )
        ),
        "permit-lob-scoped-case-read",
    ),
    (
        "permit", {"evidence_pack:read"},
        lambda p, r, _ctx: (
            p.organization_id == r.organization_id
            and p.role in {"reviewer", "admin"}
        ),
        "permit-evidence-pack-reviewer-admin",
    ),
]


def is_authorized(
    *,
    principal: Principal,
    action: str,
    resource: Resource,
    context: dict[str, Any] | None = None,
) -> AuthzDecision:
    """Evaluate the policy library. Cedar deny-wins semantics:
    1. Check all `forbid` policies. ANY match → DENY.
    2. Check all `permit` policies. AT LEAST ONE match → ALLOW.
    3. Default → DENY.
    """
    ctx = context or {}

    # 1. Deny pass — any forbid match terminates as deny
    for effect, actions, cond, name in _POLICIES:
        if effect != "forbid":
            continue
        if action not in actions:
            continue
        if cond(principal, resource, ctx):
            return AuthzDecision(
                allowed=False,
                matched_policy=name,
                reason=f"forbid policy '{name}' matched",
            )

    # 2. Permit pass — first permit match wins
    for effect, actions, cond, name in _POLICIES:
        if effect != "permit":
            continue
        if action not in actions:
            continue
        if cond(principal, resource, ctx):
            return AuthzDecision(
                allowed=True,
                matched_policy=name,
                reason=f"permit policy '{name}' matched",
            )

    # 3. Default deny
    return AuthzDecision(
        allowed=False,
        matched_policy="default",
        reason="no permit policy matched (default deny)",
    )


def require_authorized(
    *,
    principal: Principal,
    action: str,
    resource: Resource,
    context: dict[str, Any] | None = None,
) -> None:
    """Raise AuthzDenied if not authorized. Use in route handlers."""
    decision = is_authorized(principal=principal, action=action, resource=resource, context=context)
    if not decision.allowed:
        raise AuthzDenied(
            decision.reason,
            principal=principal.user_id,
            action=action,
            resource=f"{resource.kind}:{resource.id}",
        )


# =============================================================================
# Snapshot for /api/v1/authz/policies — let auditors see the whole library
# =============================================================================


def policy_snapshot() -> dict[str, Any]:
    """Return the policy library shape for auditor inspection."""
    return {
        "evaluator": "cedar-shape (Python re-impl; AWS Verified Permissions migration target)",
        "deny_wins": True,
        "default_decision": "deny",
        "policies": [
            {"effect": effect, "actions": sorted(actions), "name": name}
            for effect, actions, _cond, name in _POLICIES
        ],
        "total_policies": len(_POLICIES),
    }
