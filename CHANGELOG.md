# Changelog

All notable changes to ClinCase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] â€” 2026-05-03

### Round 8 â€” demo-readiness & rubric coverage

#### Added
- `ops/demo/CLINCASE_MVP_DECK.pptx` â€” 13-slide MVP deck
- `ops/demo/PITCH_SCRIPT.md` â€” verbatim 5-minute pitch script with word counts
- `ops/demo/SPEAKER_NOTES.md` â€” per-slide speaker notes
- `ops/demo/ANTICIPATED_QUESTIONS.md` â€” 20 Q&A beyond the existing QA_DRILL
- `ops/demo/LEAVE_BEHIND.md` â€” 1-page printable handout for judges
- `ops/demo/COGNIZANT_NEWS_TALKING_POINTS.md` â€” 3 stage-ready opening lines
- `ops/demo/PITCH_ONE_LINER.md` â€” 10-second elevator pitch card
- `ops/adr/0001-0008` â€” 8 canonical Architecture Decision Records (Nygard format)
- `ops/sre/LOAD_TEST_RESULTS.md` â€” 5-tier scalability evidence (Tier 1 measured, Tiers 2-5 procedure-defined)
- `ops/demo/EDGE_CASES.md` â€” 28 named edge cases across 6 categories
- `ops/demo/DEMO_DAY_CHECKLIST.md` â€” T-24h preflight + T-0 minute-by-minute + Q&A + fallbacks
- `ops/demo/MVP_COMPLETENESS.md` â€” every rubric phrase mapped to specific app evidence
- `ops/demo/SMOKE_TEST_RESULTS.md` â€” last live smoke test result
- `backend/scripts/smoke_test.py` â€” 5-layer self-check
- `backend/scripts/build_deck.py` â€” programmatic deck builder
- Backend `/api/v1/version` â€” git SHA + uptime + build metadata
- Backend `/api/v1/capabilities` â€” feature-flag snapshot for judges
- Backend `/api/v1/healthz/deep` â€” per-layer self-check (5 layers + integrations)
- Request-ID middleware â€” propagates `X-Request-Id` through every request + structlog context
- Top-level `README.md` rewritten as judge-first-impression
- `LICENSE` (MIT)
- `CONTRIBUTING.md`
- `SECURITY.md` + `frontend/public/.well-known/security.txt`
- `ROADMAP.md`
- `ARCHITECTURE.md` (top-level pointer)
- `docs/INDEX.md` (every doc with one-line purpose)
- `docs/ARCHITECTURE_DIAGRAM.md` (ASCII + Mermaid diagrams)
- `.editorconfig`
- Makefile targets: `smoke`, `deck`, `preflight`, `frontend.typecheck`, `kiro.export`, `tf.fmt`, `tf.validate`

### Round 7 â€” rubric coverage
- Smoke test PASSED across all 5 layers (56 routes, 7 parents, 22 sub-agents)

### Round 6 â€” 2026-trend alignment
- `ops/architecture/AI_ADAPTATION_GAP.md` â€” conceptual peer of velocity gap
- `ops/architecture/AGENTIC_ACTIONS.md` â€” user goal â†’ 7-agent network â†’ 5 typed actions â†’ outcome
- `ops/terraform/s3-vectors/` â€” 6-file Terraform module for S3 Vectors substrate
- `ops/demo/CASE_STUDY_VIGNETTE.md` â€” Maria Chen 2026-format case study
- Updated `/architecture/layers` with adaptation gap + Flowsource shape + agentic capital framing
- Flowsource alignment block in `ops/kiro/HOOKS.md`

### Round 5 â€” governed GenAI Gateway
- `app/llm/gateway.py` â€” literal in-process GenAI Gateway (per-tenant model allowlist, 24h quota, content-safety, audit)
- `app/api/llm_gateway.py` â€” `/llm-gateway/usage` + `/policy` endpoints
- `app/llm/factory.py` â€” wraps underlying LLMClient with Gateway
- `ops/terraform/bedrock-vpc-endpoint/` â€” 7-file PrivateLink + IAM with per-model-id condition
- `ops/architecture/Q_vs_BEDROCK.md` â€” division-of-roles doc with decision matrix
- `ops/kiro/HOOKS.md` + `.kiro/hooks/` â€” 3 working hook scripts for SDLC discipline

### Round 4 â€” 5-layer formal architecture
- `ops/architecture/TARGET_ARCHITECTURE.md` â€” 5-named-layer canonical doc
- `ops/architecture/BUSINESS_USE_CASE.md` â€” 4 KPIs with target ranges + per-component impact map
- `app/api/architecture.py` + `frontend/src/routes/Architecture.tsx` â€” live introspectable

### Round 3 â€” AI velocity gap industrialization
- `ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md`
- `ops/industrialization/CHECKLIST.md` â€” Discover Â· Design Â· Build Â· Scale gates
- `.github/workflows/ci.yml` + `deploy-prod.yml`
- `ops/sre/SLO.yaml` (7 SLOs) + `ops/sre/RUNBOOK.md` (7 named incidents)
- `ops/multi-tenant/ONBOARDING.md`

### Round 2 â€” Industrialize Pack
- Live frontend wiring of all Impact Pack endpoints
- `app/api/evidence_pack.py` â€” auditor-grade SHA-256 bundle
- `ops/neuro-san-integration/clincase-network.hocon` â€” AAOSA agent network
- `ops/agent-foundry/agent-foundry-manifest.yaml` â€” Agent Foundry bundle descriptor
- `ops/aws/agentcore/deployment.yaml` â€” Bedrock AgentCore deployment manifest
- `app/api/responsible_ai.py` â€” model card with NIST AI RMF + ISO 42001 + EU AI Act
- `frontend/src/routes/{ROI,Industrialize}.tsx` â€” interactive pages

### Round 1 â€” Impact Pack
- `app/integrations/trizetto/` â€” Facets v3 + QNXT v2 adapters with SHA-256 tamper hash
- `app/compliance/cms_0057f.py` â€” live compliance scorecard
- `app/business_value/` â€” per-case ROI Â· org rollup Â· Star projection Â· provider abrasion
- `app/integrations/kiro/exporter.py` â€” auto-generates `.kiro/specs/` (85 files)
- `app/integrations/amazon_q/client.py` â€” Q Business retrieval client
- `ops/demo/COGNIZANT_GO_TO_MARKET.md` â€” Day 0 â†’ Day 90 commercialization plan

### Foundation
- 7-agent LangGraph DAG with conditional edges (HITL gate, DENY-path)
- 22 sub-agents auto-discovered via `pkgutil`
- `Agent[I, O]` framework with full production lifecycle
- `BudgetTracker` reservation pattern
- 4 Guardrails (Schema, PHI, Citation, Token-budget)
- `ModelRouter` (Haiku â†’ Sonnet escalation)
- `TraceSink` ABC (Postgres + InMemory)
- `case_jobs` queue (Postgres SKIP LOCKED)
- Per-org quotas, deterministic response cache
- React 18 + TypeScript strict frontend with 17 routes
- MCP server with 5 tools
- Da Vinci PAS endpoint
- Multi-region + provisioned-throughput Terraform stubs

---

## [Unreleased] â€” post-pilot roadmap

See [`ROADMAP.md`](ROADMAP.md) for what comes next.
