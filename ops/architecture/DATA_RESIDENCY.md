# ClinCase — Per-Tenant Data Residency

**Audience:** TriZetto delivery + customer compliance officers + EU/IN/UK regulators

The default ClinCase deployment runs in `ap-south-1` (Mumbai). For customers with data-residency obligations — French HDS, German DSGVO, UK ICO healthcare data rules, India's DPDP Act, US-payer regional preference — every domain row must be stored, processed, and retained inside their declared region.

This is a per-tenant property, not a per-deployment one.

## How it works

`org_quotas.data_region` (TEXT, default `ap-south-1`) declares the tenant's region. Every code path that touches tenant data routes by this column:

| Layer | How it routes by `data_region` |
|---|---|
| **API** | `app/auth/dependencies.py` injects `data_region` into the request context; downstream services read from it. |
| **DB writes** | Multi-region Aurora Global cluster; the customer's DSN points at the writer in their region (`Aurora Global` cross-region promotion is RPO≈1s). |
| **Bedrock** | Per-tenant `BEDROCK_MODEL_ID` env override; e.g. EU tenants resolve to `eu.anthropic.claude-sonnet-4-6` and AWS PrivateLink endpoint in `eu-west-1`. |
| **S3 audit lake** | Per-tenant bucket prefix; CRR replicates to peer regions only when allowed. |
| **TriZetto Gateway** | `TRIZETTO_GATEWAY_URL` per tenant; routed via Route 53 LBR to the closest TriZetto regional endpoint. |
| **Q Business** | `AMAZON_Q_REGION` per tenant. |
| **CloudWatch logs** | Per-region log groups; cross-region log shipping disabled by default. |
| **KMS** | Per-tenant multi-region key with `Replicas` constrained to allowed regions only. |

## Tier × Region matrix

`org_quotas.tier` ∈ {bronze, silver, gold} interacts with `data_region`:

| Tier | Region options | RPO/RTO | Bedrock model allowlist | WAF rate limit |
|---|---|---|---|---|
| **Bronze** | Single region (customer's choice) | RPO 5min · RTO 30min | Sonnet only (Haiku unavailable to keep costs predictable) | 10 req/s/IP |
| **Silver** | Single region + warm cross-region read replica | RPO 1min · RTO 5min | Sonnet + Haiku | 50 req/s/IP |
| **Gold** | Multi-region active/active (`ops/terraform/multi-region/`) | RPO 1s · RTO 60s | Sonnet + Haiku + (future) Nova | 200 req/s/IP |

The tier × region matrix is the column on which both pricing and SLA hinge. Customer onboarding (`ops/multi-tenant/ONBOARDING.md`) pinpoints the customer's tier on Day 0.

## Region routing decision tree

```
                           ┌─────────────────────┐
                           │ Request arrives at  │
                           │ ALB → API pod       │
                           └──────────┬──────────┘
                                      │
                                      ▼
                  ┌───────────────────────────────────┐
                  │ get_current_user(...)              │
                  │  → user.organization_id            │
                  │  → SELECT data_region, tier        │
                  │    FROM org_quotas WHERE org=...   │
                  └──────────┬────────────────────────┘
                             │
              ┌──────────────┼──────────────────┐
              ▼              ▼                  ▼
       data_region=     data_region=     data_region=
       'ap-south-1'     'eu-west-1'      'us-east-1'
              │              │                  │
              ▼              ▼                  ▼
       Aurora India    Aurora Frankfurt   Aurora N. Virginia
       Bedrock APAC    Bedrock EU         Bedrock US
       S3 ap-south-1   S3 eu-west-1       S3 us-east-1
       TriZetto IN     TriZetto EU        TriZetto US
```

## Compliance crosswalk

| Regulation | Effective | What it requires | How `data_region` satisfies it |
|---|---|---|---|
| **HIPAA** (US) | 1996 | PHI processed inside BAA-covered AWS regions | `us-east-1` / `us-west-2` are HIPAA-eligible |
| **DPDP Act 2023** (India) | 2024+ | Sensitive personal data of Indian residents stored in India by default | `ap-south-1` (Mumbai) |
| **GDPR + EU AI Act high-risk healthcare** | 2018 + Aug 2 2026 | EU resident data processed inside EEA | `eu-west-1` / `eu-central-1` |
| **HDS (Hébergeur de Données de Santé)** (France) | 2018 | Healthcare data on HDS-certified hosts | AWS HDS certification active in `eu-west-3` (Paris) |
| **UK Data Protection Act + ICO healthcare guidance** | 2018+ | Healthcare data on UK-regulated infrastructure | `eu-west-2` (London) |

## Cross-region operations that are explicitly forbidden

For a `data_region=eu-west-1` tenant, these operations FAIL HARD:

- Writing a `decisions` row to `ap-south-1` Aurora
- Logging PHI-containing prompt material to `us-east-1` CloudWatch
- Bedrock InvokeModel against a non-EU model_id
- S3 CRR replicating audit objects outside EEA without explicit cross-border-transfer agreement

The enforcement is a combination of:
1. **App-layer** — `data_region` checked before every external call
2. **IAM** — per-tenant role's `Resource:` ARNs scoped to the tenant's region
3. **VPC endpoint policy** — `aws:RequestedRegion` condition on Bedrock / S3 / KMS endpoints

## Onboarding a customer with data-residency requirements

Add to `ops/multi-tenant/ONBOARDING.md`:

```bash
# 1. Set the tenant's region during seed
INSERT INTO organizations (id, name, slug) VALUES ('orgEU01', 'Centene EU GmbH', 'centene-eu');
INSERT INTO org_quotas (organization_id, data_region, tier)
  VALUES ('orgEU01', 'eu-west-1', 'gold');

# 2. Provision per-tenant Bedrock Guardrail in the tenant's region
aws bedrock create-guardrail --region eu-west-1 ...

# 3. Provision per-tenant KMS key with Replicas constrained
terraform apply -var=tenant_data_region=eu-west-1 \
                 -var=allowed_replica_regions='["eu-central-1"]' \
                 ops/terraform/per-tenant-tenant.tf

# 4. Configure TriZetto Gateway URL for the tenant's region
PUT /api/v1/quotas/orgEU01 { "trizetto_gateway_url": "https://trizetto-eu.example.com" }
```

## What's deferred to post-pilot

- ⚪ Per-region Bedrock Guardrail provisioning automation (`ops/terraform/per-tenant/`)
- ⚪ Per-region KMS multi-region key Terraform (`ops/terraform/per-tenant-kms/`)
- ⚪ Per-region CDN edge configuration (`ops/terraform/cloudfront-multi-region/`)
- ⚪ Cross-region failover for Gold-tier tenants (`ops/sre/RUNBOOK.md` § INC-002 generalization)

These land at the first Facets/QNXT customer that requires them. The schema and routing primitives already in place.
