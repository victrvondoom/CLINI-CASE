# ClinCase — Target Enterprise Architecture

**Audience:** Cognizant Health Sciences solution architect · TriZetto product engineering · AWS account team
**Purpose:** Show — in the language a senior Cognizant architect uses — that ClinCase is engineered for industrialization, not for demo polish.

---

## The 5 layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         1.  EXPERIENCE LAYER                             │
│                                                                          │
│   React 18 SPA · TypeScript strict · Tailwind · SSE for live trace       │
│   17 routes incl. /dashboard /cases /roi /compliance /industrialize      │
│   Role-aware (coordinator / reviewer / admin)                            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  HTTPS · JWT · Idempotency-Key
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  2.  ORCHESTRATION & POLICY ENGINE                       │
│                                                                          │
│   FastAPI · LangGraph 7-agent DAG · BudgetTracker · review_gate (HITL)   │
│   case_jobs queue (Postgres SKIP LOCKED) · per-org quotas · response     │
│   cache · idempotent submits · 22 sub-agents                             │
└─────┬────────────────────┬────────────────────┬─────────────────┬───────┘
      │                    │                    │                 │
      ▼                    ▼                    ▼                 ▼
┌──────────────┐   ┌────────────────┐   ┌─────────────────┐  ┌─────────────┐
│ 3. CONTEXT   │   │ 4. GENAI       │   │ 5. TELEMETRY    │  │ External    │
│    RETRIEVAL │   │    GATEWAY     │   │    & GOVERNANCE │  │ INTEGRATIONS│
│              │   │                │   │                 │  │             │
│ Bedrock KB   │   │ LLMClient ABC  │   │ TraceSink ABC   │  │ TriZetto AI │
│ Amazon Q Biz │   │ Bedrock client │   │ Prometheus /met │  │  Gateway    │
│ Policy corpus│   │ Anthropic API  │   │ Postgres audit  │  │  (Facets v3 │
│ Citation     │   │ ModelRouter    │   │ Compliance      │  │  + QNXT v2) │
│  resolver    │   │  (Sonnet/Haiku │   │  scorecard      │  │             │
│ FHIR R4      │   │  escalation)   │   │ Evidence Pack   │  │ MCP server  │
│  validator   │   │ Bedrock        │   │  (SHA-256       │  │  (5 tools)  │
│              │   │  Guardrails    │   │  tamper-evident)│  │             │
│              │   │  per-tenant    │   │ Responsible AI  │  │ FHIR PAS    │
│              │   │ Budget+token   │   │  model card     │  │  endpoint   │
│              │   │  ceilings      │   │ SLO+error budg. │  │             │
└──────┬───────┘   └────────┬───────┘   └────────┬────────┘  └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          AWS Foundation                                  │
│                                                                          │
│  Bedrock (Claude Sonnet 4.6 + Haiku 4.5) · Bedrock Knowledge Base ·      │
│  Bedrock Guardrails · AgentCore Runtime · Amazon Q Business · RDS Aurora │
│  Global · S3 + KMS multi-region · ALB + WAF · IAM Identity Center · X-Ray│
│  + CloudWatch · SNS → PagerDuty · IRSA · NetworkPolicy (VPC-only egress) │
└──────────────────────────────────────────────────────────────────────────┘
```

Each layer is **independently testable, independently deployable, and independently scalable**. That's the property a Cognizant solution architect looks for in "production-grade" — and it's how ClinCase resists the AI velocity gap (Ravi Kumar Dec 2025): every layer carries its own ROI lever.

---

## 1. Experience Layer

| Component | Responsibility | Where it lives | Why it matters to Cognizant |
|---|---|---|---|
| Dashboard | Live KPIs (MTD savings, decision TAT, annualized projection) | `frontend/src/routes/Dashboard.tsx` | First screen a CFO sees; signals ROI immediately. |
| Case Detail | 7-agent live trace · decision · appeal · patient comm | `frontend/src/routes/CaseDetail.tsx` | The "AI assistant" workflow — not a chat box. |
| `/roi` | Interactive Star Ratings + per-case ROI calculator | `frontend/src/routes/ROI.tsx` | CFO-facing tool for in-call ROI sizing. |
| `/compliance` | Live CMS-0057-F + state-AI-law scorecard | `frontend/src/routes/Compliance.tsx` | Audit-ready evidence on demand. |
| `/industrialize` | Live Cognizant Neuro / Foundry compatibility + Responsible AI card | `frontend/src/routes/Industrialize.tsx` | Production-readiness panel for SAs. |
| `/architecture` | This document, made interactive | `frontend/src/routes/Architecture.tsx` | "Show me the architecture" answered live. |
| SSE trace stream | Real-time agent-by-agent updates | `frontend/src/lib/sse.ts` + `app/api/stream.py` | Replaces a spinner with proof of work. |
| Role-based RBAC | Coordinator / Reviewer / Admin | `frontend/src/components/RequireAuth.tsx` | Enterprise audit trail; CMS-0057-F § IV.C HITL signoff. |

**Stack.** React 18 + TypeScript strict + Tailwind + Vite. Vite proxies `/api/*` to backend; production build served via ALB → S3+CloudFront fallback.

**Business outcome.** Replaces the manual PA workflow that consumed 12–13 hours / week per oncologist (AMA 2025) with a 2-minute click-through. Eight UI moments — KPI tile, decision badge, citation chips, agent trace panel, evidence-pack download, TriZetto submit button, ROI calculator, compliance scorecard — each map to a specific business outcome and are live at demo time.

---

## 2. Orchestration & Policy Engine

| Component | Responsibility | Where it lives | Business lever |
|---|---|---|---|
| `Agent[I, O]` framework | Production lifecycle: validate → cache lookup → guardrail → reserve budget → act → guardrail → reflect → commit budget → emit trace | `backend/app/agents/framework/agent.py` | Same lifecycle for every agent — testable, replaceable, observable. **Closes the velocity gap by eliminating bespoke per-agent plumbing.** |
| LangGraph 7-agent DAG | Clinical Extractor → Policy Retriever → Necessity Reasoner → Decision Composer → Denial Forecaster → Appeals Drafter → Patient Communicator | `backend/app/graph/build.py` | Conditional edges (HITL gate, DENY→appeal) are declarative; topology inspectable for auditors. |
| `BudgetTracker` | Per-case $5 / 600K-token / 600s ceiling; reservation pattern | `backend/app/agents/framework/budget.py` | **Cost runaway impossible** — `BudgetExceeded` raised before any LLM token is spent. |
| Guardrails (Schema · PHI · Citation · Token-budget) | Input + output validation per agent | `backend/app/agents/framework/guardrails.py` | Hallucination mitigation; CMS-0057-F § IV.B.2 specific-reason notice. |
| `case_jobs` queue | Postgres SKIP-LOCKED; idempotency-key dedup; janitor reaps stale heartbeats | `backend/app/jobs/queue.py` | Survives restarts, scales to 10K cases/day; same RPO/RTO as Aurora. |
| `review_gate` HITL node | Routes adverse determinations to qualified clinician | `backend/app/graph/build.py` + `backend/app/api/cases.py` resume endpoint | **CMS-0057-F § IV.C + CA SB 1120 compliant by design.** ClinCase never auto-denies. |
| Per-org quotas | Atomic SQL gate; daily + monthly limits | `backend/app/quotas.py` | Cost containment per tenant; HTTP 429 with `Retry-After`. |
| Deterministic response cache | sha256-keyed; per-org isolated; schema-pinned | `backend/app/agents/framework/cache.py` | Retry-storm cost displacement; multi-tenant safe by construction. |

**Business outcome.** Orchestration is where AI investment becomes AI value. Every concern that kills AI pilots (cost runaway, schema drift, audit gaps, lack of HITL, race conditions) is engineered out *here*, once, for every agent. **This is the layer that lifts ClinCase into McKinsey's 5%.**

---

## 3. Context Retrieval Service

| Component | Responsibility | Where it lives | Business lever |
|---|---|---|---|
| `policy_retriever` orchestrator | Routes between Bedrock KB and Amazon Q Business backends per `USE_AMAZON_Q` | `backend/app/agents/policy_retriever/orchestrator.py` | **Customer-aligned grounding** — uses the customer's existing knowledge corpus, not a brittle hand-curated one. |
| `keyword_filter` sub-agent | Deterministic over the curated 21-policy corpus | `backend/app/agents/policy_retriever/sub_agents/keyword_filter.py` | Free, fast, deterministic dev path. |
| `q_business_retriever` sub-agent | Amazon Q Business semantic search over M365/SharePoint/Confluence | `backend/app/agents/policy_retriever/sub_agents/q_business_retriever.py` | **No new vector index required at customer site** — plug into their existing Q Business connector. |
| `llm_reranker` sub-agent | LLM-rerank when > 5 candidates | `backend/app/agents/policy_retriever/sub_agents/llm_reranker.py` | Recall + precision; tuned to ≤ 5 final excerpts to keep context window cheap. |
| `citation_resolver` sub-agent | Resolves to fully-pointered `PolicyExcerpt` (page + section + URL) | `backend/app/agents/policy_retriever/sub_agents/citation_resolver.py` | **Every citation in every Decision is auditable to a specific policy section.** |
| `phi_sanitizer` sub-agent | Redacts PHI before any non-Bedrock LLM call | `backend/app/agents/clinical_extractor/sub_agents/phi_sanitizer.py` | HIPAA Privacy Rule guardrail; safe RAG over PHI-bearing FHIR. |
| `fhir_resource_validator` | FHIR R4 schema validation pre-extraction | `backend/app/agents/clinical_extractor/sub_agents/fhir_resource_validator.py` | Anchors decisions on validated clinical context, not parsed strings. |
| `biomarker_specialist` | LOINC-bound HER2/EGFR/PD-L1/BRAF/MSI extraction | `backend/app/agents/clinical_extractor/sub_agents/biomarker_specialist.py` | Domain-specific extraction; oncology demands this precision. |

**Business outcome.** Context retrieval is the difference between "GenAI demo" and "GenAI in production." Bedrock KB and Amazon Q Business are pluggable behind a single `KeywordFilterInput → KeywordFilterOutput` schema — the orchestrator picks at call time. **A new customer flips one env var (`USE_AMAZON_Q=true`) and gets retrieval over their existing M365 corpus** — zero downstream code change.

---

## 4. GenAI Gateway

| Component | Responsibility | Where it lives | Business lever |
|---|---|---|---|
| `LLMClient` ABC | Provider-agnostic surface | `backend/app/llm/base.py` | Switch providers (Anthropic direct ↔ Bedrock ↔ OpenRouter) by env flip. **Vendor-lock-in mitigated.** |
| `BedrockClient` | InvokeModel wrapper; ApiBoto3 in `ap-south-1` | `backend/app/llm/bedrock_client.py` | Production default; co-located with RDS in `ap-south-1`. |
| `ModelRouter` | Haiku → Sonnet escalation on retry | `backend/app/agents/framework/models.py` | **Cost-optimal default** — try Haiku first; escalate only on parse failure. |
| `ModelSpec` | Declarative size + role + max_tokens + temperature | `backend/app/agents/framework/models.py` | Per-agent model assignment; auditable model lineage. |
| `LLMGrader` | Self-evaluation on reflection-enabled agents (3 of 22) | `backend/app/agents/framework/grader.py` | Quality-threshold reflection; Haiku grader keeps cost down. |
| Bedrock Guardrails | Per-tenant PHI redaction policy | `BEDROCK_GUARDRAIL_ID` in env | **Per-tenant safety policy** — onboarding doc at `ops/multi-tenant/ONBOARDING.md`. |
| Bedrock Provisioned Throughput | 1 MU Sonnet + 1 MU Haiku, OneMonth commit | `ops/terraform/provisioned-throughput/` | Predictable cost + predictable TPM at scale; alarms at 80% / 95% utilization. |
| Bedrock AgentCore Runtime (apply-ready) | Per-parent Runtime + Memory + Gateway + Identity | `ops/aws/agentcore/deployment.yaml` | **Production agentic runtime** — framework-agnostic; LangGraph supported. |

**Business outcome.** The Gateway is the single pane of glass over every LLM call ClinCase makes. Models, costs, tokens, guardrails, throughput, and identity all flow through one named component. **A Cognizant CISO can sign off on this layer without auditing 28 agent files** — they audit one Gateway.

---

## 5. Telemetry & Governance Layer

| Component | Responsibility | Where it lives | Business lever |
|---|---|---|---|
| `TraceSink` ABC | Pluggable persistence + SSE for every agent invocation | `backend/app/agents/framework/trace_sink.py` | `PostgresTraceSink` in prod, `InMemoryTraceSink` in tests, custom impls per customer. |
| `agent_runs` audit table | Every invocation: input, output, model_id, tokens, latency, error | `backend/db/schema.sql` | **CMS-0057-F § IV.D 7-year retention by design.** Every decision reproducible. |
| Prometheus `/metrics` | 8 metric families (cases, queue depth, agent invocations, latency, tokens, cost, active orgs) | `backend/app/api/metrics.py` | Standard scrape; HPA on `clincase_jobs_queue_depth{status="queued"}`. |
| SLO + error-budget | 7 SLOs with PagerDuty burn-rate alerts | `ops/sre/SLO.yaml` | Industry-standard Datadog/Honeycomb pattern; production-grade SLO discipline. |
| SRE runbook | 7 named incidents · diagnose+fix · post-mortem template | `ops/sre/RUNBOOK.md` | Day-1 on-call ready; Cognizant escalation path documented. |
| Compliance scorecard | Live CMS-0057-F + state-AI-law clause checker | `backend/app/compliance/cms_0057f.py` + `/api/v1/compliance/case/{id}` | **8 clauses tracked, 6 in-force today.** No mocks. |
| Business value calc | Per-case ROI, org rollup, Star projection, provider abrasion | `backend/app/business_value/` + 4 endpoints | **Live ROI evidence per case.** $1,499.55/case verifiable on demand. |
| Evidence Pack | Single-file bundle with bundle-SHA-256 tamper hash | `backend/app/api/evidence_pack.py` | **Auditor-grade artifact** — case + decision + agent_runs + reviewer_actions + compliance + ROI in one tamper-evident JSON. |
| Responsible AI model card | NIST AI RMF + ISO 42001 + EU AI Act + AWS AI Service Card | `backend/app/api/responsible_ai.py` | Procurement-question-answer doc; live + downloadable Markdown. |
| Foundry manifest | Cognizant Neuro / Agent Foundry compatibility descriptor | `backend/app/api/foundry.py` | Live evidence of stack alignment. |

**Business outcome.** This is the layer that turns "AI we trust" into "AI an auditor trusts." Every line in the health-sciences sales motion (HIPAA · CMS-0057-F · CA SB 1120 · EU AI Act · ISO 42001 · NIST AI RMF) has a named, queryable component here. **Compliance is not a slide — it's an endpoint.**

---

## Cross-cutting concerns

### Multi-tenancy

- `organization_id` enforced in every domain query; cross-org reads return 404 (no existence leak).
- Per-tenant Bedrock Guardrail (per-customer PHI policy) — `BEDROCK_GUARDRAIL_ID` env per tenant.
- Per-tenant KMS multi-region key; tenant's IAM role decrypts only its own data.
- `org_quotas` table with atomic conditional UPDATE for race-free rate limiting.
- AWS Lambda Tenant Isolation Mode ([GA early 2026](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)) adoption documented in `ops/multi-tenant/ONBOARDING.md`.

### CI/CD

- `.github/workflows/ci.yml` — lint · pytest · tsc · pip-audit · bandit · Semgrep healthcare ruleset · npm audit · CycloneDX SBOM · multi-arch ECR push · Terraform plan.
- `.github/workflows/deploy-prod.yml` — OIDC (no static keys) · staging smoke · GitHub-environment manual approval · canary 10% · post-deploy smoke · auto-promote on error budget · Slack release notification.

### Kiro IDE alignment

- `.kiro/specs/` materialized for all 7 parents + 22 sub-agents (85 files).
- Auto-generated from `AGENT_MANIFEST` via `python -m app.integrations.kiro.exporter`.
- A new specialty (cardiology, behavioral health, transplant) = edit 3 markdown files; Kiro Hooks regenerate the agent skeleton — **the Cognizant industrialization velocity that's the whole point of "spec-driven AI development."**

### Scalability

- Stateless API tier (3–50 replicas, HPA on CPU + memory).
- Worker tier scaled on custom queue-depth metric (5–100 replicas, HPA External metric).
- Aurora primary + cross-region secondary (apply-ready Terraform).
- Bedrock Provisioned Throughput pinned (apply-ready Terraform).

---

## Pattern alignment with AWS reference architectures

| ClinCase layer | AWS reference architecture |
|---|---|
| Experience Layer | [AWS SaaS Storefront pattern](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/) — ALB + sticky for SSE + WAF |
| Orchestration & Policy Engine | [Bedrock Agents + LangGraph hybrid](https://aws.amazon.com/bedrock/agentcore/) — AgentCore Runtime apply-ready |
| Context Retrieval Service | [Amazon Q Business + Bedrock KB hybrid](https://aws.amazon.com/q/business/) — same retrieval contract, two backends |
| GenAI Gateway | [Bedrock Provisioned Throughput + Guardrails](https://aws.amazon.com/bedrock/) — capacity + safety per tenant |
| Telemetry & Governance | [CloudWatch + X-Ray + AWS Distro for OpenTelemetry](https://aws.amazon.com/distro-for-opentelemetry/) — Prometheus on top |

This mirrors the [aws-samples/sample-bedrock-agentcore-runtime-cicd](https://github.com/aws-samples/sample-bedrock-agentcore-runtime-cicd) reference pattern: GitHub Actions + OIDC + ECR + Inspector + AgentCore. ClinCase follows the AWS-blessed shape, not a bespoke one.

---

## Stage-gate maturity (mapped to Cognizant Agent Foundry)

| Stage | Layers required for graduation | ClinCase status |
|---|---|---|
| **Discover** | Use case · baseline metric · ROI band | ✅ |
| **Design** | Experience + Orchestration layers defined; agent contract locked | ✅ |
| **Build** | All 5 layers shipped; CI/CD live; integrations tested | ✅ |
| **Scale** | SLOs · runbook · multi-tenant onboarding · Terraform apply-ready · pilot customer | 🟡 awaits first pilot |

Layer-by-layer gating spec is in `ops/industrialization/CHECKLIST.md`.

---

## Why this stands up in front of a Cognizant VP

A VP/architect accountable for client outcomes cares about three questions. Each layer has an answer:

1. **"Where's the ROI?"** → Telemetry & Governance Layer · live `/api/v1/business-value/*` endpoints · $1,499.55 saved per case · $1.26B / half-star at Humana scale.
2. **"Where's the risk?"** → Telemetry & Governance Layer · live `/api/v1/compliance/case/{id}` · per-tenant Bedrock Guardrails · review_gate HITL · Evidence Pack with SHA-256 tamper hash.
3. **"Can we sell this Monday?"** → Orchestration + GenAI Gateway · TriZetto AI Gateway adapter (MCP-native, Aug 6 2025 platform) · drop-in for Facets v3 + QNXT v2.

Three answers, three live endpoints. Not three slides.
