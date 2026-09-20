"""Postgres-backed asynchronous job queue for case-DAG runs.

Why Postgres and not Redis/SQS for the hackathon-to-production path:
  • Single dependency we already deploy (RDS Aurora in production)
  • SKIP LOCKED gives us correct concurrent claim semantics with no race
  • Survives restarts; no in-memory state to lose
  • Easy to inspect / audit ("show me the queue right now")

Schema (created idempotently on first import via `ensure_schema`):

    case_jobs (
      id              uuid PRIMARY KEY,
      case_id         text NOT NULL,
      organization_id text NOT NULL,
      idempotency_key text UNIQUE,                 -- de-dup window
      job_type        text NOT NULL,               -- "run_full", "resume", ...
      status          text NOT NULL,               -- queued | running | done | error | dead
      payload_json    jsonb NOT NULL,
      result_json     jsonb,
      error_text      text,
      attempts        int  NOT NULL DEFAULT 0,
      max_attempts    int  NOT NULL DEFAULT 3,
      claimed_at      timestamptz,
      claimed_by      text,
      heartbeat_at    timestamptz,
      created_at      timestamptz NOT NULL DEFAULT now(),
      finished_at     timestamptz
    )

The worker loop:
  1. claim: SELECT … WHERE status='queued' FOR UPDATE SKIP LOCKED LIMIT 1
  2. mark running, set claimed_by=worker_id, heartbeat_at=now()
  3. execute the DAG against the payload
  4. mark done with result_json (or error with retry-or-dead)

A janitor task reaps jobs whose heartbeat is stale ( > 2 * heartbeat_interval ).
Stale jobs get requeued (status='queued', attempts incremented) up to max_attempts,
after which they go to status='dead'.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.db import db

# =============================================================================
# Schema management
# =============================================================================


_SCHEMA = """
CREATE TABLE IF NOT EXISTS case_jobs (
    id              uuid PRIMARY KEY,
    case_id         text        NOT NULL,
    organization_id text        NOT NULL,
    idempotency_key text        UNIQUE,
    job_type        text        NOT NULL,
    status          text        NOT NULL CHECK (status IN ('queued','running','done','error','dead')),
    payload_json    jsonb       NOT NULL,
    result_json     jsonb,
    error_text      text,
    attempts        int         NOT NULL DEFAULT 0,
    max_attempts    int         NOT NULL DEFAULT 3,
    claimed_at      timestamptz,
    claimed_by      text,
    heartbeat_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz
);
CREATE INDEX IF NOT EXISTS case_jobs_status_created_idx
    ON case_jobs (status, created_at)
    WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS case_jobs_case_id_idx ON case_jobs (case_id);
"""


async def ensure_schema() -> None:
    """Idempotent schema bootstrap. Called on FastAPI startup + worker boot."""
    await db.execute(_SCHEMA)


# =============================================================================
# Public types
# =============================================================================


JobStatus = Literal["queued", "running", "done", "error", "dead"]
JobType = Literal["run_full", "resume_after_review", "draft_appeal_only"]


@dataclass
class Job:
    id: uuid.UUID
    case_id: str
    organization_id: str
    job_type: JobType
    status: JobStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    max_attempts: int
    created_at: datetime
    claimed_at: datetime | None
    finished_at: datetime | None


def _row_to_job(row: dict[str, Any]) -> Job:
    return Job(
        id=row["id"],
        case_id=row["case_id"],
        organization_id=row["organization_id"],
        job_type=row["job_type"],
        status=row["status"],
        payload=json.loads(row["payload_json"]) if isinstance(row["payload_json"], str) else row["payload_json"],
        result=(json.loads(row["result_json"]) if isinstance(row["result_json"], str) else row["result_json"]) if row.get("result_json") else None,
        error=row.get("error_text"),
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        created_at=row["created_at"],
        claimed_at=row.get("claimed_at"),
        finished_at=row.get("finished_at"),
    )


# =============================================================================
# Producer API (used by FastAPI handlers)
# =============================================================================


async def enqueue(
    *,
    case_id: str,
    organization_id: str,
    job_type: JobType = "run_full",
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
) -> Job:
    """Enqueue a job. If `idempotency_key` matches an existing job, returns it.

    Idempotency semantics: identical key → identical job. The CALLER passes a
    deterministic key (e.g. SHA256 of the request body); duplicate submissions
    of the same case body return the same job_id.
    """
    job_id = uuid.uuid4()
    if idempotency_key:
        existing = await db.fetchrow(
            "SELECT * FROM case_jobs WHERE idempotency_key = $1",
            idempotency_key,
        )
        if existing:
            return _row_to_job(dict(existing))
    row = await db.fetchrow(
        """INSERT INTO case_jobs
              (id, case_id, organization_id, idempotency_key, job_type,
               status, payload_json, max_attempts)
           VALUES ($1, $2, $3, $4, $5, 'queued', $6, $7)
           RETURNING *""",
        job_id,
        case_id,
        organization_id,
        idempotency_key,
        job_type,
        json.dumps(payload or {}),
        max_attempts,
    )
    return _row_to_job(dict(row))


async def get_job(job_id: uuid.UUID) -> Job | None:
    row = await db.fetchrow("SELECT * FROM case_jobs WHERE id = $1", job_id)
    return _row_to_job(dict(row)) if row else None


async def list_jobs_for_case(case_id: str, limit: int = 20) -> list[Job]:
    rows = await db.fetch(
        "SELECT * FROM case_jobs WHERE case_id = $1 ORDER BY created_at DESC LIMIT $2",
        case_id, limit,
    )
    return [_row_to_job(dict(r)) for r in rows]


# =============================================================================
# Consumer API (used by the worker process)
# =============================================================================


async def claim_next(*, worker_id: str) -> Job | None:
    """Atomically claim the next queued job using SELECT … FOR UPDATE SKIP LOCKED.

    Multiple workers can call this concurrently; each gets a different job
    or None. Postgres handles the locking correctly — no race.

    Implementation note: we acquire a connection from the asyncpg pool
    and run the SELECT-then-UPDATE inside a single transaction so the row
    lock from `FOR UPDATE SKIP LOCKED` survives until the UPDATE commits.
    """
    async with db.pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """SELECT id FROM case_jobs
                   WHERE status = 'queued'
                   ORDER BY created_at ASC
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1"""
        )
        if not row:
            return None
        job_id = row["id"]
        updated = await conn.fetchrow(
            """UPDATE case_jobs
                   SET status='running', attempts=attempts+1,
                       claimed_at=now(), claimed_by=$2, heartbeat_at=now()
                   WHERE id = $1
                   RETURNING *""",
            job_id, worker_id,
        )
        return _row_to_job(dict(updated))


async def heartbeat(job_id: uuid.UUID) -> None:
    """Worker pings every N seconds while running. Janitor reaps if stale."""
    await db.execute(
        "UPDATE case_jobs SET heartbeat_at = now() WHERE id = $1 AND status = 'running'",
        job_id,
    )


async def mark_done(job_id: uuid.UUID, result: dict[str, Any]) -> None:
    await db.execute(
        """UPDATE case_jobs
           SET status='done', result_json=$2, finished_at=now(), heartbeat_at=now()
           WHERE id = $1""",
        job_id,
        json.dumps(result),
    )


async def mark_error(job_id: uuid.UUID, error: str, *, dead: bool = False) -> None:
    """Mark error. If `dead=True`, jump straight to terminal 'dead' status (no retry)."""
    if dead:
        await db.execute(
            """UPDATE case_jobs
               SET status='dead', error_text=$2, finished_at=now()
               WHERE id = $1""",
            job_id, error,
        )
        return
    # Retryable error: bounce back to queued unless we've exhausted attempts
    await db.execute(
        """UPDATE case_jobs
           SET status = CASE
                WHEN attempts >= max_attempts THEN 'dead'
                ELSE 'queued'
              END,
               error_text = $2,
               finished_at = CASE
                WHEN attempts >= max_attempts THEN now()
                ELSE NULL
              END,
               claimed_at = NULL,
               claimed_by = NULL,
               heartbeat_at = NULL
           WHERE id = $1""",
        job_id, error,
    )


async def reap_stale(*, stale_after_seconds: int = 120) -> int:
    """Janitor: requeue jobs whose heartbeat is older than `stale_after_seconds`.

    Returns the number of jobs reaped. Run periodically from the worker
    process or a cron Lambda.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    rows = await db.fetch(
        """UPDATE case_jobs
           SET status = CASE
                WHEN attempts >= max_attempts THEN 'dead'
                ELSE 'queued'
              END,
               error_text = COALESCE(error_text, '') ||
                            ' [reaped at ' || now() || ' due to stale heartbeat]',
               claimed_at = NULL,
               claimed_by = NULL,
               heartbeat_at = NULL
           WHERE status = 'running' AND heartbeat_at < $1
           RETURNING id""",
        cutoff,
    )
    return len(rows)


# =============================================================================
# Telemetry
# =============================================================================


async def queue_depth() -> dict[str, int]:
    """Return {status: count} for the queue. Powers the /metrics endpoint."""
    rows = await db.fetch(
        "SELECT status, COUNT(*) AS n FROM case_jobs GROUP BY status"
    )
    out = {"queued": 0, "running": 0, "done": 0, "error": 0, "dead": 0}
    for r in rows:
        out[r["status"]] = r["n"]
    return out
