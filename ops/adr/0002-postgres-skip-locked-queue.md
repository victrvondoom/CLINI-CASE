# ADR-0002 — Postgres SKIP LOCKED for the case-job queue

## Status
Accepted · 2026-04-15

## Context

ClinCase needs a job queue for asynchronous case execution: the API tier accepts a case via `POST /run-async` and returns a 202 immediately; one of N worker replicas picks the job up, runs the 7-agent DAG, and writes the result back. Requirements:

- **Race-free concurrent claim** at any worker count (5 → 100 replicas).
- **Survives restarts** — a case in flight when a worker crashes must be picked up by another worker.
- **Idempotent submit** — same client submitting twice must not produce duplicate runs.
- **Audit-grade trail** — every job's status transitions reproducible for CMS-0057-F § IV.D.
- **Same RPO/RTO as the primary DB** — ClinCase's single source of truth is RDS Aurora; the queue must not introduce a different recovery profile.

Three options were on the table:

1. **Postgres `SELECT … FOR UPDATE SKIP LOCKED`** — a single table in the same RDS cluster.
2. **Redis Streams** — purpose-built for this pattern; XADD/XREADGROUP semantics.
3. **AWS SQS** — managed, durable, native AWS integration.

## Decision

**Postgres SKIP LOCKED.**

Implementation in `app/jobs/queue.py`. Schema is a single `case_jobs` table with status + heartbeat. Workers do `SELECT id FROM case_jobs WHERE status='queued' ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1` inside a transaction, then `UPDATE … SET status='running', claimed_by=...`. A background janitor reaps stale-heartbeat jobs.

## Consequences

**Positive**
- **One fewer dependency.** Already deploying RDS Aurora; not deploying a Redis cluster or paying for SQS.
- **Same RPO/RTO as the primary DB.** A region-failover that recovers Aurora also recovers the queue (and recovers cases mid-execution via heartbeat reaping). Multi-region module (`ops/terraform/multi-region/`) is RDS-native.
- **Operationally inspectable.** "Show me the queue right now" = a single `SELECT * FROM case_jobs WHERE status IN ('queued','running')`. No bespoke admin tooling.
- **Idempotency by unique index.** The `idempotency_key` column is `UNIQUE`; duplicate submits return the same `job_id` row.
- **Race-free at any scale.** Postgres SKIP LOCKED is the canonical pattern; performance verified concurrent-claim test in `tests/`.

**Negative**
- **Higher RDS write load** than a separate queue. At 10K cases/day this is ~10K transactions/day, well within Aurora `db.r6g.xlarge`'s capacity (capacity model `ops/SCALING.md`).
- **Polling-based.** Workers poll every 2 s when idle. At idle this is one cheap query/worker/2s. Not a concern at our scale; would matter at 1000+ workers (we'd add LISTEN/NOTIFY then).

**Neutral**
- `pg_stat_activity` shows the queue traffic. CloudWatch can scrape `clincase_jobs_queue_depth` from `/metrics` for HPA.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Redis Streams | Adds a second stateful service (more deploy surface, separate RPO/RTO, separate AWS-Health surface). Save it for the `streaming.py` SSE pub/sub where it's actually needed. |
| AWS SQS | Adds a third recovery profile (Aurora + Redis + SQS). Idempotent submit + audit-grade trail are awkward — SQS doesn't expose its message log; we'd still need a Postgres table for the trail. Net: same Postgres write load, plus SQS bill. |
| Bedrock-managed orchestration | Doesn't apply (LangGraph DAG is the orchestrator; this queue is one level above). |

## References

- Postgres SKIP LOCKED docs: https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE
- Implementation: `backend/app/jobs/queue.py`
- Capacity model: `ops/SCALING.md`
- Multi-region failover behavior: `ops/terraform/multi-region/rds.tf`
