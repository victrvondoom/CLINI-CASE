# ClinCase â€” Documentation Index

Every doc in this repo, with one-line purpose. Use this as the table of contents.

## Top-level

| File | Purpose |
|---|---|
| [`README.md`](../README.md) | Judge first-impression: what is ClinCase, where to look, 30-sec tour |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Top-level architecture pointer (links to canonical 5-layer doc) |
| [`PROPOSAL.md`](../PROPOSAL.md) | Original strategy + 23-day plan (LOCKED â€” do not edit) |
| [`ROADMAP.md`](../ROADMAP.md) | Day 0 â†’ Day 90 â†’ post-pilot direction |
| [`CHANGELOG.md`](../CHANGELOG.md) | What shipped, when, organized by round |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | How to add agents Â· how to extend Â· architecture boundary rules |
| [`SECURITY.md`](../SECURITY.md) | Responsible-disclosure policy + scope |
| [`LICENSE`](../LICENSE) | MIT |
| [`CLAUDE.md`](../CLAUDE.md) | Coding conventions (Python/TS/agent rules) |
| [`Makefile`](../Makefile) | All dev tasks â€” `make help` |

## Architecture

| Doc | Purpose |
|---|---|
| [`ops/architecture/TARGET_ARCHITECTURE.md`](../ops/architecture/TARGET_ARCHITECTURE.md) | Canonical 5-named-layer enterprise architecture |
| [`ops/architecture/BUSINESS_USE_CASE.md`](../ops/architecture/BUSINESS_USE_CASE.md) | Use case anchoring + 4 KPIs + per-component impact map |
| [`ops/architecture/AI_ADAPTATION_GAP.md`](../ops/architecture/AI_ADAPTATION_GAP.md) | AI adaptation gap framing â€” embed-into-existing-process |
| [`ops/architecture/AGENTIC_ACTIONS.md`](../ops/architecture/AGENTIC_ACTIONS.md) | User goal â†’ 7-agent network â†’ 5 typed actions â†’ outcome |
| [`ops/architecture/Q_vs_BEDROCK.md`](../ops/architecture/Q_vs_BEDROCK.md) | Amazon Q vs Bedrock division-of-roles + decision matrix |
| [`docs/ARCHITECTURE_DIAGRAM.md`](./ARCHITECTURE_DIAGRAM.md) | ASCII + Mermaid diagrams |

## Architecture Decision Records (ADRs)

| ID | Decision |
|---|---|
| [ADR-0001](../ops/adr/0001-langgraph-over-raw-orchestration.md) | Use LangGraph for the 7-agent DAG |
| [ADR-0002](../ops/adr/0002-postgres-skip-locked-queue.md) | Postgres SKIP LOCKED for the case queue |
| [ADR-0003](../ops/adr/0003-per-tenant-bedrock-guardrails.md) | Per-tenant Bedrock Guardrail attached at InvokeModel |
| [ADR-0004](../ops/adr/0004-pluggable-retrieval-behind-one-schema.md) | Pluggable retrieval (Bedrock KB â†” Q Business) behind one schema |
| [ADR-0005](../ops/adr/0005-genai-gateway-as-in-process-wrapper.md) | GenAI Gateway as in-process LLMClient wrapper |
| [ADR-0006](../ops/adr/0006-exact-match-response-cache-not-semantic.md) | Exact-match SHA-256 response cache (not semantic) |
| [ADR-0007](../ops/adr/0007-review-gate-as-langgraph-node.md) | HITL review_gate as a LangGraph node |
| [ADR-0008](../ops/adr/0008-evidence-pack-sha256-bundle.md) | Evidence Pack as single tamper-evident SHA-256 JSON bundle |

## Industrialization

| Doc | Purpose |
|---|---|
| [`ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md`](../ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md) | Ravi Kumar's AI velocity gap â†’ ClinCase positioning + ROI |
| [`ops/industrialization/CHECKLIST.md`](../ops/industrialization/CHECKLIST.md) | Agent Foundry stage gates: Discover Â· Design Â· Build Â· Scale |
| [`ops/neuro-san-integration/clincase-network.hocon`](../ops/neuro-san-integration/clincase-network.hocon) | Neuro-SAN AAOSA-format agent network definition |
| [`ops/agent-foundry/agent-foundry-manifest.yaml`](../ops/agent-foundry/agent-foundry-manifest.yaml) | Agent Foundry bundle manifest (AgentSpec conventions) |
| [`ops/aws/agentcore/deployment.yaml`](../ops/aws/agentcore/deployment.yaml) | AWS Bedrock AgentCore deployment manifest (apply-ready) |
| [`ops/kiro/HOOKS.md`](../ops/kiro/HOOKS.md) | Kiro IDE Hooks for SDLC + Flowsource alignment |

## SRE & operations

| Doc | Purpose |
|---|---|
| [`ops/SCALING.md`](../ops/SCALING.md) | Capacity model â€” 1K â†’ 10K â†’ 100K cases/day |
| [`ops/sre/SLO.yaml`](../ops/sre/SLO.yaml) | 7 SLOs with PagerDuty burn-rate alerts |
| [`ops/sre/RUNBOOK.md`](../ops/sre/RUNBOOK.md) | 7 named incidents Â· diagnose+fix Â· post-mortem template |
| [`ops/sre/LOAD_TEST_RESULTS.md`](../ops/sre/LOAD_TEST_RESULTS.md) | 5-tier scalability evidence (Tier 1 measured) |
| [`ops/multi-tenant/ONBOARDING.md`](../ops/multi-tenant/ONBOARDING.md) | Per-tenant customer onboarding playbook |

## Demo & pitch

| Doc | Purpose |
|---|---|
| [`ops/demo/CLINCASE_MVP_DECK.pptx`](../ops/demo/CLINCASE_MVP_DECK.pptx) | 13-slide MVP pitch deck |
| [`ops/demo/PITCH_SCRIPT.md`](../ops/demo/PITCH_SCRIPT.md) | Verbatim 5-min pitch script with word counts |
| [`ops/demo/SPEAKER_NOTES.md`](../ops/demo/SPEAKER_NOTES.md) | Per-slide speaker notes |
| [`ops/demo/PITCH_ONE_LINER.md`](../ops/demo/PITCH_ONE_LINER.md) | 10s / 30s / 60s elevator pitch versions |
| [`ops/demo/COGNIZANT_NEWS_TALKING_POINTS.md`](../ops/demo/COGNIZANT_NEWS_TALKING_POINTS.md) | 3 stage-ready opening lines for the demo |
| [`ops/demo/DEMO_DAY_CHECKLIST.md`](../ops/demo/DEMO_DAY_CHECKLIST.md) | T-24h preflight + T-0 minute-by-minute + Q&A + fallbacks |
| [`ops/demo/QA_DRILL.md`](../ops/demo/QA_DRILL.md) | First 30 anticipated Q&A |
| [`ops/demo/ANTICIPATED_QUESTIONS.md`](../ops/demo/ANTICIPATED_QUESTIONS.md) | 20 additional Q&A beyond QA_DRILL |
| [`ops/demo/EDGE_CASES.md`](../ops/demo/EDGE_CASES.md) | 28 named edge cases (trigger Â· expected Â· file path Â· test pointer) |
| [`ops/demo/MVP_COMPLETENESS.md`](../ops/demo/MVP_COMPLETENESS.md) | Every rubric phrase mapped to specific app evidence |
| [`ops/demo/SMOKE_TEST_RESULTS.md`](../ops/demo/SMOKE_TEST_RESULTS.md) | Last live smoke test result |
| [`ops/demo/CASE_STUDY_VIGNETTE.md`](../ops/demo/CASE_STUDY_VIGNETTE.md) | Maria Chen 2026-format case study |
| [`ops/demo/COGNIZANT_GO_TO_MARKET.md`](../ops/demo/COGNIZANT_GO_TO_MARKET.md) | Day 0 â†’ Day 90 commercialization plan |
| [`ops/demo/LEAVE_BEHIND.md`](../ops/demo/LEAVE_BEHIND.md) | 1-page printable handout for judges |
| [`ops/demo/PITCH_DECK.md`](../ops/demo/PITCH_DECK.md) | Long-form pitch narrative (text version of the deck) |
| [`ops/demo/VIDEO_SCRIPT.md`](../ops/demo/VIDEO_SCRIPT.md) | Video walkthrough script |
| [`ops/demo/AUDIT_DEMO_QUERIES.sql`](../ops/demo/AUDIT_DEMO_QUERIES.sql) | SQL queries to show during the audit-readiness portion |

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
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | lint Â· pytest Â· tsc Â· pip-audit Â· bandit Â· Semgrep Â· CycloneDX SBOM Â· multi-arch ECR Â· Terraform plan |
| [`.github/workflows/deploy-prod.yml`](../.github/workflows/deploy-prod.yml) | OIDC Â· staging smoke Â· GitHub-environment manual approval Â· canary 10% Â· auto-promote |

## Kiro IDE

| Path | Purpose |
|---|---|
| [`.kiro/specs/`](../.kiro/specs/) | Auto-generated 85-file Kiro spec library (regenerated by exporter) |
| [`.kiro/hooks/`](../.kiro/hooks/) | 3 working hook scripts: regenerate-specs, architecture-boundary-check, verify-foundry-manifest |
| [`ops/kiro/HOOKS.md`](../ops/kiro/HOOKS.md) | Kiro Hooks documentation + Flowsource alignment |

## Backend code (high-level pointers)

| Path | What lives there |
|---|---|
| `backend/app/main.py` | FastAPI app composition + lifespan |
| `backend/app/agents/framework/` | `Agent[I, O]` base + lifecycle + grader + budget + cache + guardrails + trace_sink |
| `backend/app/agents/<parent>/` | Each of 7 parent agents (orchestrator + node + schemas + sub-agents) |
| `backend/app/agents/manifest.py` | Auto-discovery via `pkgutil.iter_modules(app.agents.*)` |
| `backend/app/llm/gateway.py` | GenAI Gateway (per-tenant policy + quota + audit) |
| `backend/app/api/` | 17 API route modules |
| `backend/app/integrations/{trizetto,amazon_q,kiro}/` | External system adapters |
| `backend/app/compliance/cms_0057f.py` | CMS-0057-F live scorecard |
| `backend/app/business_value/` | ROI Â· Star Ratings Â· provider abrasion |
| `backend/app/jobs/queue.py` | Postgres SKIP LOCKED case queue |
| `backend/app/streaming.py` | SSE pub/sub (in-process + Redis backends) |
| `backend/scripts/smoke_test.py` | 5-layer self-check |
| `backend/scripts/build_deck.py` | Programmatic PPTX deck builder |

## Frontend code (high-level pointers)

| Path | What lives there |
|---|---|
| `frontend/src/main.tsx` | Router + AuthProvider |
| `frontend/src/components/AppShell.tsx` | TopBar + Sidenav + main outlet |
| `frontend/src/routes/` | 17 route components incl. `/architecture`, `/roi`, `/compliance`, `/industrialize` |
| `frontend/src/lib/api.ts` | Typed API client (mirrors all 59 backend routes) |
| `frontend/src/lib/sse.ts` | SSE trace stream consumer |
