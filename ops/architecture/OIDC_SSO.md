# ClinCase — OIDC SSO Integration (ADR-0010)

**Status:** Accepted (round-11 scaffold; live wiring at first customer)
**Audience:** Customer IdP team (Okta / Azure AD / Ping / Auth0) · partner security · auditor

## Why OIDC

Round-9 auth was email + bcrypt + JWT. Correct for demo + internal admin. NOT correct for any Tier-1 payer because:

1. **Their IAM team rejects all non-SSO credentials in production**
2. **MFA / conditional access / session lifetime must enforce at IdP**, not at ClinCase
3. **SCIM provisioning + offboarding** must come from the IdP
4. **Audit log of WHO authenticated** must live in the IdP, not in ClinCase

## Decision

ClinCase is an OIDC Relying Party. Customers point us at any OIDC-compliant IdP via the discovery URL. We do NOT build per-customer auth integrations.

## Supported IdPs (any one of)

| IdP | Discovery URL pattern |
|---|---|
| Okta | `https://{tenant}.okta.com/.well-known/openid-configuration` |
| Azure AD | `https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration` |
| Google Workspace | `https://accounts.google.com/.well-known/openid-configuration` |
| Ping Identity | `https://{tenant}.pingidentity.com/.well-known/openid-configuration` |
| Auth0 | `https://{tenant}.auth0.com/.well-known/openid-configuration` |
| AWS IAM Identity Center | `https://identitycenter.amazonaws.com/...` |

## Flow

**Authorization Code Flow + PKCE (RFC 7636).** No implicit flow, no resource-owner password flow.

```
Browser                            ClinCase API                IdP
   │                                    │                       │
   │  1. GET /api/v1/auth/oidc/login    │                       │
   ├───────────────────────────────────►│                       │
   │                                    │  2. fetch discovery   │
   │                                    ├──────────────────────►│
   │  3. 302 → authorize_url            │                       │
   │     (state + PKCE challenge)       │                       │
   │◄───────────────────────────────────┤                       │
   │                                                            │
   │  4. log in + consent (MFA at IdP)                          │
   ├───────────────────────────────────────────────────────────►│
   │                                                            │
   │  5. 302 → /api/v1/auth/oidc/callback?code=...&state=...   │
   │◄───────────────────────────────────────────────────────────┤
   │                                                            │
   │  6. GET /api/v1/auth/oidc/callback │                       │
   ├───────────────────────────────────►│                       │
   │                                    │  7. exchange code     │
   │                                    │     + PKCE verifier   │
   │                                    ├──────────────────────►│
   │                                    │  8. id_token + access │
   │                                    │◄──────────────────────┤
   │                                    │  9. validate id_token │
   │                                    │     (sig, nonce, exp) │
   │                                    │ 10. upsert user row   │
   │                                    │ 11. mint ClinCase JWT  │
   │ 12. 302 → /#access_token=...       │                       │
   │◄───────────────────────────────────┤                       │
```

## Configuration (env)

```bash
OIDC_DISCOVERY_URL=https://acme.okta.com/.well-known/openid-configuration
OIDC_CLIENT_ID=0oab123abc456
OIDC_CLIENT_SECRET=*****          # from AWS Secrets Manager in production
OIDC_REDIRECT_URI=https://api.clincase.example.com/api/v1/auth/oidc/callback
OIDC_SCOPES=openid profile email offline_access groups
OIDC_ORGANIZATION_ID_CLAIM=https://clincase.com/claims/organization_id
OIDC_ROLE_CLAIM=https://clincase.com/claims/role
```

The `organization_id` and `role` claims are negotiated with each customer's IdP team — they map IdP groups to ClinCase roles. Example claim mapping in Okta:

```
ClinCase coordinator role := groups contains 'ClinCase_Coordinators'
ClinCase reviewer role    := groups contains 'ClinCase_Reviewers'
ClinCase admin role       := groups contains 'ClinCase_Admins'
```

## What the scaffold ships today (round-11)

- `app/auth/oidc.py` — full RP implementation, PKCE, state store, token exchange, ID-token claim extraction
- `app/api/auth_oidc.py` — three routes:
  - `GET /api/v1/auth/oidc/status` (unauth, frontend probe)
  - `GET /api/v1/auth/oidc/login`
  - `GET /api/v1/auth/oidc/callback`
- Routes are 503 unless OIDC env is set — safe to deploy without a configured IdP

## What's deferred to first customer cutover

- ⚠ **JWKS-based ID token signature validation** — today decodes only. Lands at first customer with their JWKS endpoint. Implementation: `pyjwt` + `httpx` + cache JWKS for 10 min.
- ⚠ **Refresh token rotation** — today drops the refresh token; lands when sessions exceed 1 hour
- ⚠ **SCIM provisioning** — today auto-upserts on login (JIT). SCIM endpoint lands at first customer that requires deprovisioning automation.
- ⚠ **Logout + RP-Initiated Logout** — today UI-side localStorage wipe; full RP-Initiated Logout (OIDC RP-Initiated Logout 1.0) lands at first customer.

Each is deferrable — none block a pilot.

## Sources

- OIDC Core 1.0 — https://openid.net/specs/openid-connect-core-1_0.html
- OIDC RP-Initiated Logout — https://openid.net/specs/openid-connect-rpinitiated-1_0.html
- RFC 7636 PKCE — https://datatracker.ietf.org/doc/html/rfc7636
- AWS Cognito OIDC docs — https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-oidc-flow.html
