# ClinCase — Cell-Based Architecture (ADR-0009)

**Status:** Accepted (round-11; deployed-1-cell today, cell-1 + cell-2 lit at first multi-region customer)
**Audience:** Cognizant TriZetto solution architect · AWS account team · auditor verifying blast-radius bounds

## Context

Round-9 architecture is a single-region, single-Aurora-primary, single-K8s-namespace deployment. That's correct for the first 1–10 pilot customers (≤ 50K cases/day). Above that, a single bad query, a single 0-day, or a single noisy tenant becomes a *global* incident.

Industry-standard pattern for multi-tenant SaaS at scale: **cells** (sometimes called pods, shards, fleets). AWS Identity, Slack, Stripe, Cloudflare all use the cell pattern. From the AWS docs ([Reducing the Scope of Impact with Cell-Based Architecture](https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/)): *"Cell-based architectures partition workload deployments across cells. Each cell can serve a subset of users."*

## Decision

Adopt the cell pattern with these properties:

| Property | ClinCase cell |
|---|---|
| Deployment unit | 1 Aurora cluster + 1 K8s namespace + 1 worker fleet + 1 Bedrock IAM role + 1 KMS CMK |
| Tenant pinning | consistent-hash by `organization_id`, optionally restricted by `data_region` |
| Capacity per cell (soft) | 200 tenants OR 50K cases/day, whichever is lower |
| Cells per region | 1 today, more added horizontally |
| Blast radius bound | at most 200 tenants affected by one cell's outage |

A tenant's cell is *durable*: once pinned, the tenant stays in that cell unless explicitly migrated. The router (`backend/app/cells.py`) implements this via SHA-256 consistent hashing — cell membership is derived, not stored, until a `cells.tenant_to_cell` table lands.

## Three deployed cells in the model

Today (round-11) the cell registry hard-codes:

| Cell ID | Region | K8s namespace | Aurora cluster ARN |
|---|---|---|---|
| `cell-0-apac-1` | ap-south-1 | clincase | arn:aws:rds:ap-south-1:.../cluster:clincase-cell0 |
| `cell-1-us-1`   | us-east-1  | clincase-cell1 | arn:aws:rds:us-east-1:.../cluster:clincase-cell1 |
| `cell-2-eu-1`   | eu-west-1  | clincase-cell2 | arn:aws:rds:eu-west-1:.../cluster:clincase-cell2 |

Cell-0 is the only one *currently provisioned*. Cell-1 + Cell-2 light up at the first multi-region customer.

## Implementation summary

| Component | Where |
|---|---|
| Cell registry + lookup | `backend/app/cells.py` |
| `X-ClinCase-Cell-Id` response header | `backend/app/api/cell_router_middleware.py` |
| Cell snapshot for ops endpoints | `cells.cell_snapshot()` |
| Architecture descriptor surfacing | `app/api/architecture.py` Layer 5 |

The middleware decodes the JWT (unsafe — full validation happens later) to extract `organization_id` + `data_region`, resolves the cell, and stamps the response header. Customer SRE filing a support ticket can hand us:

- `X-Request-Id` (already shipped round 8)
- `X-ClinCase-Cell-Id` (this ADR)
- `X-API-Version` (round 10)
- `X-ClinCase-Build-Sha` (round 8)

— enough for us to triage in seconds.

## Migration story (today → cell-aware)

1. **Today:** middleware emits `X-ClinCase-Cell-Id` based on hash. The single deployment ignores the cell value at routing time.
2. **First customer in `eu-west-1`:** apply `ops/terraform/multi-region/` for that cell; deploy `clincase-cell2` namespace; the cell-router still resolves consistently. Customer's writes hit cell-2's Aurora.
3. **First > 50K cases/day customer:** add `cell-3-apac-2` in ap-south-1; reshard heavy tenants. Re-pin requires DB migration job.
4. **First 100K-tenant horizon:** introduce `cells.tenant_to_cell` table and a router that 307-redirects to the right cell's ALB. Hash-based pin becomes the bootstrap pin only.

## Trade-offs

### Why not "one cell per tenant" (full isolation)?
Cost — a separate Aurora cluster per tenant is ~$200/month/tenant. 200-tenant shared cell is ~$1/tenant/month for the same isolation guarantee.

### Why not microservices?
The cell pattern operates at a *higher* level than microservices. Each cell IS a full ClinCase (api + worker + db + cache). Microservices would slice along agent boundaries and break the multi-agent transactional invariant we worked hard to maintain.

### Why hash-based pinning + a future table?
Hash-based is correct for greenfield. A table becomes necessary when:
- Tenants need to migrate (e.g., a tenant outgrows a cell)
- Cells are removed (re-pinning is otherwise unbounded)
- Manual override is required (compliance / political)

Most production cell systems use both: hash for default, table for overrides.

## Verifiable today

- `GET /api/v1/architecture/layers` → Layer 5 lists `cells.py` + `cell_router_middleware.py`
- A logged-in user's response carries `X-ClinCase-Cell-Id` (via dev-tools / cURL `-i`)
- `from app.cells import list_cells, cell_for_organization` returns 3 cells

## Sources

- AWS Well-Architected — *Reducing the Scope of Impact with Cell-Based Architecture* (https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/)
- Slack engineering — *Scaling Slack's job queue* (cells / shards)
- Stripe engineering — *Online migrations at scale*
