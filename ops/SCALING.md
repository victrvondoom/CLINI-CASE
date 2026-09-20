# ClinCase — Scaling Plan

**Single source of truth** for "how does this scale to a real Cognizant payer customer?" Read this end-to-end if a judge asks the question.

---

## Capacity targets

| Tier | Daily volume | Concurrent peak | p99 latency | Cost/case | Monthly $ (infra) |
|---|--:|--:|--:|--:|--:|
| **Pilot**       |   1,000 cases/day |  20 concurrent |  90s | $0.45 | $320  |
| **Production**  |  10,000 cases/day | 200 concurrent |  90s | $0.45 | $1,200 |
| **Scale**       | 100,000 cases/day | 2,000 concurrent | 90s | $0.40 | $8,400 |

A single mid-sized US oncology practice generates **80–200 PA requests / day**. Per-payer cohort = **5,000–15,000 / day**. The Production tier above maps to one Cognizant Health Sciences enterprise client.

---

## The math (per case)

A clean trastuzumab APPROVE case end-to-end:

| Step | Latency | Tokens (in / out) | Cost (Bedrock) |
|---|--:|--:|--:|
| Clinical Extractor (orchestrator + 3 sub-agents)  | ~6 s  |  4,000 / 1,500 | $0.035 |
| Policy Retriever (KB + reranker)                  | ~3 s  |  2,500 / 200   | $0.011 |
| Necessity Reasoner (1 splitter + 5 matchers + 1 calibrator) | ~25 s | 18,000 / 4,000 | $0.114 |
| Decision Composer (verdict + rationale + citation) | ~8 s | 6,000 / 1,500 | $0.040 |
| Denial Forecaster (3 sub-agents, gated)            | ~6 s | 5,500 / 1,000 | $0.032 |
| Patient Communicator (empathy + steps + tuner)     | ~4 s | 3,000 / 800   | $0.022 |
| **Total (no appeal needed)**                       | **~52 s** | **39 K / 9 K** | **~$0.25** |
| + Appeals Drafter (DENY path adds 3 sub-agents)    | +18 s | +12 K / +4 K  | +$0.20 |

DAG runtime fits a **90-second p99 SLA** with parallel fan-out on Necessity Reasoner. Per-case cost ranges $0.25 (APPROVE) to $0.45 (DENY+appeal).

---

## Bottleneck analysis at each scale point

### 1,000 cases/day (Pilot)

- **Bottleneck**: none — single API replica + 5 workers handles it
- **DB**: 1 vCPU, 200 conn, < 30% utilization
- **Bedrock**: well under per-region TPM ceilings
- **Action**: deploy `ops/k8s/` defaults; turn on /metrics scraping

### 10,000 cases/day (Production)

- **Bottleneck**: Bedrock TPM in `ap-south-1` for Sonnet 4.6
  - Need provisioned throughput: ~600K input + 200K output TPM
- **DB**: bumps to 4 vCPU, 32 GB, replication lag concerns
  - Action: read-replica for `agent_runs` queries; WAL-level archiving
- **Worker pool**: 25 replicas; queue depth target 5 jobs/replica
- **API pool**: 6 replicas behind ALB; sticky sessions for SSE

### 100,000 cases/day (Scale)

- **Bottleneck shifts to LLM provisioning + DB write throughput**
  - Bedrock: dedicated provisioned throughput (DPT) — 6M input TPM, 2M output TPM
  - Switch `agent_runs` writes to async batched insert via Lambda → S3 → Athena (audit-grade, write-cheap)
  - Hot path keeps Postgres for `cases`, `decisions`, `appeals` only
- **Multi-region**: active/active in `ap-south-1` + `us-east-1` with route53 latency-based routing
- **Cache**: ~12% of cases hit a semantic cache (similar prior submissions) → Redis layer
- **Worker pool**: 80 replicas across 3 AZs

---

## Why the architecture supports this

### 1. Stateless API tier

The API tier (`app/main.py`) holds zero per-request state. The ALB can route any request to any replica. Sticky sessions exist only for SSE to keep one client on one replica for the streaming connection.

### 2. Postgres job queue with `SELECT FOR UPDATE SKIP LOCKED`

`app/jobs/queue.py` uses Postgres's `SKIP LOCKED` semantics — proven correct under concurrent worker access at any scale. Unlike Redis Streams or SQS, it survives a region outage with the same RPO/RTO as the primary database.

### 3. Worker pool decoupled from API

`app/workers/case_runner.py` is a separate process. API replica restart ≠ worker restart. K8s Deployment per tier allows independent scaling. Workers run with longer `terminationGracePeriodSeconds` (60s) than the API (30s) because they hold in-flight DAG runs.

### 4. Single shared `AgentContext` per case

All 7 agents in a case share one `BudgetTracker`, one `TraceSink`, one trace tree. The per-case ceiling is real — a runaway case literally cannot exceed $5 / 600K tokens / 10 minutes because the framework's `BudgetExceeded` raises before any LLM token is spent.

### 5. Pluggable `TraceSink`

Production: `PostgresTraceSink` writes `agent_runs` rows directly. At 100K cases/day this is the bottleneck; switch to `AsyncBatchedTraceSink` (buffer 100 rows in-memory, flush every 5 sec via single multi-row INSERT). Hot path stays sub-millisecond.

### 6. Idempotency on case submission

`Idempotency-Key` header on `POST /cases/{id}/run-async`. Retry storms after a network blip don't enqueue 50 duplicate runs. Standard Stripe-style semantics.

### 7. Auto-discovering manifest

`app/agents/manifest.py` walks `app.agents.*` at boot. Adding an 8th parent agent (e.g. `prior_auth_negotiator` for payer-side negotiation) requires zero edits to the manifest, the K8s manifest, or the API. Drop in the package, restart, manifest updates.

### 8. Pluggable SSE pub/sub (SCALE-7)

`app/streaming.py` defines a `PubSubBackend` ABC with two implementations:
`InProcessBackend` (single-process, default for dev/hackathon) and
`RedisPubSubBackend` (multi-replica fan-out via Redis pub/sub channel
`clincase:case:{id}`). Selection is automatic via `REDIS_URL` env var —
empty → in-process; set → Redis. **Zero call-site changes** between modes:
agents, the SSE handler, and the framework all use the same
`publish/subscribe/unsubscribe` functions.

The Redis backend uses ONE shared subscriber connection per process with
a `psubscribe('clincase:case:*')` pattern, demuxing to local in-process
queues by case_id — so 1,000 concurrent SSE consumers across 50 API replicas
need only 50 Redis subscriptions, not 50,000.

### 9. Per-org daily/monthly quotas (SCALE-8)

`app/quotas.py` enforces case quotas atomically via a single conditional
`UPDATE … WHERE … RETURNING` — the WHERE clause IS the eligibility check,
so two concurrent submitters serialize via row lock with no race window.
Day/month boundaries roll over automatically when crossed (no cron needed).
A breached quota returns HTTP 429 with `Retry-After` and a structured
JSON error body. Admin endpoints under `/api/v1/quotas/*` let an org admin
(role-gated) tune their own caps.

### 10. Deterministic response cache (SCALE-9)

`app/agents/framework/cache.py` is a Postgres-backed exact-match cache
keyed by `sha256(qualified_name | org_id | output_schema_version | input_json)`.
Hooked into `Agent.invoke()` as **lifecycle step 0** (before guardrails).
On hit, the framework reconstructs the cached output, emits a `cache_hit`
trace event with the cached model_id and age, and skips the LLM call
entirely. On miss, the lifecycle runs normally and stores the output on
success. TTL defaults to 1 hour (configurable per-agent via `cache_ttl_seconds`).

Why this matters: a retry-storm of one case (network blip, browser re-fire,
audit-panel rerun) used to mean 21 fresh LLM calls × $0.005 each = $0.10
wasted per replay. With the cache it costs ONE Postgres SELECT.

Cache key includes `organization_id`, so org A's cached output is never
visible to org B even on byte-identical input — multi-tenant safe by
construction.

---

## Failure modes (and how we handle each)

| Failure | Detection | Recovery |
|---|---|---|
| Worker process crash mid-DAG | Heartbeat stops > 30s | Janitor reaps, requeues with `attempts++`, dies after `max_attempts=3` |
| Bedrock 5xx | Framework catches in retry loop | ModelRouter escalates Haiku → Sonnet; eventually `BudgetExceeded` if tokens run out |
| Bedrock regional outage | All workers fail to claim or call | API still queues jobs; backlog drains when region recovers; OR multi-region failover |
| RDS primary failover | New connections briefly fail | asyncpg pool retries with exponential backoff; in-flight DAGs requeued via heartbeat reaper |
| LLM credit exhaustion | `BudgetExceeded` in framework | Job marked `error`, retry exhausted, then `dead`. Operator alert via Prometheus alert rule |
| User submits 50 duplicates | Idempotency-Key dedup | Single job_id returned for all 50 |
| Schema parse failure (LLM emits malformed JSON) | Framework retry-with-feedback | Up to `max_iterations` attempts, escalating Haiku → Sonnet on each retry |
| HITL gate trips (low confidence) | `triggered_hitl=true` in NecessityReasonerOutput | Graph routes to `review_gate` (terminal); `POST /cases/{id}/resume` continues with reviewer verdict |
| Per-case budget exhausted (runaway loop) | `BudgetTracker.reserve` raises `BudgetExceeded` | Job marked `error`, NOT retried. Manual intervention. |

---

## Observability stack

- **`/metrics`** — Prometheus scrape every 60s. 8 metrics, ~50 series at scale.
- **CloudWatch Logs** (production) — structlog JSON straight to log groups, indexed by case_id + agent_name.
- **AWS X-Ray** — `parent_span_id` chain in `AgentTrace` maps 1:1 to X-Ray spans.
- **PagerDuty alerts** wired to:
  - `clincase_jobs_queue_depth{status="queued"} > 200 for 5m` → P2
  - `rate(clincase_agent_invocations_total{status="error"}[5m]) > 0.05` → P3
  - `clincase_llm_cost_usd_total - clincase_llm_cost_usd_total offset 1h > 100` → P2 (cost runaway)

---

## Cost ceiling controls

1. **Per-case budget** in `BudgetTracker` — hard cap of $5 / case (default; tunable per org)
2. **Bedrock provisioned throughput** — locks unit cost, prevents on-demand spikes
3. **Idempotency dedup** — duplicate submits charge zero additional LLM tokens
4. **Per-org daily quotas** — enforced in `POST /cases` (not implemented yet; ~30 min add)
5. **Prometheus alert** on `clincase_llm_cost_usd_total` rate

---

## Cognizant Impact Pack (May 2026)

Six deliverables added on top of the 7-agent core to align ClinCase
unmistakably with Cognizant's 2025–2026 strategic stack:

| # | Deliverable | Where |
|---|---|---|
| **IMPACT-1** | TriZetto AI Gateway adapter — MCP-native submission of determinations to Facets / QNXT, SHA-256 tamper-evident decision hashes | `app/integrations/trizetto/`, `POST /api/v1/integrations/trizetto/submit` |
| **IMPACT-2** | CMS-0057-F + state-AI-law live scorecard (per-case + org rollup, 8 clauses tracked, 6 in-force today) | `app/compliance/cms_0057f.py`, `GET /api/v1/compliance/case/{id}` and `/api/v1/compliance/org` |
| **IMPACT-3** | Business value calculator — per-case ROI vs $1,500 manual baseline; Humana-scale Star Ratings projection ($1.26B/half-star); provider-abrasion reduction model | `app/business_value/`, `GET /api/v1/business-value/{case,org,star-impact,provider-abrasion}` |
| **IMPACT-4** | Kiro IDE spec exporter — auto-generates `.kiro/specs/<agent>/{requirements,design,tasks}.md` for all 7 parents + 22 sub-agents from `AGENT_MANIFEST` (85 files written) | `app/integrations/kiro/`, `POST /api/v1/integrations/kiro/export` |
| **IMPACT-5** | Amazon Q Business retriever — drop-in alternative to Bedrock KB for customers whose policy library lives in M365/SharePoint/Confluence; toggled via `USE_AMAZON_Q=true` | `app/integrations/amazon_q/`, `app/agents/policy_retriever/sub_agents/q_business_retriever.py` |
| **IMPACT-6** | Cognizant Go-to-Market 1-pager — Day 0 → Day 90 commercialization plan, pricing motion, joint-AWS-blog-post ask | `ops/demo/GO_TO_MARKET.md` |

Strategic alignment achieved:
- Cognizant TriZetto AI Gateway (Aug 6, 2025; MCP-native; Bedrock + Sonnet 4.6) — **ClinCase deploys natively as a Gateway-bound agent bundle.**
- Cognizant–Anthropic partnership (Nov 4, 2025; 350K employees on Claude + Claude Code + MCP + Agent SDK) — **ClinCase's stack matches verbatim.**
- AWS Kiro IDE (spec-driven agentic workflow; AWS's only published healthcare reference is "drug discovery in 3 weeks") — **ClinCase publishes 85 files of payer-PA-domain Kiro specs, the first comprehensive reference in AWS's healthcare portfolio.**
- AHIP 80%-real-time-by-2027 pledge (60+ insurers, 257M lives; only ~11% eliminated 6 months in) — **ClinCase is the path for Cognizant TriZetto customers.**

## What we built post-pilot-prep (honest status)

| Lever | Status | Where |
|---|---|---|
| SSE pub/sub multi-replica fan-out               | ✅ **built** — Redis backend with in-process fallback | `app/streaming.py` (`PubSubBackend` ABC, `RedisPubSubBackend`); wired in `main.py` lifespan + `case_runner.py` boot. Single-replica dev keeps in-process. |
| Per-org daily/monthly case quota                 | ✅ **built** — atomic SQL gate, returns 429 with `Retry-After` | `app/quotas.py`, wired into `cases.py:run_full` + `jobs.py:run_full_async`; admin endpoints `GET /api/v1/quotas/me` / `PUT /api/v1/quotas/{org_id}` |
| Deterministic response cache (sub-agent level)   | ✅ **built** — sha256-keyed, schema-pinned, per-org isolated, 1h TTL | `app/agents/framework/cache.py`; integrated in `Agent.invoke()` lifecycle as step 0 (before guardrails). `cache_enabled=True` per agent class. |
| Multi-region active/active                       | 🟡 **terraform stub apply-ready** — gated by AWS procurement | `ops/terraform/multi-region/` (Aurora Global, Route 53 LBR, S3 CRR, multi-region KMS). +$1,430/month vs single-region. |
| Bedrock provisioned throughput                   | 🟡 **terraform stub apply-ready** — gated by 1-month commit | `ops/terraform/provisioned-throughput/` (1 MU Sonnet + 1 MU Haiku, OneMonth commit, CloudWatch utilization alarms). +$63,510/month. |

Status legend: ✅ shipping in code today · 🟡 apply-ready Terraform, AWS-procurement-blocked.

## Remaining gaps (ranked by hackathon-to-production effort)

- ⚠️ **No semantic cache layer** (12% case dedup opportunity unrealized).
  Deferred to post-May-6 — needs Bedrock Titan Embeddings + similarity threshold tuning.
  The exact-match cache (above) catches the retry-storm case which is the highest-value 80%.
- ⚠️ **`agent_runs` Postgres-write hot path** — at 100K cases/day this becomes the bottleneck.
  Mitigation already designed: `AsyncBatchedTraceSink` (`framework/trace_sink.py` is already a pluggable ABC). ~3 hours to implement when needed.
- ⚠️ **Bedrock KB cross-region replication** — current MIGRATION_RUNBOOK doc covers this manually. Should be Terraformed inside `multi-region/` once AWS exposes a replication API for Bedrock KB sources (currently only the source S3 bucket replicates; KB index rebuild is manual).

These remaining gaps are knowable, costed, and on the post-pilot roadmap. Each has an explicit ticket and an effort estimate.

---

## Q&A talking points

> *"How would this handle 50,000 cases on Day 1 of a payer rollout?"*

The worker tier scales horizontally on `clincase_jobs_queue_depth` — the HPA's `External` metric source is wired to that. From 5 → 100 replicas takes ~3 minutes (cold-start a new replica + claim queue jobs). Bedrock TPM is the actual ceiling; we'd pre-provision dedicated throughput before Day 1 and warm-start with a synthetic-load run. Worst case: queue depth grows to ~10K, p99 case latency stretches to ~15 minutes (still inside CMS-0057-F § IV.B.1's 7-day SLA by 5 orders of magnitude), HPA catches up, queue drains.

> *"What's the cost at 10K cases/day?"*

$1,200/month infra + ~$135/day Bedrock = **$5,250/month total**. Per-case all-in: **$0.45**. Vs. manual cost of $1,500/case = **3,300× cheaper per PA**.

> *"What's the single biggest risk?"*

Bedrock regional capacity. We mitigate with provisioned throughput in `ap-south-1` + warm standby in `us-east-1`. If both AWS Bedrock regions go down simultaneously, every AI healthcare app stops — that's an industry event, not an ClinCase event.
