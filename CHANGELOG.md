# Changelog

All notable changes to ClinCase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **OncoTwin**, a patient digital twin layered on top of the prior-auth pipeline: living twin state, personalised baselines, multimodal fusion, change-point and trajectory intelligence, what-if simulation, twin memory and a clinician-gated handoff into ClinCase. See [`docs/ONCOTWIN.md`](docs/ONCOTWIN.md).
- OncoTwin CI job: tests, the one-command synthetic journey and the red-team stress test.

### Changed
- `README.md` rewritten as product documentation.
- Vulnerability reports now go through GitHub private security advisories (`SECURITY.md`, `.well-known/security.txt`).
- Demo accounts and the demo organisation renamed; existing databases are migrated on the next boot.

### Removed
- Slide decks, presentation scripts and printed handouts.

---

## [0.1.0] — 2026-05-03

### Agents and orchestration
- 7-agent LangGraph DAG with conditional edges (HITL gate, DENY path)
- 22 sub-agents auto-discovered via `pkgutil`
- `Agent[I, O]` framework with full production lifecycle
- `BudgetTracker` reservation pattern
- 4 guardrails (schema, PHI, citation, token budget)
- `ModelRouter` (Haiku → Sonnet escalation)
- `TraceSink` ABC (Postgres + in-memory)
- Deterministic sub-agent response cache
- `case_jobs` queue (Postgres `SKIP LOCKED`) and per-org quotas

### GenAI Gateway
- `app/llm/gateway.py` — in-process GenAI Gateway (per-tenant model allowlist, 24h quota, content safety, audit)
- `app/api/llm_gateway.py` — `/llm-gateway/usage` and `/policy` endpoints
- `app/llm/factory.py` — wraps the underlying `LLMClient` with the Gateway

### Integrations
- `app/integrations/trizetto/` — Facets v3 + QNXT v2 adapters with SHA-256 tamper hash
- `app/integrations/amazon_q/` — Amazon Q Business retrieval client
- `app/integrations/kiro/exporter.py` — generates the `.kiro/specs/` library
- MCP server with 5 tools
- Da Vinci PAS endpoint
- `ops/neuro-san-integration/clincase-network.hocon` — AAOSA agent network
- `ops/agent-foundry/agent-foundry-manifest.yaml` — Agent Foundry bundle descriptor
- `ops/aws/agentcore/deployment.yaml` — Bedrock AgentCore deployment manifest

### Compliance, audit and business value
- `app/compliance/cms_0057f.py` — live CMS-0057-F scorecard
- `app/api/evidence_pack.py` — auditor-grade SHA-256 evidence bundle
- `app/api/responsible_ai.py` — model card with NIST AI RMF, ISO 42001 and EU AI Act mappings
- `app/business_value/` — per-case ROI, org rollup, Star Ratings projection, provider abrasion

### Operations
- `/api/v1/version`, `/api/v1/capabilities` and `/api/v1/healthz/deep` endpoints
- Request-ID middleware propagating `X-Request-Id` through every request and log line
- `backend/scripts/smoke_test.py` — 5-layer self-check
- `ops/sre/SLO.yaml` (7 SLOs), `ops/sre/RUNBOOK.md` (7 named incidents), `ops/sre/LOAD_TEST_RESULTS.md`
- `ops/multi-tenant/ONBOARDING.md`
- `.github/workflows/ci.yml` and `deploy-prod.yml`
- Makefile targets: `smoke`, `preflight`, `frontend.typecheck`, `kiro.export`, `tf.fmt`, `tf.validate`

### Infrastructure
- Terraform modules: multi-region, provisioned throughput, Bedrock VPC endpoint, S3 Vectors
- Kubernetes manifests for the API and worker tiers

### Frontend
- React 18 + TypeScript strict frontend with 17 routes, including `/architecture`, `/roi`, `/compliance` and `/industrialize`

### Documentation
- `ops/architecture/` — target architecture, business use case, AI adaptation gap, agentic actions, Q vs Bedrock
- `ops/adr/0001-0008` — 8 Architecture Decision Records (Nygard format)
- `ops/kiro/HOOKS.md` and `.kiro/hooks/`
- `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`, `ROADMAP.md`, `ARCHITECTURE.md`
- `docs/INDEX.md` and `docs/ARCHITECTURE_DIAGRAM.md`

---

See [`ROADMAP.md`](ROADMAP.md) for what comes next.
