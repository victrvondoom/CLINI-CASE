# ClinCase — Chaos Engineering Playbook

**Audience:** ClinCase SRE rotation · Cognizant TriZetto on-call SA · auditor verifying production-grade resilience

> *"In a world of complex distributed systems, hope is not a strategy."* — Netflix Chaos Monkey origin paper.

ClinCase's reactive runbook ([`RUNBOOK.md`](./RUNBOOK.md)) covers what to do **after** an incident. This playbook covers what to break **on purpose** — quarterly — so the runbook never gets surprised.

## The 5 named experiments

Each experiment has: **hypothesis** (what should NOT happen), **mechanism** (how to inject), **metrics** (what to watch), **expected outcome** (what success looks like), **rollback** (how to stop).

### EXP-01 — Bedrock 5xx storm in `ap-south-1`

**Hypothesis:** A 50% Bedrock 5xx rate over 5 minutes does NOT cascade into customer-facing 5xx > 1%.

**Mechanism:** AWS Fault Injection Simulator (FIS) — `aws:bedrock:fault` action. 5-minute window, 50% failure rate.

**Metrics:**
- `clincase_circuit_breaker_state{model_id="apac.anthropic.claude-sonnet-4-6"}` should transition `CLOSED → OPEN` within 60s of injection
- `rate(clincase_agent_invocations_total{status="error"}[5m])` should NOT exceed 5%
- `histogram_quantile(0.95, clincase_case_duration_seconds_bucket)` should NOT exceed 120s
- `clincase_jobs_queue_depth{status="queued"}` should NOT exceed 50 above baseline

**Expected outcome:** Circuit breaker OPENs Sonnet within 60s; ModelRouter escalates Haiku → Sonnet on retry, but with breaker OPEN, agents fail fast with `CircuitBreakerOpen` instead of waiting 30s for timeout. Customer sees fast-503 with `Retry-After`. Queue backs up but recovers within 10 min after experiment ends.

**Rollback:** FIS auto-stops at 5-minute window; re-verify breaker transitions back through HALF_OPEN → CLOSED.

### EXP-02 — Worker pod kill during in-flight DAG

**Hypothesis:** Killing a worker pod mid-DAG-run does NOT lose the case; janitor reaps the stale heartbeat and another worker resumes.

**Mechanism:** `kubectl delete pod clincase-worker-<pod> -n clincase --grace-period=5` 30 seconds after a case starts running.

**Metrics:**
- The case's `case_jobs.status` should transition `running → queued → running` within 90s (heartbeat-stale + janitor reap interval)
- `case_jobs.attempts` should increment by 1
- The case's final decision row should still write within 3 minutes total (1 minute extra over normal)

**Expected outcome:** Janitor (`reap_stale` in `app/jobs/queue.py`) reaps the stale heartbeat after `2 × heartbeat_interval = 60s`; case requeued; another worker claims; case completes.

**Rollback:** None — this is K8s-default behavior.

### EXP-03 — Postgres primary failover

**Hypothesis:** RDS Aurora primary failover does NOT cause case data loss or > 60s of customer-facing 5xx.

**Mechanism:** `aws rds reboot-db-instance --db-instance-identifier clincase-primary --force-failover`.

**Metrics:**
- `db.connected` log entries appear within 30s of failover trigger
- `clincase_jobs_queue_depth{status="running"}` jobs should NOT lose state — verify `case_jobs.heartbeat_at` continues incrementing post-failover
- API `/healthz/deep` should report `database.status=ok` within 60s
- No case_runs row should be incomplete (every started case finishes or is requeued)

**Expected outcome:** asyncpg pool reconnects with exponential backoff; in-flight DAG runs that were checkpointed survive; uncheckpointed DAG runs are reaped by the janitor and requeued.

**Rollback:** Failover is reversible via another forced reboot if needed.

### EXP-04 — Redis (SSE pub/sub) outage

**Hypothesis:** Redis going down does NOT block agent execution; only SSE event fan-out is degraded.

**Mechanism:** Stop the redis container (or set `REDIS_URL=""` env via ConfigMap reload).

**Metrics:**
- Agent runs continue: `clincase_cases_total{status="done"}` continues to increment
- SSE events to NEW connections fail-soft (logged, not raised)
- Existing SSE connections receive a final `done` event before disconnecting
- `streaming.redis.publish_failed` warning appears in logs but does NOT propagate

**Expected outcome:** Agents complete; coordinator's browser stops receiving live trace events but `GET /api/v1/cases/{id}/audit` still returns the persisted trace. Partial degradation, not full outage.

**Rollback:** Restart Redis; new SSE connections work; old connections need page refresh.

### EXP-05 — TriZetto Gateway 100% rejection

**Hypothesis:** TriZetto Gateway returning 503 for all submits does NOT block case decisions; submit becomes a separately-retryable user action.

**Mechanism:** Stop the mock TriZetto receiver (or for live Gateway, ask Cognizant to flip the dev tenant to deny mode).

**Metrics:**
- Case runs complete normally
- Decisions are persisted
- `POST /api/v1/integrations/trizetto/submit` returns `accepted: false` with a clear error
- The user can retry the submit later when Gateway recovers

**Expected outcome:** TriZetto Gateway is in the saga's "downstream system" tier. Its failure does NOT roll back the in-house decision write — the saga compensation is a "retry submit" pattern, not a DB rollback. Case remains in `approved` status; a future re-submit succeeds.

**Rollback:** Restart mock receiver; verify pending submits succeed.

## Quarterly cadence

Each quarter, run all 5 experiments in sequence on staging:

| Quarter start week | Experiment | Owner |
|---|---|---|
| Week 1 | EXP-01 (Bedrock 5xx storm) | TL |
| Week 2 | EXP-02 (Worker pod kill) | TL |
| Week 3 | EXP-03 (Postgres failover) | TL + DBA |
| Week 4 | EXP-04 (Redis outage) | TL |
| Week 5 | EXP-05 (TriZetto Gateway down) | TL + Cognizant TriZetto SA |

Each experiment ends with a 1-page summary in `ops/sre/chaos-results/EXP-NN-YYYY-Q.md` covering: did the hypothesis hold? what surprised us? what action items came out?

## Why this is industry-grade

- **Netflix Chaos Monkey heritage** — the canonical pattern; every Tier-1 SRE org runs it
- **AWS Fault Injection Simulator** — the AWS-native primitive; FIS supports Bedrock fault injection per [AWS FIS docs](https://docs.aws.amazon.com/fis/)
- **Each experiment has a rollback** — not "we kill it and pray"; each is bounded and reversible
- **Hypotheses written down BEFORE running** — distinguishes science from spelunking

## Production-grade chaos requires production-grade observability

These experiments are only useful if the metrics are queryable. We have:
- `/metrics` Prometheus endpoint
- 7 SLOs in `ops/sre/SLO.yaml` with PagerDuty burn-rate alerts
- OpenTelemetry distributed tracing (round 9)
- Per-model circuit breaker snapshots at `/api/v1/llm-gateway/circuit-breakers`

Without these, chaos is noise. With them, chaos is preventive.

## What's deferred to post-pilot

- ⚪ AWS Fault Injection Simulator Terraform — apply-ready stub TODO at `ops/terraform/fis/`
- ⚪ Game-day calendar scheduling automation
- ⚪ Cross-region failover experiment (requires multi-region apply first)

## Sources

- Netflix Chaos Engineering — https://netflixtechblog.com/the-netflix-simian-army-16e57fbab116
- Principles of Chaos Engineering — https://principlesofchaos.org/
- AWS FIS — https://aws.amazon.com/fis/
