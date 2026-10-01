"""Run registry — one row per execution of a case (initial run, rerun, human-review resume).

`start_run` is the single place a run identity is minted. It serialises per case with an advisory lock so two
concurrent submissions get distinct, strictly increasing attempt numbers (a cancelled run keeps its number —
numbers are never reused), and it stamps the stable Case Intelligence ID onto the case row. All schema changes here are additive and nullable, so rows written before this module
existed remain valid (they simply carry no run id).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.db import db
from app.identity import (
    RUN_STATUSES,
    RUN_TRIGGERS,
    RunIdentity,
    case_intelligence_id,
    new_run_id,
    new_trace_id,
)

log = structlog.get_logger()

_TERMINAL = ("paused", "completed", "failed", "cancelled")

SCHEMA_SQL = """
-- Serialise concurrent API/worker starts (constraint widening below drops and re-adds a constraint).
SELECT pg_advisory_xact_lock(hashtext('clincase_run_identity_schema'));

ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;

CREATE TABLE IF NOT EXISTS case_runs (
    run_id               TEXT PRIMARY KEY,
    case_id              TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    organization_id      TEXT NOT NULL,
    case_intelligence_id TEXT NOT NULL,
    attempt_no           INTEGER NOT NULL,
    trigger              TEXT NOT NULL CHECK (trigger IN ('initial','rerun','resume')),
    parent_run_id        TEXT REFERENCES case_runs(run_id),
    trace_id             TEXT NOT NULL,
    job_id               UUID,
    status               TEXT NOT NULL DEFAULT 'running'
                         CHECK (status IN ('queued','running','paused','completed','failed','cancelled','superseded')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at          TIMESTAMPTZ,
    UNIQUE (case_id, attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_case_runs_case ON case_runs (case_id, attempt_no);

-- 'superseded' (a paused run replaced by a newer execution) was added after the first release: widen once.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'case_runs_status_check' AND pg_get_constraintdef(oid) LIKE '%superseded%'
    ) THEN
        ALTER TABLE case_runs DROP CONSTRAINT IF EXISTS case_runs_status_check;
        ALTER TABLE case_runs ADD CONSTRAINT case_runs_status_check CHECK (
            status IN ('queued','running','paused','completed','failed','cancelled','superseded'));
    END IF;
END $$;

-- The durable state of a run that stopped for human review (what the remaining agents need to continue).
CREATE TABLE IF NOT EXISTS case_run_states (
    run_id          TEXT PRIMARY KEY REFERENCES case_runs(run_id) ON DELETE CASCADE,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL,
    schema_version  INTEGER NOT NULL,
    pause_kind      TEXT NOT NULL,
    pause_reason    TEXT,
    state_json      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS trace_id TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS job_attempt INTEGER;
CREATE INDEX IF NOT EXISTS idx_agent_runs_run ON agent_runs (run_id);

ALTER TABLE decisions ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions (run_id);

ALTER TABLE appeals ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE appeals ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;

ALTER TABLE reviewer_actions ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE reviewer_actions ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;

-- /cases/{id}/resume has always recorded action 'resume_with_<verdict>', which the original CHECK rejected
-- (every resume failed with 503 on a schema-conformant database). Widen it once; idempotent.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'reviewer_actions_action_check'
          AND pg_get_constraintdef(oid) LIKE '%resume_with_approve%'
    ) THEN
        ALTER TABLE reviewer_actions DROP CONSTRAINT IF EXISTS reviewer_actions_action_check;
        ALTER TABLE reviewer_actions ADD CONSTRAINT reviewer_actions_action_check CHECK (action IN (
            'approve','override_to_approve','override_to_deny','escalate','add_note',
            'resume_with_approve','resume_with_deny','resume_with_refer'));
    END IF;
END $$;

ALTER TABLE IF EXISTS llm_invocations ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE IF EXISTS llm_invocations ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;
ALTER TABLE IF EXISTS llm_invocations ADD COLUMN IF NOT EXISTS trace_id TEXT;
"""


async def ensure_schema() -> None:
    """Idempotent; applied at API and worker start (and mirrored in db/schema.sql)."""
    await db.execute(SCHEMA_SQL)


async def _start(
    conn: Any,
    *,
    organization_id: str,
    case_id: str,
    trigger: str | None,
    job_id: Any,
    parent_run_id: str | None,
    trace_id: str | None,
    status: str,
) -> RunIdentity:
    # Serialise attempt numbering per case (released at transaction end).
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"case_runs:{case_id}")
    last_no = await conn.fetchval(
        "SELECT COALESCE(MAX(attempt_no), 0) FROM case_runs WHERE case_id = $1", case_id
    )
    attempt_no = int(last_no) + 1
    chosen = trigger or ("initial" if attempt_no == 1 else "rerun")
    if chosen not in RUN_TRIGGERS:
        raise ValueError(f"unknown run trigger {chosen!r}")
    # Lineage skips cancelled runs (they never executed): the parent is the latest run that could have.
    prev_run = await conn.fetchval(
        "SELECT run_id FROM case_runs WHERE case_id = $1 AND status <> 'cancelled' "
        "ORDER BY attempt_no DESC LIMIT 1",
        case_id,
    )
    parent = parent_run_id if parent_run_id is not None else prev_run
    ciid = case_intelligence_id(organization_id, case_id)
    if trace_id is None:
        from app.observability.otel import get_current_trace_id

        trace_id = get_current_trace_id() or new_trace_id()
    identity = RunIdentity(
        case_id=case_id,
        organization_id=organization_id,
        case_intelligence_id=ciid,
        run_id=new_run_id(),
        attempt_no=attempt_no,
        trigger=chosen,
        trace_id=trace_id,
        parent_run_id=parent,
    )
    finished_at = datetime.now(UTC) if status in _TERMINAL else None
    await conn.execute(
        """INSERT INTO case_runs (run_id, case_id, organization_id, case_intelligence_id, attempt_no,
                                  trigger, parent_run_id, trace_id, job_id, status, finished_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
        identity.run_id,
        case_id,
        organization_id,
        ciid,
        attempt_no,
        chosen,
        parent,
        trace_id,
        job_id,
        status,
        finished_at,
    )
    await conn.execute(
        "UPDATE cases SET case_intelligence_id = $1 WHERE id = $2 AND case_intelligence_id IS DISTINCT FROM $1",
        ciid,
        case_id,
    )
    return identity


async def start_run(
    *,
    organization_id: str,
    case_id: str,
    trigger: str | None = None,
    job_id: Any = None,
    parent_run_id: str | None = None,
    trace_id: str | None = None,
    status: str = "running",
    conn: Any = None,
) -> RunIdentity:
    """Mint a new run for the case. Pass `conn` to join the caller's open transaction."""
    if status not in RUN_STATUSES:
        raise ValueError(f"unknown run status {status!r}")
    kwargs: dict[str, Any] = {
        "organization_id": organization_id,
        "case_id": case_id,
        "trigger": trigger,
        "job_id": job_id,
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "status": status,
    }
    if conn is not None:
        return await _start(conn, **kwargs)
    async with db.pool.acquire() as c, c.transaction():
        return await _start(c, **kwargs)


async def mark_run(
    run_id: str, status: str, *, job_id: Any = None, conn: Any = None, finished: bool | None = None
) -> None:
    """Update a run's status (and optionally link its job). Terminal statuses stamp `finished_at`."""
    if status not in RUN_STATUSES:
        raise ValueError(f"unknown run status {status!r}")
    done = finished if finished is not None else status in _TERMINAL
    sql = (
        "UPDATE case_runs SET status = $2, job_id = COALESCE($3, job_id), "
        "finished_at = CASE WHEN $4 THEN NOW() ELSE finished_at END WHERE run_id = $1"
    )
    if conn is not None:
        await conn.execute(sql, run_id, status, job_id, done)
    else:
        await db.execute(sql, run_id, status, job_id, done)


async def latest_run_id(case_id: str, *, conn: Any = None) -> str | None:
    sql = "SELECT run_id FROM case_runs WHERE case_id = $1 ORDER BY attempt_no DESC LIMIT 1"
    value = await (conn.fetchval(sql, case_id) if conn is not None else db.fetchval(sql, case_id))
    return str(value) if value is not None else None


async def list_runs(organization_id: str, case_id: str) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """SELECT run_id, case_id, case_intelligence_id, attempt_no, trigger, parent_run_id, trace_id,
                  job_id, status, created_at, finished_at
           FROM case_runs WHERE case_id = $1 AND organization_id = $2 ORDER BY attempt_no""",
        case_id,
        organization_id,
    )
    return [dict(r) for r in rows]


async def settle_runs_for_job(job_id: Any, status: str, *, conn: Any = None) -> int:
    """Move the unfinished run(s) linked to a job to `status` (used on retry/dead-letter). Returns rows changed."""
    if status not in RUN_STATUSES:
        raise ValueError(f"unknown run status {status!r}")
    done = status in _TERMINAL
    sql = (
        "UPDATE case_runs SET status = $2, finished_at = CASE WHEN $3 THEN NOW() ELSE finished_at END "
        "WHERE job_id = $1 AND status IN ('queued','running')"
    )
    result = await (
        conn.execute(sql, job_id, status, done)
        if conn is not None
        else db.execute(sql, job_id, status, done)
    )
    try:
        return int(str(result).rsplit(" ", 1)[-1])
    except (ValueError, IndexError):
        return 0


async def fail_runs_of_dead_jobs() -> list[dict[str, Any]]:
    """Runs whose job was dead-lettered (retries exhausted or reaped) can never finish: mark them failed.

    Returns the runs just failed so the caller can announce them (the worker that held the lease may be gone)."""
    rows = await db.fetch(
        """UPDATE case_runs r SET status = 'failed', finished_at = NOW()
           FROM case_jobs j
           WHERE r.job_id = j.id AND j.status = 'dead' AND r.status IN ('queued','running')
           RETURNING r.run_id, r.case_id, r.trigger, r.case_intelligence_id, r.trace_id"""
    )
    return [dict(r) for r in rows]


async def paused_run_id(case_id: str, *, conn: Any = None) -> str | None:
    """The latest run that stopped at the review gate (the one a human decision resolves)."""
    sql = (
        "SELECT run_id FROM case_runs WHERE case_id = $1 AND status = 'paused' "
        "ORDER BY attempt_no DESC LIMIT 1"
    )
    value = await (conn.fetchval(sql, case_id) if conn is not None else db.fetchval(sql, case_id))
    return str(value) if value is not None else None


async def settle_execution_run(run_id: str, status: str, *, conn: Any = None) -> None:
    """Finish an EXECUTION run (initial/rerun) and supersede any older run still waiting at the review gate.

    A newer execution replaces an earlier pause: the case's state now comes from the newer run, so the old
    paused run can no longer be resumed and must not stay 'paused' forever. Resume runs never supersede."""
    if conn is None:
        # Both statements or neither: a crash between them must not leave the old run 'paused'.
        async with db.pool.acquire() as own, own.transaction():
            await settle_execution_run(run_id, status, conn=own)
        return
    await mark_run(run_id, status, conn=conn)
    if status not in ("paused", "completed"):
        return
    sql = (
        "UPDATE case_runs old SET status = 'superseded', finished_at = COALESCE(old.finished_at, NOW()) "
        "FROM case_runs cur "
        "WHERE cur.run_id = $1 AND cur.trigger <> 'resume' AND old.case_id = cur.case_id "
        "AND old.status = 'paused' AND old.attempt_no < cur.attempt_no"
    )
    await conn.execute(sql, run_id)
