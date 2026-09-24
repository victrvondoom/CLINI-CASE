# ClinCase — Documentation Index

Every doc in this repo, with one-line purpose. Use this as the table of contents.

## Top-level

| File | Purpose |
|---|---|
| [`README.md`](../README.md) | Product overview: what ClinCase is, how it works, how to run it |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Top-level architecture pointer (links to canonical 5-layer doc) |
| [`PROPOSAL.md`](../PROPOSAL.md) | Product and engineering specification (agent contracts, schemas, data models) |
| [`ROADMAP.md`](../ROADMAP.md) | Now → first pilot → post-pilot direction |
| [`CHANGELOG.md`](../CHANGELOG.md) | What shipped, and when |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | How to add agents · how to extend · architecture boundary rules |
| [`SECURITY.md`](../SECURITY.md) | Responsible-disclosure policy + scope |
| [`LICENSE`](../LICENSE) | MIT |
| [`Makefile`](../Makefile) | All dev tasks — `make help` |

## Product

| Doc | Purpose |
|---|---|
| [`docs/ONCOTWIN.md`](./ONCOTWIN.md) | OncoTwin patient digital twin: capabilities, measured results, limitations, API |

## Architecture

| Doc | Purpose |
|---|---|
| [`ops/architecture/TARGET_ARCHITECTURE.md`](../ops/architecture/TARGET_ARCHITECTURE.md) | Canonical 5-named-layer enterprise architecture |
| [`ops/architecture/BUSINESS_USE_CASE.md`](../ops/architecture/BUSINESS_USE_CASE.md) | Use case anchoring + 4 KPIs + per-component impact map |
| [`ops/architecture/AI_ADAPTATION_GAP.md`](../ops/architecture/AI_ADAPTATION_GAP.md) | AI adaptation gap framing — embed into existing processes |
| [`ops/architecture/AGENTIC_ACTIONS.md`](../ops/architecture/AGENTIC_ACTIONS.md) | User goal → 7-agent network → 5 typed actions → outcome |
| [`ops/architecture/Q_vs_BEDROCK.md`](../ops/architecture/Q_vs_BEDROCK.md) | Amazon Q vs Bedrock division-of-roles + decision matrix |
| [`docs/ARCHITECTURE_DIAGRAM.md`](./ARCHITECTURE_DIAGRAM.md) | ASCII + Mermaid diagrams |

## Architecture Decision Records (ADRs)

| ID | Decision |
|---|---|
| [ADR-0001](../ops/adr/0001-langgraph-over-raw-orchestration.md) | Use LangGraph for the 7-agent DAG |
| [ADR-0002](../ops/adr/0002-postgres-skip-locked-queue.md) | Postgres SKIP LOCKED for the case queue |
| [ADR-0003](../ops/adr/0003-per-tenant-bedrock-guardrails.md) | Per-tenant Bedrock Guardrail attached at InvokeModel |
| [ADR-0004](../ops/adr/0004-pluggable-retrieval-behind-one-schema.md) | Pluggable retrieval (Bedrock KB ↔ Q Business) behind one schema |
| [ADR-0005](../ops/adr/0005-genai-gateway-as-in-process-wrapper.md) | GenAI Gateway as in-process LLMClient wrapper |
| [ADR-0006](../ops/adr/0006-exact-match-response-cache-not-semantic.md) | Exact-match SHA-256 response cache (not semantic) |
| [ADR-0007](../ops/adr/0007-review-gate-as-langgraph-node.md) | HITL review_gate as a LangGraph node |
| [ADR-0008](../ops/adr/0008-evidence-pack-sha256-bundle.md) | Evidence Pack as single tamper-evident SHA-256 JSON bundle |

## Industrialization

| Doc | Purpose |
|---|---|
| [`ops/industrialization/CHECKLIST.md`](../ops/industrialization/CHECKLIST.md) | Agent Foundry stage gates: Discover · Design · Build · Scale |
| [`ops/neuro-san-integration/clincase-network.hocon`](../ops/neuro-san-integration/clincase-network.hocon) | Neuro-SAN AAOSA-format agent network definition |
| [`ops/agent-foundry/agent-foundry-manifest.yaml`](../ops/agent-foundry/agent-foundry-manifest.yaml) | Agent Foundry bundle manifest (AgentSpec conventions) |
| [`ops/aws/agentcore/deployment.yaml`](../ops/aws/agentcore/deployment.yaml) | AWS Bedrock AgentCore deployment manifest (apply-ready) |
| [`ops/aws/MIGRATION_RUNBOOK.md`](../ops/aws/MIGRATION_RUNBOOK.md) | Step-by-step migration to AWS Bedrock, with rollback drill |
| [`ops/kiro/HOOKS.md`](../ops/kiro/HOOKS.md) | Kiro IDE Hooks for SDLC discipline |

## SRE & operations

| Doc | Purpose |
|---|---|
| [`ops/SCALING.md`](../ops/SCALING.md) | Capacity model — 1K → 10K → 100K cases/day |
| [`ops/sre/SLO.yaml`](../ops/sre/SLO.yaml) | 7 SLOs with PagerDuty burn-rate alerts |
| [`ops/sre/RUNBOOK.md`](../ops/sre/RUNBOOK.md) | 7 named incidents · diagnose+fix · post-mortem template |
| [`ops/sre/LOAD_TEST_RESULTS.md`](../ops/sre/LOAD_TEST_RESULTS.md) | 5-tier scalability evidence (Tier 1 measured) |
| [`ops/multi-tenant/ONBOARDING.md`](../ops/multi-tenant/ONBOARDING.md) | Per-tenant customer onboarding playbook |

## Infrastructure (Terraform)

| Module | Purpose |
|---|---|
| [`ops/terraform/multi-region/`](../ops/terraform/multi-region/) | Aurora Global + Route 53 LBR + S3 CRR + multi-region KMS |
| [`ops/terraform/provisioned-throughput/`](../ops/terraform/provisioned-throughput/) | Bedrock Provisioned Throughput (1 MU Sonnet + 1 MU Haiku) |
| [`ops/terraform/bedrock-vpc-endpoint/`](../ops/terraform/bedrock-vpc-endpoint/) | PrivateLink VPC endpoint + endpoint policy + IAM with per-model-id condition |
| [`ops/terraform/s3-vectors/`](../ops/terraform/s3-vectors/) | S3 Vectors substrate for Bedrock KB (per-tenant index) |

## Kubernetes (production manifests)

| File | Purpose |
|---|---|
| [`ops/k8s/api-deployment.yaml`](../ops/k8s/api-deployment.yaml) | API tier Deployment + Service + Ingress + HPA |
| [`ops/k8s/worker-deployment.yaml`](../ops/k8s/worker-deployment.yaml) | Worker tier Deployment + HPA (queue-depth) + PDB |
| [`ops/k8s/config.yaml`](../ops/k8s/config.yaml) | Namespace + ConfigMap + Secrets shape + ServiceAccounts + NetworkPolicy |

## CI/CD

| Workflow | Purpose |
|---|---|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Frontend type-check + build · backend lint · sample fixtures · README sections · OncoTwin tests |
| [`.github/workflows/deploy-prod.yml`](../.github/workflows/deploy-prod.yml) | OIDC · staging smoke · GitHub-environment manual approval · canary 10% · auto-promote |

## Kiro IDE

| Path | Purpose |
|---|---|
| [`.kiro/specs/`](../.kiro/specs/) | Auto-generated Kiro spec library (regenerated by exporter) |
| [`.kiro/hooks/`](../.kiro/hooks/) | Hook scripts: regenerate-specs, architecture-boundary-check, verify-foundry-manifest |
| [`ops/kiro/HOOKS.md`](../ops/kiro/HOOKS.md) | Kiro Hooks documentation |

## Backend code (high-level pointers)

| Path | What lives there |
|---|---|
| `backend/app/main.py` | FastAPI app composition + lifespan |
| `backend/app/agents/framework/` | `Agent[I, O]` base + lifecycle + grader + budget + cache + guardrails + trace_sink |
| `backend/app/agents/<parent>/` | Each of 7 parent agents (orchestrator + node + schemas + sub-agents) |
| `backend/app/agents/manifest.py` | Auto-discovery via `pkgutil.iter_modules(app.agents.*)` |
| `backend/app/llm/gateway.py` | GenAI Gateway (per-tenant policy + quota + audit) |
| `backend/app/api/` | API route modules |
| `backend/app/oncotwin/` | OncoTwin engine, intelligence, ML, safety gates |
| `backend/app/integrations/{trizetto,amazon_q,kiro}/` | External system adapters |
| `backend/app/compliance/cms_0057f.py` | CMS-0057-F live scorecard |
| `backend/app/business_value/` | ROI · Star Ratings · provider abrasion |
| `backend/app/jobs/queue.py` | Postgres SKIP LOCKED case queue |
| `backend/app/streaming.py` | SSE pub/sub (in-process + Redis backends) |
| `backend/scripts/smoke_test.py` | 5-layer self-check |

## Frontend code (high-level pointers)

| Path | What lives there |
|---|---|
| `frontend/src/main.tsx` | Router + AuthProvider |
| `frontend/src/components/AppShell.tsx` | TopBar + Sidenav + main outlet |
| `frontend/src/routes/` | Route components incl. `/architecture`, `/roi`, `/compliance`, `/industrialize`, `/twin` |
| `frontend/src/oncotwin/` | OncoTwin UI components and API client |
| `frontend/src/lib/api.ts` | Typed API client |
| `frontend/src/lib/sse.ts` | SSE trace stream consumer |
