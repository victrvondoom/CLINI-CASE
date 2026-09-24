# ClinCase — Roadmap

**Companion to:** [`ops/industrialization/CHECKLIST.md`](ops/industrialization/CHECKLIST.md) — Agent Foundry stage gates.

## Now

- ✅ 7-agent prior-authorization pipeline with HITL review, evidence packs and the live pipeline console
- ✅ OncoTwin patient digital twin, validated on synthetic cohorts ([`docs/ONCOTWIN.md`](docs/ONCOTWIN.md))
- 🟡 AWS Bedrock as the default LLM provider (`ops/aws/MIGRATION_RUNBOOK.md`)
- 🟡 First pilot customer

## Next (Day 0 → Day 90 of the first pilot)

| Day | Milestone | Status |
|---|---|---|
| 0   | First Facets/QNXT pilot customer signs | awaiting go-ahead |
| 7   | Per-tenant Bedrock Guardrail provisioned · TriZetto Gateway URL configured | doc'd in `ops/multi-tenant/ONBOARDING.md` |
| 14  | First synthetic case live in pilot env | doc'd |
| 21  | First production case live with Evidence Pack | doc'd |
| 30  | First reviewer signoff on a HITL pause (CA SB 1120 verification) | doc'd |
| 45  | Bedrock Provisioned Throughput pinned (1 MU Sonnet OneMonth) | terraform apply-ready |
| 60  | Second specialty (cardiology) live via Kiro spec edit | spec-export demonstrated |
| 90  | First pilot ROI report published | open |

## After Day 90 (post-pilot)

These are the items deferred from the initial build scope. Each has an explicit "why later" rationale in either an ADR or a SCALING.md gap entry.

### Production hardening
- **Datadog LLM Observability SDK init** (`backend/app/observability/datadog.py`) — hallucination eval, prompt-injection scanner, token/cost SLOs ported to Datadog from the current Prometheus-shaped definitions in `ops/sre/SLO.yaml`. ~1-day port.
- **AgentCore Evaluate API as CI quality gate** — wrap `backend/tests/agents/` deterministic eval cases as an AgentCore Evaluate suite that gates the deploy pipeline.
- **Per-tenant Bedrock Guardrail Terraform automation** — currently per-customer provisioning is documented; should be a reusable Terraform module under `ops/terraform/per-tenant/`.
- **AWS Lambda Tenant Isolation Mode** ([GA early 2026](https://www.dataa.dev/2026/02/28/aws-lambda-tenant-isolation-mode-multi-tenant-saas-2/)) — Firecracker MicroVM per-tenant hardware isolation. Adopt when first customer that requires it asks.
- **`agent_runs` async-batched S3 archival** — at 100K cases/day the per-row Postgres write becomes a bottleneck. Batched 5-second-window flush via Lambda → S3 → Athena. Designed in `ops/SCALING.md` § "100,000 cases/day"; ready to implement.

### Specialty expansion
- **Cardiology** — Kiro spec edit + Hook regen pattern proves the multi-vertical story. Day 60 milestone above.
- **Behavioral health** — Day-180 target.
- **Transplant** — Day-365 target (transplant PA is the highest-stakes specialty).

### OncoTwin
- Validation on real longitudinal cohorts before any clinical use.
- Sub-daily signal ingestion, so shorter risk horizons can be offered.

### Multi-region active/active
- Terraform module ready (`ops/terraform/multi-region/`). Apply when first customer demands < 60-second RTO across regions.

### Semantic response cache (vs the current exact-match cache)
- ADR-0006 deferred this. Adopt when (a) Bedrock Titan Embeddings is part of the cost basis already and (b) a production-grade safety review of the false-positive risk in clinical decision support is complete.

### MCP A2A interop
- ClinCase's MCP server is the producer side. Subscribe to athenahealth's MCP server (HIMSS 2026 launch) for provider-side EHR data on-demand.

## Strategic direction (post-Day-365)

- **Two-sided platform** — same ClinCase codebase, run from the payer's perspective for adverse-determination quality control. ADR for this would land in 2027.
- **Agent marketplace listing** — ClinCase as the reference oncology specialty bundle that other specialty bundles fork from (cardiology, behavioral health, transplant). Stage = Discover for each new vertical.
- **Real-time PA decisioning** as the AHIP 2027 mandate hits. ClinCase's 90-second decision is already inside the spec; the bottleneck moves from ClinCase to the customer's downstream claims engine.
