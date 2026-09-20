"""Fine-grained authorization layer.

Round-9 RBAC is role-only: `coordinator | reviewer | admin`. That's correct
for the demo cohort. It's NOT enough for a Tier-1 payer customer:

  • A nurse case manager needs access to oncology cases ONLY in their
    assigned LOB (line-of-business).
  • A medical director can see all cases in their MSO, but NOT cases at
    other MSOs even within the same payer.
  • A reviewer can sign off on AGENT-decided cases, but NOT cases that
    were already PHYSICIAN-signed (CA SB-1120 conflict-of-interest).

These are *attribute-based* rules — you can't express them in role-only RBAC.

The industry pattern is:
  • AWS uses **Cedar** (the policy language behind AWS Verified Permissions)
  • Cloud-native open-source uses **OPA / Rego**
  • Both support principal × action × resource × context evaluation

ClinCase uses the Cedar shape (so future migration to AWS Verified
Permissions is a config flip). The actual evaluator today is a small
Python implementation of Cedar's core semantics — full Cedar would land
post-pilot when the policy library exceeds ~50 rules.

Pairs with: ops/architecture/AUTHZ_CEDAR.md
"""
from app.authz.cedar import (
    AuthzDecision,
    AuthzDenied,
    Principal,
    Resource,
    is_authorized,
    policy_snapshot,
    require_authorized,
)

__all__ = [
    "AuthzDenied",
    "AuthzDecision",
    "Principal",
    "Resource",
    "is_authorized",
    "policy_snapshot",
    "require_authorized",
]
