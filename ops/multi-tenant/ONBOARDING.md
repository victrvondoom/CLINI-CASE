# ClinCase — Multi-Tenant Customer Onboarding

**Audience:** Cognizant TriZetto delivery + AeroFyta deployment engineering

This is the playbook for spinning up a new Cognizant Facets / QNXT customer on ClinCase. Designed to be repeatable in a single business day per customer once the first pilot is in flight.

---

## Tenant model

ClinCase is multi-tenant by construction. The boundary is `organization_id` (TEXT) on every domain row:

| Table | Tenant column |
|---|---|
| `users` | `organization_id` |
| `cases` | `organization_id` |
| `agent_runs` | scoped via `case_id → cases.organization_id` |
| `decisions`, `appeals`, `reviewer_actions` | scoped via `case_id` |
| `case_jobs` | `organization_id` (queue.py) |
| `org_quotas` | `organization_id` (quotas.py) |
| `agent_response_cache` | `organization_id` (cache key includes it) |

Cross-org reads are blocked at the API layer (`get_current_user(...)` injects the caller's org; queries always include `WHERE organization_id = $1`).

---

## Per-tenant configuration surface

Per-customer settings that vary across deployments and are NOT hardcoded:

| Configuration | Source | Per-tenant? |
|---|---|---|
| `BEDROCK_MODEL_ID` (primary) | env / `app/config.py` | ✅ optional override per tenant |
| `BEDROCK_HAIKU_MODEL_ID` (fallback) | env / `app/config.py` | ✅ optional override |
| `BEDROCK_GUARDRAIL_ID` | env / `app/config.py` | ✅ **required override per tenant** (PHI policy varies) |
| `BEDROCK_KB_ID` | env / `app/config.py` | ✅ optional override (customer's own KB) |
| `USE_AMAZON_Q` + `AMAZON_Q_APPLICATION_ID` + `AMAZON_Q_INDEX_ID` | env / `app/config.py` | ✅ override when customer's policy library is in M365/SharePoint |
| `TRIZETTO_GATEWAY_URL` + `TRIZETTO_GATEWAY_TOKEN` | env / `app/config.py` | ✅ per-customer Gateway URL |
| `HITL_CONFIDENCE_THRESHOLD` | env / `app/config.py` | ✅ override (state-law-driven) |
| `daily_case_limit` + `monthly_case_limit` | `org_quotas` table | ✅ per-tenant via `PUT /api/v1/quotas/{org_id}` |
| **AWS KMS key ARN** for envelope encryption | Terraform module per tenant | ✅ per-tenant key (multi-region replica) |
| **Custom domain + ALB cert** | Route 53 + ACM | ✅ per-tenant |

---

## Day-0 onboarding playbook

### Pre-checks
- [ ] Customer signed BAA with AWS (HIPAA covered services agreement)
- [ ] Customer signed BAA with AeroFyta
- [ ] Customer's `organization_id` allocated (snake_case, e.g. `centene_ma_oncology`)
- [ ] Customer's MA member count + current Star Rating recorded for Star projection

### Provision per-tenant AWS resources
- [ ] Apply `ops/terraform/per-tenant-tenant.tf` (TODO module — clone from `multi-region/rds.tf` KMS pattern):
  - per-tenant KMS multi-region key
  - per-tenant Bedrock Guardrail (CloudFormation)
  - per-tenant S3 audit bucket with CRR to secondary region
- [ ] Output: `BEDROCK_GUARDRAIL_ID` for the customer's PHI/redaction policy

### Provision per-tenant TriZetto integration
- [ ] Cognizant TriZetto delivery team configures the AI Gateway to accept ClinCase submissions for this tenant
- [ ] Output: `TRIZETTO_GATEWAY_URL` + `TRIZETTO_GATEWAY_TOKEN` (rotated quarterly)
- [ ] ClinCase MCP server bearer token registered with the Gateway (rotated quarterly)

### Provision per-tenant policy corpus
**Path A (simple):** Bedrock Knowledge Base — customer policy PDFs ingested to S3 → Bedrock KB sync → `BEDROCK_KB_ID`.
**Path B (preferred for TriZetto customers):** Amazon Q Business — customer's existing M365/SharePoint/Confluence connector. Toggle `USE_AMAZON_Q=true` + `AMAZON_Q_APPLICATION_ID` + `AMAZON_Q_INDEX_ID`.

### Seed the tenant in ClinCase
- [ ] `INSERT INTO organizations (id, name, slug) VALUES (...)`
- [ ] First admin user via `POST /api/v1/auth/users` (admin role)
- [ ] Set quotas: `PUT /api/v1/quotas/{organization_id}` with daily + monthly caps
- [ ] Smoke-run one synthetic case end-to-end via `POST /api/v1/demo-fixtures/{name}/create-case` + `POST /cases/{id}/run-async`
- [ ] Verify Evidence Pack returns valid bundle with bundle_sha256

### Verify Day-1 readiness
- [ ] `GET /api/v1/compliance/org` returns 100% TAT compliance, 100% SB-1120 (no denies yet — vacuously true), 100% audit completeness
- [ ] `GET /api/v1/business-value/org` returns 0 (no cases yet — expected)
- [ ] `GET /api/v1/foundry/manifest` returns the per-tenant Bedrock model_ids
- [ ] Datadog SLO monitor created from `ops/sre/SLO.yaml`

---

## Per-tenant isolation model

| Boundary | Mechanism |
|---|---|
| **Data** | `organization_id` enforced in every API query; cross-org reads return 404 (don't leak existence) |
| **PHI** | Per-tenant `BEDROCK_GUARDRAIL_ID` — customer's PHI policy applied to every model invocation |
| **Encryption** | Per-tenant KMS multi-region key; tenant's IAM role can decrypt; everyone else denied |
| **Compute** | Same EKS cluster (cost-efficient at < 100 customers); per-tenant namespace at scale; **AWS Lambda Tenant Isolation Mode** ([GA early 2026](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)) for Firecracker MicroVM hardware isolation when a customer requires it |
| **Network** | NetworkPolicy locks egress to VPC + Bedrock VPC endpoint; no public internet for PHI |
| **LLM cost** | Per-tenant `BudgetTracker` + per-org daily/monthly quotas + Bedrock Provisioned Throughput shared across tenants |
| **Audit trail** | `agent_runs` rows scoped via `case_id → cases.organization_id`; Evidence Pack endpoint org-scoped |

---

## Per-tenant config endpoint (introspection)

`GET /api/v1/foundry/manifest` returns the live per-tenant config — model_ids, region, guardrail_id, KB_id, Q Business app/index ids, Gateway URL. Customer's compliance officer queries this to verify what's configured.

For a customer asking *"what model is reasoning over my PHI?"*: `GET /api/v1/responsible-ai/model-card` returns the live model card with the Bedrock model_ids in use.

---

## Customer-of-customer isolation (sub-tenants)

For a Cognizant TriZetto deployment that resells ClinCase to *its* downstream payers (e.g., a Cognizant-managed BPO that runs PA for multiple regional Blue plans), each downstream payer should be its own `organization_id`. The Cognizant tenant is the "platform admin" tier; downstream payers are the operational tier.

Tactical: don't introduce a third level (sub-org). Just allocate one `organization_id` per actual data-isolation boundary. Cognizant's reporting can roll up across organization_ids it manages via a future `partner_id` join table — out of scope for the first pilot.

---

## Onboarding effort budget

A repeatable customer onboarding (after the first pilot) targets:

| Phase | Owner | Duration |
|---|---|---|
| BAA + procurement | Customer + AeroFyta legal | 5–10 business days |
| Per-tenant AWS Terraform apply | AeroFyta SRE | 30 min (apply already-vetted modules) |
| TriZetto Gateway configuration | Cognizant TriZetto delivery | 1–2 business days |
| Policy corpus ingestion (Bedrock KB OR Q Business connector) | Customer IT + AeroFyta | 1–3 business days |
| Tenant seed + smoke | AeroFyta deployment eng | 1 hr |
| First case live | Customer clinical ops | 30 min |
| **Total customer-onboarding** (after the first one is set up) | | **~7–15 business days end-to-end** |

That's the velocity Cognizant Agent Foundry's Scale stage targets. ClinCase is engineered to hit it.

---

## Sources

- [AWS Lambda Tenant Isolation Mode (early 2026)](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)
- [Redis — Multi-tenant data isolation patterns](https://redis.io/blog/data-isolation-multi-tenant-saas/)
- [AWS — HIPAA on AWS](https://aws.amazon.com/compliance/hipaa-compliance/)
