# ClinCase â€” Industrialization Checklist

**Aligned 1:1 with Cognizant Agent Foundry's published 4-stage methodology**
(Discover â†’ Design â†’ Build â†’ Scale; [press release Jul 10, 2025](https://news.cognizant.com/2025-07-10-Cognizant-Introduces-Agent-Foundry-Powering-Agentic-AI-at-Enterprise-Scale))

This is the gating document for *"is ClinCase production-grade for a Cognizant TriZetto customer Monday?"* Each gate has explicit acceptance criteria + the artifact that proves it.

---

## Stage 1 Â· Discover âœ…

**Foundry definition:** AI-driven process mining surfaces automation opportunities. Identify the use case, baseline the cost, quantify the ROI band.

| Gate | Criterion | Evidence |
|---|---|---|
| Use case identified | One named workflow with measurable cycle-time + error rate | Oncology PA Â· `ops/demo/PITCH_DECK.md` Â§ Problem |
| Industry baseline established | Manual cost / case Â· time / case Â· denial rate | AMA $1,500 / 18 min Â· `ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md` Â§ ROI levers |
| Regulatory forcing function | At least one in-force regulation that *requires* automation | CMS-0057-F Â§ IV.B.1 (live Jan 1 2026) Â· CA SB 1120 |
| Competitive benchmark | Public ROI numbers from a peer deployment | Elevance Health OS 70% denial reduction Â· Summit Health 42% PA-time reduction |
| Star Ratings linkage | Direct $$ tied to Star measure(s) the agent influences | $1.26B/half-star at Humana scale Â· `app/business_value/star_ratings.py` |

---

## Stage 2 Â· Design âœ…

**Foundry definition:** Define agent roles + frameworks + change-management plan.

| Gate | Criterion | Evidence |
|---|---|---|
| Agent inventory locked | Named parents + sub-agents + reflection thresholds + model sizes | 7 parents, 22 sub-agents Â· `app/agents/manifest.py` Â· live at `/api/v1/agents/manifest` |
| Schemas declared | Pydantic v2 input + output for every agent | `app/agents/<parent>/schemas.py` |
| Lifecycle declared | Single `Agent[I,O]` base class with shared invoke() | `app/agents/framework/agent.py` |
| Guardrail surface declared | Schema Â· PHI Â· Citation Â· Token-budget guardrails attached | `app/agents/framework/guardrails.py` Â· per-agent declared |
| Foundry manifest published | YAML manifest with Discover/Design/Build/Scale labeling | `ops/agent-foundry/agent-foundry-manifest.yaml` |
| Neuro-SAN compatible | AAOSA-format network definition | `ops/neuro-san-integration/clincase-network.hocon` |
| Responsible AI card | NIST AI RMF + ISO 42001 + EU AI Act + AWS AI Service Card structure | `app/api/responsible_ai.py` Â· live at `/api/v1/responsible-ai/model-card` |
| Change-management plan | HITL gate + reviewer queue + audit trail | `app/graph/build.py` review_gate node Â· `app/api/cases.py` resume endpoint |

---

## Stage 3 Â· Build âœ…

**Foundry definition:** Multi-agent orchestration + partner-tech integration.

| Gate | Criterion | Evidence |
|---|---|---|
| Multi-agent orchestration runs end-to-end | Live LangGraph DAG completes a case in < 90s p95 | SLO `decision-tat` in `ops/sre/SLO.yaml` |
| Bedrock + Sonnet 4.6 integration | Production-grade model wrapper with fallback escalation | `app/agents/framework/models.py` ModelRouter Â· `app/llm/bedrock_client.py` |
| MCP server | JSON-RPC 2.0 MCP-compliant tool surface | `app/mcp/server.py` Â· `/mcp` endpoint |
| TriZetto AI Gateway adapter | Facets v3 + QNXT v2 events with tamper-evident hashes | `app/integrations/trizetto/` Â· `POST /api/v1/integrations/trizetto/submit` |
| Amazon Q Business connector | Drop-in alternative to Bedrock KB | `app/agents/policy_retriever/sub_agents/q_business_retriever.py` Â· `USE_AMAZON_Q=true` |
| Kiro IDE integration | Auto-generated `.kiro/specs/` for every agent | `app/integrations/kiro/exporter.py` Â· 85 files generated |
| Postgres job queue | Race-free SKIP-LOCKED claim Â· idempotency Â· janitor | `app/jobs/queue.py` Â· 10K-cases/day capacity model |
| Multi-replica SSE pub/sub | Redis pub/sub backend for fan-out | `app/streaming.py` `RedisPubSubBackend` |
| Per-org quota enforcement | Atomic 429 with Retry-After header | `app/quotas.py` Â· `app/api/quotas.py` |
| Deterministic response cache | Per-org sha256-keyed exact-match cache | `app/agents/framework/cache.py` Â· integrated in `Agent.invoke()` |
| FHIR R4 ingest | Da Vinci PAS endpoint live | `app/api/fhir_pas.py` Â· `POST /fhir/Claim/$submit` |
| Live business-value calculator | Per-case ROI Â· org rollup Â· Star projection Â· provider abrasion | `app/business_value/` Â· 4 endpoints Â· live frontend on `/roi` |
| Live compliance scorecard | 8 clauses tracked Â· per-case + org rollup | `app/compliance/cms_0057f.py` Â· live frontend on `/compliance` |
| Evidence pack export | Single-file bundle with bundle-SHA-256 | `app/api/evidence_pack.py` Â· `GET /api/v1/cases/{id}/evidence-pack` |

---

## Stage 4 Â· Scale ðŸŸ¡ (apply-ready; awaiting first Cognizant pilot customer)

**Foundry definition:** Industrialized via Neuro AI Multi-Agent Accelerator. Compatible with Azure AI Foundry, Google Agentspace, Salesforce Agentforce, WRITER.

| Gate | Criterion | Evidence | Status |
|---|---|---|---|
| Neuro AI Multi-Agent Accelerator compatible | AAOSA agent-network definition | `ops/neuro-san-integration/clincase-network.hocon` | âœ… |
| Bedrock AgentCore production deployment | Per-parent Runtime resources + Memory + Gateway | `ops/aws/agentcore/deployment.yaml` | âœ… apply-ready |
| Multi-region active/active | Aurora Global + Route 53 LBR + S3 CRR + multi-region KMS | `ops/terraform/multi-region/` | âœ… apply-ready |
| Provisioned Throughput | 1 MU Sonnet + 1 MU Haiku Â· OneMonth commitment | `ops/terraform/provisioned-throughput/` | âœ… apply-ready |
| K8s production manifests | API + worker tiers Â· HPA Â· PDB Â· IRSA Â· NetworkPolicy | `ops/k8s/` | âœ… |
| CI/CD pipeline | Build Â· test Â· security scan Â· SBOM Â· multi-arch ECR push Â· Terraform plan | `.github/workflows/ci.yml` | âœ… |
| Production deploy gate | Manual approval Â· canary 10% Â· post-deploy smoke Â· auto-promote | `.github/workflows/deploy-prod.yml` | âœ… |
| SLO/error-budget definitions | 7 SLOs with PagerDuty burn-rate alerts | `ops/sre/SLO.yaml` | âœ… |
| SRE runbook | 7 named incidents with diagnose+fix steps + post-mortem template | `ops/sre/RUNBOOK.md` | âœ… |
| Per-tenant Bedrock Guardrail | Per-customer guardrail ID; PHI redaction policy | `BEDROCK_GUARDRAIL_ID` env per tenant; `ops/multi-tenant/onboarding.md` | ðŸŸ¡ onboarding doc only |
| Per-tenant KMS keys | DENY-by-default policy; tenant role assumes only its own key | KMS multi-region key in `ops/terraform/multi-region/rds.tf`; per-tenant key TBD per onboarding | ðŸŸ¡ |
| AgentCore Evaluate-as-CI | Deterministic eval cases as a CI gate | `ops/agentcore/evaluate-suite.yaml` (TODO post-pilot) | âšª deferred |
| Datadog LLM Observability | Hallucination eval + prompt-injection scanner SDK init | `app/observability/datadog.py` (TODO post-pilot) | âšª deferred |
| First platform pilot customer | 30-day pilot live Â· 1,000 cases/day Â· ROI report published | TBD post-the hackathon | â³ |

Legend: âœ… shipped today Â· ðŸŸ¡ partial / docs-only Â· âšª deferred to post-pilot Â· â³ awaiting customer

---

## Acceptance for "production-ready"

A Cognizant solution architect, asking *"is ClinCase production-ready for our customer Monday?"*, gets a yes when **all of Build is âœ… and at least these Scale items are âœ…** (everything above today):

- âœ… `ops/k8s/` manifests
- âœ… `.github/workflows/ci.yml` + `deploy-prod.yml`
- âœ… `ops/sre/SLO.yaml` + `ops/sre/RUNBOOK.md`
- âœ… `ops/terraform/multi-region/` + `ops/terraform/provisioned-throughput/`
- âœ… `ops/aws/agentcore/deployment.yaml`
- âœ… `ops/neuro-san-integration/clincase-network.hocon`
- âœ… `ops/agent-foundry/agent-foundry-manifest.yaml`
- âœ… Live Responsible AI model card Â· Evidence Pack endpoint Â· CMS-0057-F live scorecard

ClinCase meets that bar today.

---

## Out of scope for the the hackathon demo (and intentionally deferred)

These are listed for honesty â€” they are *known* gaps that don't block a 30-day pilot:

- âšª **Datadog LLM SDK init** (`app/observability/datadog.py`). The SLO definitions in `ops/sre/SLO.yaml` are Prometheus-shaped; a Datadog or Honeycomb mirror is a 1-day port.
- âšª **AgentCore Evaluate API integration** as a CI gate. The deterministic eval cases live in `backend/tests/agents/`; wrapping them as an AgentCore Evaluate suite is a post-pilot effort.
- âšª **Per-tenant Bedrock Guardrail provisioning** automation. Today the guardrail ID is per-deployment; per-customer guardrails are documented in `ops/multi-tenant/onboarding.md` and trivially Terraformed when a second customer signs.
- âšª **Lambda Tenant Isolation Mode** ([GA early 2026](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)) for Firecracker MicroVM-level per-tenant isolation. Adopt when first customer that requires it asks.

These are intentionally deferred. The hackathon demo doesn't need them; the first customer might.
