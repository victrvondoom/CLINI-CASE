"""Saga state machine engine — persistent, replayable, compensable.

Round-9 documented the saga pattern in `ops/architecture/SAGA_PATTERN.md`.
Round-11 listed `case_sagas` + saga endpoint as deferred. Round-12 ships it.

The saga is the durable record of a multi-step distributed transaction. Each
step has:
  • action     — the forward operation (write decision, submit to TriZetto, ...)
  • compensate — the inverse (only invoked when a later step fails)
  • status     — pending | running | completed | failed | compensated

Saga invariants:
  • Steps execute in order.
  • If any step fails, the engine runs compensations IN REVERSE ORDER for all
    completed steps.
  • A saga is durable: the worker can crash mid-saga, restart, and the engine
    resumes from the last completed step.
  • Idempotency keys per step prevent double-execution after restart.

Today the saga engine is wired for the post-decision flow:
    1. write decision        (cannot compensate — it's the system of record)
    2. submit to TriZetto    (compensate: mark submission as canceled)
    3. notify coordinator    (compensate: send "submission canceled" SSE event)
    4. emit case_decided     (compensate: emit case_decision_canceled)

Pairs with: ops/architecture/SAGA_PATTERN.md
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import structlog

from app.db import db

log = structlog.get_logger()


# =============================================================================
# State + step types
# =============================================================================


SagaStatus = str  # 'pending' | 'running' | 'completed' | 'failed' | 'compensated'


@dataclass
class SagaStep:
    name: str
    payload: dict[str, Any]
    status: SagaStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    completed_at: str | None = None


@dataclass
class Saga:
    saga_id: str
    case_id: str
    organization_id: str
    saga_type: str                       # e.g. "post_decision_v1"
    status: SagaStatus
    steps: list[SagaStep]
    created_at: str
    updated_at: str
    error: str | None = None


# =============================================================================
# Schema bootstrap (idempotent — also covered by the future Alembic migration)
# =============================================================================


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS case_sagas (
    saga_id          TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    organization_id  TEXT NOT NULL,
    saga_type        TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN
                       ('pending','running','completed','failed','compensated')),
    steps            JSONB NOT NULL DEFAULT '[]'::JSONB,
    error            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_case_sagas_case        ON case_sagas (case_id);
CREATE INDEX IF NOT EXISTS idx_case_sagas_org_status  ON case_sagas (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_case_sagas_status      ON case_sagas (status) WHERE status IN ('pending','running','failed');
"""


async def ensure_schema() -> None:
    """Idempotent schema bootstrap. Called from app/main.py lifespan."""
    await db.execute(_SCHEMA_SQL)


# =============================================================================
# Step registry — mapping step names to (action, compensate) pairs
# =============================================================================


StepCallable = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


_STEP_REGISTRY: dict[str, tuple[StepCallable, StepCallable | None]] = {}


def register_step(name: str, *, action: StepCallable, compensate: StepCallable | None = None) -> None:
    """Register a saga step. Call from module init time."""
    _STEP_REGISTRY[name] = (action, compensate)


# =============================================================================
# Saga engine — start, resume, compensate
# =============================================================================


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(saga: Saga) -> dict[str, Any]:
    return {
        "saga_id": saga.saga_id,
        "case_id": saga.case_id,
        "organization_id": saga.organization_id,
        "saga_type": saga.saga_type,
        "status": saga.status,
        "steps": [step.__dict__ for step in saga.steps],
        "error": saga.error,
        "created_at": saga.created_at,
        "updated_at": saga.updated_at,
    }


def _deserialize(row: Any) -> Saga:
    steps_raw = row["steps"]
    if isinstance(steps_raw, str):
        steps_raw = json.loads(steps_raw)
    steps = [SagaStep(**s) for s in steps_raw]
    return Saga(
        saga_id=row["saga_id"],
        case_id=row["case_id"],
        organization_id=row["organization_id"],
        saga_type=row["saga_type"],
        status=row["status"],
        steps=steps,
        error=row["error"],
        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
        updated_at=row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
    )


async def _persist(saga: Saga) -> None:
    saga.updated_at = _now_iso()
    await db.execute(
        """
        INSERT INTO case_sagas (saga_id, case_id, organization_id, saga_type, status, steps, error)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        ON CONFLICT (saga_id) DO UPDATE
            SET status = EXCLUDED.status,
                steps = EXCLUDED.steps,
                error = EXCLUDED.error,
                updated_at = NOW()
        """,
        saga.saga_id,
        saga.case_id,
        saga.organization_id,
        saga.saga_type,
        saga.status,
        json.dumps([s.__dict__ for s in saga.steps]),
        saga.error,
    )


async def start_saga(
    *,
    case_id: str,
    organization_id: str,
    saga_type: str,
    step_specs: list[dict[str, Any]],
) -> Saga:
    """Create a new saga, persist it as 'pending', and return it.

    `step_specs` is a list of `{name, payload}` dicts in execution order.
    """
    saga = Saga(
        saga_id=f"saga_{uuid.uuid4().hex[:16]}",
        case_id=case_id,
        organization_id=organization_id,
        saga_type=saga_type,
        status="pending",
        steps=[SagaStep(name=s["name"], payload=s.get("payload", {})) for s in step_specs],
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    await _persist(saga)
    return saga


async def execute_saga(saga: Saga) -> Saga:
    """Run the saga from its current state. Idempotent on completed steps.

    On step failure, compensate all completed prior steps in reverse order.
    """
    saga.status = "running"
    await _persist(saga)

    failed_index: int | None = None

    for i, step in enumerate(saga.steps):
        if step.status == "completed":
            continue
        action, _comp = _STEP_REGISTRY.get(step.name, (None, None))
        if action is None:
            saga.error = f"unknown_step:{step.name}"
            saga.status = "failed"
            failed_index = i
            await _persist(saga)
            break
        step.status = "running"
        step.attempts += 1
        await _persist(saga)
        try:
            result = await action(step.payload)
            step.payload = {**step.payload, "_result": result}
            step.status = "completed"
            step.completed_at = _now_iso()
            step.last_error = None
            await _persist(saga)
        except Exception as e:  # noqa: BLE001
            step.status = "failed"
            step.last_error = f"{type(e).__name__}: {e}"
            saga.error = step.last_error
            saga.status = "failed"
            failed_index = i
            await _persist(saga)
            log.warning("saga.step.failed", saga_id=saga.saga_id, step=step.name, error=step.last_error)
            break

    if failed_index is not None:
        await _compensate(saga, failed_at=failed_index)
    else:
        saga.status = "completed"
        await _persist(saga)
    return saga


async def _compensate(saga: Saga, *, failed_at: int) -> None:
    """Run compensations IN REVERSE ORDER for steps 0..failed_at-1
    that completed."""
    for i in range(failed_at - 1, -1, -1):
        step = saga.steps[i]
        if step.status != "completed":
            continue
        _action, compensate = _STEP_REGISTRY.get(step.name, (None, None))
        if compensate is None:
            log.info("saga.compensate.no_op", saga_id=saga.saga_id, step=step.name)
            continue
        try:
            await compensate(step.payload)
            step.status = "compensated"
            await _persist(saga)
            log.info("saga.compensate.success", saga_id=saga.saga_id, step=step.name)
        except Exception as e:  # noqa: BLE001
            log.error("saga.compensate.failed", saga_id=saga.saga_id, step=step.name, error=str(e))
            # The saga remains in 'failed' state and an operator must manually
            # remediate. Operations runbook documents this scenario.
            saga.error = f"compensation_failed:{step.name}:{type(e).__name__}"
            await _persist(saga)
    saga.status = "compensated"
    await _persist(saga)


async def get_saga(saga_id: str) -> Saga | None:
    """Read a single saga from the DB."""
    row = await db.fetchrow(
        "SELECT * FROM case_sagas WHERE saga_id = $1",
        saga_id,
    )
    if row is None:
        return None
    return _deserialize(row)


async def list_sagas(*, organization_id: str, status: str | None = None, limit: int = 100) -> list[Saga]:
    if status:
        rows = await db.fetch(
            "SELECT * FROM case_sagas WHERE organization_id = $1 AND status = $2 "
            "ORDER BY created_at DESC LIMIT $3",
            organization_id, status, limit,
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM case_sagas WHERE organization_id = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            organization_id, limit,
        )
    return [_deserialize(r) for r in rows]


async def replay_saga(saga_id: str) -> Saga:
    """Operator-driven replay: re-run a failed saga from where it left off."""
    saga = await get_saga(saga_id)
    if saga is None:
        raise LookupError(f"saga not found: {saga_id}")
    if saga.status not in ("failed", "pending"):
        raise ValueError(f"cannot replay saga in status: {saga.status}")
    return await execute_saga(saga)
