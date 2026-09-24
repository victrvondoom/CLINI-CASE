# ClinCase — Industrialization Checklist

**Aligned 1:1 with the Agent Foundry 4-stage methodology**
(Discover → Design → Build → Scale)

This is the gating document for *"is ClinCase production-grade for a TriZetto customer Monday?"* Each gate has explicit acceptance criteria + the artifact that proves it.

---

## Stage 1 · Discover ✅

**Foundry definition:** AI-driven process mining surfaces automation opportunities. Identify the use case, baseline the cost, quantify the ROI band.

| Gate | Criterion | Evidence |
|---|---|---|
| Use case identified | One named workflow with measurable cycle-time + error rate | Oncology PA · `README.md` § Why ClinCase |
| Industry baseline established | Manual cost / case · time / case · denial rate | AMA $1,500 / 18 min · `ops/architecture/BUSINESS_USE_CASE.md` |
| Regulatory forcing function | At least one in-force regulation that *requires* automation | CMS-0057-F § IV.B.1 (live Jan 1 2026) · CA SB 1120 |
| Competitive benchmark | Public ROI numbers from a peer deployment | Elevance Health OS 70% denial reduction · Summit Health 42% PA-time reduction |
| Star Ratings linkage | Direct $$ tied to Star measure(s) the agent influences | $1.26B/half-star at Humana scale · `app/business_value/star_ratings.py` |

---

## Stage 2 · Design ✅

**Foundry definition:** Define agent roles + frameworks + change-management plan.

| Gate | Criterion | Evidence |
|---|---|---|
| Agent inventory locked | Named parents + sub-agents + reflection thresholds + model sizes | 7 parents, 22 sub-agents · `app/agents/manifest.py` · live at `/api/v1/agents/manifest` |
| Schemas declared | Pydantic v2 input + output for every agent | `app/agents/<parent>/schemas.py` |
| Lifecycle declared | Single `Agent[I,O]` base class with shared invoke() | `app/agents/framework/agent.py` |
| Guardrail surface declared | Schema · PHI · Citation · Token-budget guardrails attached | `app/agents/framework/guardrails.py` · per-agent declared |
| Foundry manifest published | YAML manifest with Discover/Design/Build/Scale labeling | `ops/agent-foundry/agent-foundry-manifest.yaml` |
| Neuro-SAN compatible | AAOSA-format network definition | `ops/neuro-san-integration/clincase-network.hocon` |
| Responsible AI card | NIST AI RMF + ISO 42001 + EU AI Act + AWS AI Service Card structure | `app/api/responsible_ai.py` · live at `/api/v1/responsible-ai/model-card` |
| Change-management plan | HITL gate + reviewer queue + audit trail | `app/graph/build.py` review_gate node · `app/api/cases.py` resume endpoint |

---

## Stage 3 · Build ✅

**Foundry definition:** Multi-agent orchestration + partner-tech integration.

| Gate | Criterion | Evidence |
|---|---|---|
| Multi-agent orchestration runs end-to-end | Live LangGraph DAG completes a case in < 90s p95 | SLO `decision-tat` in `ops/sre/SLO.yaml` |
| Bedrock + Sonnet 4.6 integration | Production-grade model wrapper with fallback escalation | `app/agents/framework/models.py` ModelRouter · `app/llm/bedrock_client.py` |
| MCP server | JSON-RPC 2.0 MCP-compliant tool surface | `app/mcp/server.py` · `/mcp` endpoint |
| TriZetto AI Gateway adapter | Facets v3 + QNXT v2 events with tamper-evident hashes | `app/integrations/trizetto/` · `POST /api/v1/integrations/trizetto/submit` |
| Amazon Q Business connector | Drop-in alternative to Bedrock KB | `app/agents/policy_retriever/sub_agents/q_business_retriever.py` · `USE_AMAZON_Q=true` |
| Kiro IDE integration | Auto-generated `.kiro/specs/` for every agent | `app/integrations/kiro/exporter.py` · 85 files generated |
| Postgres job queue | Race-free SKIP-LOCKED claim · idempotency · janitor | `app/jobs/queue.py` · 10K-cases/day capacity model |
| Multi-replica SSE pub/sub | Redis pub/sub backend for fan-out | `app/streaming.py` `RedisPubSubBackend` |
| Per-org quota enforcement | Atomic 429 with Retry-After header | `app/quotas.py` · `app/api/quotas.py` |
| Deterministic response cache | Per-org sha256-keyed exact-match cache | `app/agents/framework/cache.py` · integrated in `Agent.invoke()` |
| FHIR R4 ingest | Da Vinci PAS endpoint live | `app/api/fhir_pas.py` · `POST /fhir/Claim/$submit` |
| Live business-value calculator | Per-case ROI · org rollup · Star projection · provider abrasion | `app/business_value/` · 4 endpoints · live frontend on `/roi` |
| Live compliance scorecard | 8 clauses tracked · per-case + org rollup | `app/compliance/cms_0057f.py` · live frontend on `/compliance` |
| Evidence pack export | Single-file bundle with bundle-SHA-256 | `app/api/evidence_pack.py` · `GET /api/v1/cases/{id}/evidence-pack` |

---

## Stage 4 · Scale 🟡 (apply-ready; awaiting first pilot customer)

**Foundry definition:** Industrialized via Neuro AI Multi-Agent Accelerator. Compatible with Azure AI Foundry, Google Agentspace, Salesforce Agentforce, WRITER.

| Gate | Criterion | Evidence | Status |
|---|---|---|---|
| Neuro AI Multi-Agent Accelerator compatible | AAOSA agent-network definition | `ops/neuro-san-integration/clincase-network.hocon` | ✅ |
| Bedrock AgentCore production deployment | Per-parent Runtime resources + Memory + Gateway | `ops/aws/agentcore/deployment.yaml` | ✅ apply-ready |
| Multi-region active/active | Aurora Global + Route 53 LBR + S3 CRR + multi-region KMS | `ops/terraform/multi-region/` | ✅ apply-ready |
| Provisioned Throughput | 1 MU Sonnet + 1 MU Haiku · OneMonth commitment | `ops/terraform/provisioned-throughput/` | ✅ apply-ready |
| K8s production manifests | API + worker tiers · HPA · PDB · IRSA · NetworkPolicy | `ops/k8s/` | ✅ |
| CI/CD pipeline | Build · test · security scan · SBOM · multi-arch ECR push · Terraform plan | `.github/workflows/ci.yml` | ✅ |
| Production deploy gate | Manual approval · canary 10% · post-deploy smoke · auto-promote | `.github/workflows/deploy-prod.yml` | ✅ |
| SLO/error-budget definitions | 7 SLOs with PagerDuty burn-rate alerts | `ops/sre/SLO.yaml` | ✅ |
| SRE runbook | 7 named incidents with diagnose+fix steps + post-mortem template | `ops/sre/RUNBOOK.md` | ✅ |
| Per-tenant Bedrock Guardrail | Per-customer guardrail ID; PHI redaction policy | `BEDROCK_GUARDRAIL_ID` env per tenant; `ops/multi-tenant/onboarding.md` | 🟡 onboarding doc only |
| Per-tenant KMS keys | DENY-by-default policy; tenant role assumes only its own key | KMS multi-region key in `ops/terraform/multi-region/rds.tf`; per-tenant key TBD per onboarding | 🟡 |
| AgentCore Evaluate-as-CI | Deterministic eval cases as a CI gate | `ops/agentcore/evaluate-suite.yaml` (TODO post-pilot) | ⚪ deferred |
| Datadog LLM Observability | Hallucination eval + prompt-injection scanner SDK init | `app/observability/datadog.py` (TODO post-pilot) | ⚪ deferred |
| First platform pilot customer | 30-day pilot live · 1,000 cases/day · ROI report published | TBD | ⏳ |

Legend: ✅ shipped today · 🟡 partial / docs-only · ⚪ deferred to post-pilot · ⏳ awaiting customer

---

## Acceptance for "production-ready"

A Solution architect, asking *"is ClinCase production-ready for our customer Monday?"*, gets a yes when **all of Build is ✅ and at least these Scale items are ✅** (everything above today):

- ✅ `ops/k8s/` manifests
- ✅ `.github/workflows/ci.yml` + `deploy-prod.yml`
- ✅ `ops/sre/SLO.yaml` + `ops/sre/RUNBOOK.md`
- ✅ `ops/terraform/multi-region/` + `ops/terraform/provisioned-throughput/`
- ✅ `ops/aws/agentcore/deployment.yaml`
- ✅ `ops/neuro-san-integration/clincase-network.hocon`
- ✅ `ops/agent-foundry/agent-foundry-manifest.yaml`
- ✅ Live Responsible AI model card · Evidence Pack endpoint · CMS-0057-F live scorecard

ClinCase meets that bar today.

---

## Out of scope for the demo (and intentionally deferred)

These are listed for honesty — they are *known* gaps that don't block a 30-day pilot:

- ⚪ **Datadog LLM SDK init** (`app/observability/datadog.py`). The SLO definitions in `ops/sre/SLO.yaml` are Prometheus-shaped; a Datadog or Honeycomb mirror is a 1-day port.
- ⚪ **AgentCore Evaluate API integration** as a CI gate. The deterministic eval cases live in `backend/tests/agents/`; wrapping them as an AgentCore Evaluate suite is a post-pilot effort.
- ⚪ **Per-tenant Bedrock Guardrail provisioning** automation. Today the guardrail ID is per-deployment; per-customer guardrails are documented in `ops/multi-tenant/onboarding.md` and trivially Terraformed when a second customer signs.
- ⚪ **Lambda Tenant Isolation Mode** ([GA early 2026](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)) for Firecracker MicroVM-level per-tenant isolation. Adopt when first customer that requires it asks.

These are intentionally deferred. The demo doesn't need them; the first customer might.
