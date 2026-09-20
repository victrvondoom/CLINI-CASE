# ClinCase — API Versioning & Deprecation Policy

**Audience:** Cognizant TriZetto product team · ClinCase API consumers · joint Cognizant–AeroFyta integration engineering

ClinCase's HTTP API is consumer-facing. Customers integrate against it for case submission, status polling, evidence-pack export, and TriZetto Gateway round-tripping. Versioning + deprecation discipline is non-negotiable.

## Versioning scheme

URL-path versioning: `/api/v{N}/...`

Today every public endpoint is `/api/v1/`. The version in the path is the **major** version; backwards-compatible additions (new optional fields, new endpoints) do NOT bump the version.

We follow [Semantic Versioning](https://semver.org/) for the *implementation* (`/api/v1/version` reports the semver), but URL versions are major-only.

## What constitutes a breaking change (requires `/v2`)

- Removing a field from a response
- Changing the type of a field (e.g. `integer` → `string`)
- Removing a query parameter or making a previously optional one required
- Renaming an endpoint
- Changing HTTP status codes for documented success/error paths
- Tightening validation in a way that previously valid requests now fail
- Removing a response shape variant

What is NOT a breaking change:
- Adding new optional fields
- Adding new query parameters with backwards-compatible defaults
- Adding new endpoints
- Adding new error response variants for previously-undocumented error conditions
- Bug fixes that bring behavior into alignment with documentation

## Deprecation timeline

When `/v2` is introduced, `/v1` enters the deprecation pipeline:

| Phase | Duration | What happens to `/v1` |
|---|---|---|
| **Coexist** | Day 0 → Day 90 | `/v1` and `/v2` both fully supported; new clients use `/v2` |
| **Soft-deprecated** | Day 90 → Day 180 | `/v1` responses include `Sunset` header (RFC 8594) + `Deprecation` header; SRE alert when a customer is still on `/v1` |
| **Read-only** | Day 180 → Day 270 | Mutating `/v1` endpoints return HTTP 410; read endpoints still work |
| **Sunset** | Day 270 | All `/v1` endpoints return HTTP 410 with `Link: </api/v2/...>; rel="successor-version"` |

Total deprecation runway: **9 months minimum** from `/v2` GA. This is the AWS API Gateway / Stripe / Twilio industry standard.

## Header conventions

Every response includes:

| Header | Purpose |
|---|---|
| `X-API-Version` | The major version that handled the request (e.g. `v1`) |
| `X-ClinCase-Build-Sha` | The git SHA serving the response (from `/api/v1/version`) |
| `X-Request-Id` | Echoed from request OR minted; used for SRE incident correlation |
| `Sunset` | (deprecated only) RFC 8594 sunset date in HTTP-date format |
| `Deprecation` | (deprecated only) `true` + version-supercedes link |
| `Link` | `</api/v2/cases>; rel="successor-version"` for successor pointers |

## Per-tenant grandfathering

Some Cognizant Gold-tier customers may negotiate longer deprecation windows in their MSA. The mechanism:

```sql
ALTER TABLE org_quotas ADD COLUMN api_version_grandfather_until TIMESTAMPTZ;
```

When set, the API serves `/v1` to that tenant beyond the global Sunset date, until `api_version_grandfather_until`. SRE alert + AeroFyta engineering review per renewal cycle.

## How a `/v2` rollout looks operationally

```
T-30d:  /v2 spec published in ops/api/v2-spec.yaml + reviewed by Cognizant TriZetto product
T-14d:  /v2 endpoints deployed to staging; integration tests against TriZetto staging Gateway
T-7d:   /v2 deployed to production behind a feature flag (TENANT_OPT_IN_V2)
T-0d:   /v2 generally available; /v1 enters Coexist phase
T+90d:  /v1 enters Soft-deprecated phase; Sunset/Deprecation headers added
T+180d: /v1 mutating endpoints return 410; read endpoints continue
T+270d: /v1 fully sunset; all endpoints return 410 except grandfathered tenants
```

## Currently supported versions

| Version | Status | Notes |
|---|---|---|
| `/api/v1` | **Stable** | Every endpoint listed in `docs/INDEX.md` § "Backend code" |

`/api/v2` is not yet planned. The next major version would address breaking changes that come up during the first Cognizant pilot — most likely:

- Multi-tenant Bedrock model selection in the response (today implicit; v2 makes it explicit)
- Pagination schema standardization (today inconsistent across `list_cases` / `list_jobs`)
- Standardized error envelope (today some endpoints use FastAPI defaults, others use custom)

## Why this matters

A Cognizant TriZetto customer's CTO asks: *"What's your API deprecation policy?"* — without this doc, the answer is silence. Industry-grade systems have published deprecation timelines. Stripe, Twilio, AWS, GitHub — every Tier-1 API publishes this exact shape of policy.

## Sources

- Semantic Versioning: https://semver.org/
- RFC 8594 (Sunset HTTP header): https://datatracker.ietf.org/doc/html/rfc8594
- Stripe API versioning: https://stripe.com/docs/upgrades
- AWS API Gateway versioning: https://docs.aws.amazon.com/whitepapers/latest/best-practices-api-gateway-private-apis-integration/api-versioning.html
