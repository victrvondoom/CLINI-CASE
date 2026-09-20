# ClinCase — Fine-Grained Authorization (Cedar shape)

**Status:** Accepted (round-11)
**Audience:** Cognizant TriZetto / payer security teams · auditor verifying authz boundary

## Why we need attribute-based authorization

Round-9 RBAC was role-only. That's correct for demo. It's wrong for real customers because:

| Real-world rule | Role-only RBAC says | Cedar / ABAC says |
|---|---|---|
| Nurse case manager sees oncology cases in HER assigned LOB only | "reviewer can see cases" — too coarse | `principal.lob == resource.lob` |
| CA SB-1120: physician signoff overrides; reviewer cannot countersign | "reviewer can sign-off" — wrong | `forbid case:sign-off when resource.signed_by_physician == true` |
| Cross-tenant access blocked | enforced at app code level | enforced declaratively, audit-readable |
| Admin-only audit log read | can be forgotten in code | `forbid audit_log:read when principal.role != "admin"` |

These aren't hypothetical. Every Tier-1 payer security questionnaire asks them.

## ClinCase's choice — Cedar shape, not Cedar (yet)

Cedar is AWS's policy language behind AWS Verified Permissions. The migration target is "ClinCase's policies are Cedar policies, evaluated by AWS Verified Permissions."

Today (round-11) we ship a **Cedar-shaped Python evaluator** — same `(principal, action, resource, context)` shape, same `permit / forbid` semantics, same deny-wins ordering. Future migration is config + secrets, not application redesign.

When does this flip to AWS Verified Permissions?
- Policy count exceeds ~50 rules (today: 8)
- Per-evaluation latency budget falls below 1ms (today: ~10µs in-process)
- Customer asks for it explicitly (e.g., audit team requires AVP for compliance)

## The policy library (today)

| # | Effect | Actions | Condition | Name |
|---|---|---|---|---|
| 1 | forbid | case:read/update/delete/run/resume | cross-org | `deny-cross-org-case-access` |
| 2 | forbid | case:sign-off | already physician-signed | `deny-double-signoff-CA-SB1120` |
| 3 | forbid | case:sign-off | role=coordinator | `deny-coordinator-signoff` |
| 4 | forbid | audit_log:read | role≠admin | `deny-audit-log-non-admin` |
| 5 | permit | case:read/update/run/resume | same-org + standard role | `permit-same-org-case-rw` |
| 6 | permit | case:sign-off | reviewer/admin + not physician-signed | `permit-reviewer-signoff` |
| 7 | permit | audit_log:read | role=admin | `permit-admin-audit-read` |
| 8 | permit | case:scope-by-lob:read | LOB matches OR no LOB attribute (legacy) | `permit-lob-scoped-case-read` |
| 9 | permit | evidence_pack:read | reviewer/admin | `permit-evidence-pack-reviewer-admin` |

## Implementation

```
backend/app/authz/
├── __init__.py        # public re-exports
└── cedar.py           # evaluator + policy library
backend/app/api/authz.py   # GET /api/v1/authz/policies (admin-only)
```

## Sample call site (illustrative)

```python
from app.authz import Principal, Resource, require_authorized

@router.post("/cases/{case_id}/sign-off")
async def sign_off(case_id: str, user = Depends(get_current_user)):
    case = await get_case(case_id)
    require_authorized(
        principal=Principal(
            user_id=user["id"],
            organization_id=user["organization_id"],
            role=user["role"],
            attributes={"lob": user.get("lob")},
        ),
        action="case:sign-off",
        resource=Resource(
            kind="case",
            id=case_id,
            organization_id=case["organization_id"],
            attributes={"signed_by_physician": case.get("signed_by_physician")},
        ),
    )
    # ... actually do the signoff
```

`AuthzDenied` exception bubbles up. The framework converts to HTTP 403 with the matched policy name in the response (so auditors can debug).

## Why deny-wins

CIS / NIST / Cedar / OPA / IAM all default to deny-wins. A coding mistake that adds an over-broad permit policy doesn't accidentally grant access to a class of operations that already has an explicit forbid. This is the correct default for healthcare, finance, defense.

## What we DIDN'T do (and why)

- **Per-record ACL table** — too much storage, too much UPDATE traffic. Cedar policies + computed attributes are cheaper and more auditable.
- **OPA / Rego** — Rego is more expressive but Cedar's restricted vocabulary is *good* for auditability. Cedar is also the AWS-managed path.
- **Synchronous AVP calls** — today's < 1µs in-process eval is fine. AVP is ~5ms (network); we'll cache decisions for 60s when we migrate.

## Sources

- AWS Cedar — https://www.cedarpolicy.com/
- AWS Verified Permissions — https://aws.amazon.com/verified-permissions/
- NIST SP 800-162 ABAC — https://nvlpubs.nist.gov/nistpubs/specialpublications/NIST.sp.800-162.pdf
- CA SB-1120 (Physicians Make Decisions Act) — https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB1120
