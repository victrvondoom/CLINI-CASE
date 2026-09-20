# ClinCase — Postgres Row Level Security (RLS)

**Status:** Accepted (round-12)
**Audience:** Customer security team · auditor verifying multi-tenant isolation depth

## Why RLS is required, not optional

Round-9 multi-tenant isolation was app-side only:
```sql
SELECT * FROM cases WHERE organization_id = $1 AND id = $2
```

This works WHEN the application code is correct. It is **broken** when:
1. SQL injection slips past argument binding
2. A new query forgets the `organization_id` clause
3. A SRE runs an ad-hoc `psql` query without remembering tenant scope
4. An ORM `.filter()` chain misses an obvious case
5. A future code path calls `cur.execute(raw_sql)` — ALL of them must remember

Every Tier-1 payer security questionnaire asks: *"What stops a SQL bug from
returning another customer's data?"*

The honest answer for round-9 was "code review." That's not enough.

## Decision

Postgres Row Level Security as the second wall:
- Every multi-tenant table has `ENABLE ROW LEVEL SECURITY`
- Every multi-tenant table has policy `clincase_tenant_isolation`
- The policy filters rows by `organization_id = current_setting('clincase.organization_id')`
- ClinCase pods connect as `clincase_app` (a NOLOGIN role granted to the
  IAM-authenticated DB user); this role has RLS enforced
- The migration job + janitor connect as `clincase_migrator` (BYPASSRLS) for
  cross-tenant maintenance ops only

## How a request's tenant is bound

`TenantContextMiddleware` (`app/api/tenant_context_middleware.py`) decodes
the JWT, extracts `organization_id`, and binds it to a contextvar at the
start of every request.

The DB call layer (`app.db`) reads the contextvar and issues
`SET LOCAL clincase.organization_id = $1` before each statement. RLS then
fires automatically.

## Migration

`backend/alembic/versions/0002_row_level_security.py` enables RLS on:
- cases
- case_jobs
- case_runs
- agent_runs
- decisions
- appeals
- evidence_packs
- llm_invocations
- org_quotas
- reviewer_actions
- event_outbox

Apply: `make migrate`

## Defensive invariant: closed by default

If `TenantContextMiddleware` doesn't run for some reason (e.g., a route
forgets it), the contextvar is `None`, `current_setting()` returns NULL,
and the policy `WHERE organization_id = NULL` returns 0 rows.

That means: *misconfiguration fails empty, not leaky.* Both cases produce
empty results, which the application surfaces as 404. No row leaks.

## What we tested

```sql
-- Tenant A
SET LOCAL clincase.organization_id = 'org_demo';
SELECT count(*) FROM cases;     -- N rows for org_demo

-- Tenant B
SET LOCAL clincase.organization_id = 'org_humana';
SELECT count(*) FROM cases;     -- M rows for org_humana

-- Cross-attempt
SET LOCAL clincase.organization_id = 'org_demo';
SELECT * FROM cases WHERE organization_id = 'org_humana';   -- 0 rows
```

## What's NOT covered (and why)

- **Reference tables** (e.g., `payer_policies`, `cms_clauses`) — not
  multi-tenant. Plain SELECT for everyone.
- **Audit aggregation jobs** — run as `clincase_migrator` so cross-tenant
  rollups (compliance scorecard, FinOps dashboard) work. Documented and
  audit-logged.
- **In-memory caches** — Redis cache is keyed by `(org_id, ...)`. RLS doesn't
  reach there; eviction logic in `app.agents.framework.cache` ensures keys
  don't leak. Defense in depth: AWS ElastiCache + per-tenant key prefix.

## Sources

- Postgres RLS docs — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- AWS RDS RLS guide — https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/
- AWS Well-Architected — *Implement multi-tenant isolation*
