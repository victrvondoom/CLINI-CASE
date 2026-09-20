"""Transactional outbox table + emit/drain primitives.

The transactional outbox pattern (Microservices.io / Chris Richardson):

  • Domain write + event emit happen in the SAME database transaction.
  • A separate publisher worker drains the outbox to the message bus
    (EventBridge / Kafka / Kinesis), updating outbox rows to `published`.
  • Consumers downstream are decoupled — they subscribe to the bus, not the DB.

Schema (idempotent on first import):

    event_outbox (
      id            BIGSERIAL PRIMARY KEY,
      event_id      UUID UNIQUE NOT NULL,        -- CloudEvents `id`
      event_type    TEXT NOT NULL,                -- CloudEvents `type` (e.g. "clincase.case.decided.v1")
      event_version TEXT NOT NULL DEFAULT 'v1',
      organization_id TEXT NOT NULL,
      aggregate_type TEXT NOT NULL,               -- "case" | "appeal" | "reviewer_action"
      aggregate_id   TEXT NOT NULL,
      payload_json   JSONB NOT NULL,
      occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      published_at   TIMESTAMPTZ,                 -- NULL until publisher drains
      attempts       INT NOT NULL DEFAULT 0,
      last_error     TEXT,
      trace_id       TEXT                          -- W3C trace_id for correlation
    )
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


# =============================================================================
# Schema
# =============================================================================


_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_outbox (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID UNIQUE NOT NULL,
    event_type      TEXT NOT NULL,
    event_version   TEXT NOT NULL DEFAULT 'v1',
    organization_id TEXT NOT NULL,
    aggregate_type  TEXT NOT NULL,
    aggregate_id    TEXT NOT NULL,
    payload_json    JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    trace_id        TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_outbox_pending
    ON event_outbox (occurred_at)
    WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_outbox_org_type
    ON event_outbox (organization_id, event_type);
CREATE INDEX IF NOT EXISTS idx_event_outbox_aggregate
    ON event_outbox (aggregate_type, aggregate_id);
"""


async def ensure_schema() -> None:
    """Idempotent. Called from app lifespan."""
    from app.db import db
    await db.execute(_SCHEMA)


# =============================================================================
# DomainEvent — CloudEvents 1.0 spec-aligned
# =============================================================================


@dataclass(frozen=True)
class DomainEvent:
    """A domain event ready for the outbox.

    Maps to CloudEvents 1.0 fields:
      id              ↔ event_id (UUID)
      type            ↔ event_type (e.g. "clincase.case.decided.v1")
      source          ↔ "clincase" (set in publisher)
      specversion     ↔ "1.0"
      datacontenttype ↔ "application/json"
      data            ↔ payload_json
      time            ↔ occurred_at
    """

    event_type: str                # e.g. "clincase.case.decided.v1"
    organization_id: str
    aggregate_type: str             # "case" | "appeal" | "reviewer_action" | "trizetto_envelope"
    aggregate_id: str
    payload: dict[str, Any]
    event_version: str = "v1"


# =============================================================================
# Public emit + drain API
# =============================================================================


async def emit_event(
    event: DomainEvent,
    *,
    conn: Any | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    """Insert a domain event into the outbox.

    ATOMICITY GUARANTEE: pass the same `conn` you're using for the domain write
    so both happen in the same transaction. Without `conn` the insert is its
    own transaction (use only for fire-and-forget out-of-band events).

    Returns the event_id.
    """
    from app.db import db
    event_id = uuid.uuid4()
    sql = """
        INSERT INTO event_outbox
            (event_id, event_type, event_version, organization_id,
             aggregate_type, aggregate_id, payload_json, trace_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
        RETURNING event_id
    """
    args = (
        event_id,
        event.event_type,
        event.event_version,
        event.organization_id,
        event.aggregate_type,
        event.aggregate_id,
        json.dumps(event.payload),
        trace_id,
    )
    if conn is not None:
        await conn.execute(sql, *args)
    else:
        await db.execute(sql, *args)
    log.info(
        "outbox.emit",
        event_type=event.event_type,
        event_id=str(event_id),
        aggregate_id=event.aggregate_id,
    )
    return event_id


async def pending_events(*, batch_size: int = 100) -> list[dict[str, Any]]:
    """Pull a batch of unpublished events. Publisher worker calls this.

    Uses SELECT FOR UPDATE SKIP LOCKED so multiple publisher workers can run
    concurrently without claiming the same events.
    """
    from app.db import db
    async with db.pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            """SELECT id, event_id, event_type, event_version, organization_id,
                           aggregate_type, aggregate_id, payload_json, occurred_at,
                           attempts, trace_id
                    FROM event_outbox
                    WHERE published_at IS NULL AND attempts < 5
                    ORDER BY occurred_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT $1""",
            batch_size,
        )
        return [dict(r) for r in rows]


async def mark_published(row_id: int) -> None:
    """Mark an event as successfully published. Publisher worker calls this
    after the message bus accepts the event."""
    from app.db import db
    await db.execute(
        "UPDATE event_outbox SET published_at = NOW() WHERE id = $1",
        row_id,
    )


async def mark_failed(row_id: int, error: str) -> None:
    """Increment attempts + record last error. Publisher worker calls on bus failure."""
    from app.db import db
    await db.execute(
        """UPDATE event_outbox
           SET attempts = attempts + 1, last_error = $1
           WHERE id = $2""",
        error[:500], row_id,
    )


# =============================================================================
# CloudEvents 1.0 envelope renderer (used by publisher worker)
# =============================================================================


def to_cloudevent(row: dict[str, Any]) -> dict[str, Any]:
    """Render an outbox row as a CloudEvents 1.0 envelope.

    Industry-standard envelope = downstream consumers (EventBridge, Kafka with
    CloudEvents schema, custom consumers) parse it without bespoke logic.
    """
    payload = row["payload_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    occurred_at = row["occurred_at"]
    time_iso = occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else str(occurred_at)
    return {
        "specversion": "1.0",
        "id": str(row["event_id"]),
        "source": "clincase",
        "type": row["event_type"],
        "time": time_iso,
        "datacontenttype": "application/json",
        "subject": f"{row['aggregate_type']}/{row['aggregate_id']}",
        "data": payload,
        # ClinCase-specific extension attributes
        "clincase_organization_id": row["organization_id"],
        "clincase_event_version": row["event_version"],
        "clincase_trace_id": row.get("trace_id"),
    }


# =============================================================================
# Convenience helpers — emit a typed event in one call
# =============================================================================


async def emit_case_decided(
    *,
    organization_id: str,
    case_id: str,
    verdict: str,
    confidence: float,
    triggered_hitl: bool,
    decision_run_id: str,
    primary_model_id: str,
    cost_usd: float,
    duration_seconds: float,
    conn: Any | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    return await emit_event(
        DomainEvent(
            event_type="clincase.case.decided.v1",
            organization_id=organization_id,
            aggregate_type="case",
            aggregate_id=case_id,
            payload={
                "case_id": case_id,
                "verdict": verdict,
                "confidence": confidence,
                "triggered_hitl": triggered_hitl,
                "decision_run_id": decision_run_id,
                "primary_model_id": primary_model_id,
                "cost_usd": cost_usd,
                "duration_seconds": duration_seconds,
            },
        ),
        conn=conn,
        trace_id=trace_id,
    )


async def emit_appeal_drafted(
    *,
    organization_id: str,
    case_id: str,
    appeal_id: int,
    structured_arguments_count: int,
    conn: Any | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    return await emit_event(
        DomainEvent(
            event_type="clincase.appeal.drafted.v1",
            organization_id=organization_id,
            aggregate_type="appeal",
            aggregate_id=str(appeal_id),
            payload={
                "case_id": case_id,
                "appeal_id": appeal_id,
                "structured_arguments_count": structured_arguments_count,
            },
        ),
        conn=conn,
        trace_id=trace_id,
    )


async def emit_reviewer_signed_off(
    *,
    organization_id: str,
    case_id: str,
    reviewer_id: str,
    verdict: str,
    conn: Any | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    return await emit_event(
        DomainEvent(
            event_type="clincase.reviewer.signed_off.v1",
            organization_id=organization_id,
            aggregate_type="reviewer_action",
            aggregate_id=case_id,
            payload={
                "case_id": case_id,
                "reviewer_id": reviewer_id,
                "verdict": verdict,
            },
        ),
        conn=conn,
        trace_id=trace_id,
    )


async def emit_trizetto_envelope_dispatched(
    *,
    organization_id: str,
    case_id: str,
    gateway_id: str,
    fanout_targets: list[str],
    decision_hash_sha256: str,
    conn: Any | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    return await emit_event(
        DomainEvent(
            event_type="clincase.trizetto.envelope_dispatched.v1",
            organization_id=organization_id,
            aggregate_type="trizetto_envelope",
            aggregate_id=case_id,
            payload={
                "case_id": case_id,
                "gateway_id": gateway_id,
                "fanout_targets": fanout_targets,
                "decision_hash_sha256": decision_hash_sha256,
            },
        ),
        conn=conn,
        trace_id=trace_id,
    )
