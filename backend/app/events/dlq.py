"""Outbox dead-letter queue + replay.

Round-9 outbox publisher worker drains `event_outbox` to EventBridge / Kinesis.
On publish failure today, the row's `attempts` increments and it gets retried.
At sustained downstream outage, the row spins forever — eating publisher
throughput.

Round-12 adds:
  • event_outbox_dlq table — terminal-failure events
  • Move-to-DLQ rule: attempts >= MAX_ATTEMPTS (default 10)
  • Operator endpoints to inspect DLQ + replay events
"""
from __future__ import annotations

import os
from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()

_MAX_ATTEMPTS = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10"))


_DLQ_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS event_outbox_dlq (
    event_id          TEXT PRIMARY KEY,
    organization_id   TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    case_id           TEXT,
    payload           JSONB NOT NULL,
    attempts          INTEGER NOT NULL,
    last_error        TEXT,
    moved_to_dlq_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_created_at TIMESTAMPTZ NOT NULL,
    replay_count      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dlq_org           ON event_outbox_dlq (organization_id);
CREATE INDEX IF NOT EXISTS idx_dlq_event_type    ON event_outbox_dlq (event_type);
CREATE INDEX IF NOT EXISTS idx_dlq_moved         ON event_outbox_dlq (moved_to_dlq_at);
"""


async def ensure_schema() -> None:
    await db.execute(_DLQ_SCHEMA_SQL)


async def maybe_move_to_dlq(*, event_id: str, attempts: int, last_error: str | None) -> bool:
    """If attempts >= MAX_ATTEMPTS, move the event from event_outbox to
    event_outbox_dlq. Returns True if moved."""
    if attempts < _MAX_ATTEMPTS:
        return False
    moved = False
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM event_outbox WHERE event_id = $1 FOR UPDATE",
                event_id,
            )
            if row is None:
                return False
            await conn.execute(
                """
                INSERT INTO event_outbox_dlq (
                    event_id, organization_id, event_type, case_id, payload,
                    attempts, last_error, original_created_at
                ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
                ON CONFLICT (event_id) DO UPDATE SET
                    attempts        = EXCLUDED.attempts,
                    last_error      = EXCLUDED.last_error,
                    moved_to_dlq_at = NOW()
                """,
                row["event_id"],
                row["organization_id"],
                row["event_type"],
                row.get("case_id") if hasattr(row, "get") else row["case_id"],
                row["payload"] if isinstance(row["payload"], str) else __import__("json").dumps(row["payload"]),
                attempts,
                last_error,
                row["created_at"],
            )
            await conn.execute("DELETE FROM event_outbox WHERE event_id = $1", event_id)
            moved = True
    if moved:
        log.warning("outbox.dlq.moved", event_id=event_id, attempts=attempts, error=last_error)
    return moved


async def list_dlq(
    *, organization_id: str, event_type: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    if event_type:
        rows = await db.fetch_ro(
            "SELECT * FROM event_outbox_dlq WHERE organization_id = $1 AND event_type = $2 "
            "ORDER BY moved_to_dlq_at DESC LIMIT $3",
            organization_id, event_type, limit,
        )
    else:
        rows = await db.fetch_ro(
            "SELECT * FROM event_outbox_dlq WHERE organization_id = $1 "
            "ORDER BY moved_to_dlq_at DESC LIMIT $2",
            organization_id, limit,
        )
    return [dict(r) for r in rows]


async def replay(*, event_id: str, organization_id: str) -> bool:
    """Move event back from DLQ to event_outbox so the publisher picks it up
    again. Returns True if replayed."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM event_outbox_dlq WHERE event_id = $1 AND organization_id = $2 FOR UPDATE",
                event_id, organization_id,
            )
            if row is None:
                return False
            await conn.execute(
                """
                INSERT INTO event_outbox (
                    event_id, organization_id, event_type, case_id, payload,
                    attempts, status, created_at
                ) VALUES ($1, $2, $3, $4, $5::jsonb, 0, 'pending', NOW())
                ON CONFLICT (event_id) DO UPDATE SET
                    attempts = 0, status = 'pending'
                """,
                row["event_id"],
                row["organization_id"],
                row["event_type"],
                row["case_id"],
                row["payload"] if isinstance(row["payload"], str) else __import__("json").dumps(row["payload"]),
            )
            await conn.execute(
                "UPDATE event_outbox_dlq SET replay_count = replay_count + 1 WHERE event_id = $1",
                event_id,
            )
    log.info("outbox.dlq.replayed", event_id=event_id, organization_id=organization_id)
    return True


async def dlq_stats(*, organization_id: str) -> dict[str, Any]:
    """Per-tenant DLQ rollup for the FinOps + ops dashboards."""
    rows = await db.fetch_ro(
        "SELECT event_type, COUNT(*) AS n FROM event_outbox_dlq WHERE organization_id = $1 GROUP BY event_type",
        organization_id,
    )
    by_type = {r["event_type"]: int(r["n"]) for r in rows}
    total = sum(by_type.values())
    return {
        "organization_id": organization_id,
        "total_dlq_events": total,
        "by_event_type": by_type,
        "max_attempts_threshold": _MAX_ATTEMPTS,
    }
