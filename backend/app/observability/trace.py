"""Agent invocation tracing - audit log + SSE event emission.

Every agent call MUST be wrapped in `trace_agent(case_id, agent_name, input)`.
This:
  1. Inserts a row into `agent_runs` at start.
  2. Emits an `agent_started` SSE event.
  3. Yields a mutable result dict; agent fills in `output`, `model_id`,
     `input_tokens`, `output_tokens`.
  4. On clean exit: updates the row with output + latency, emits `agent_finished`.
  5. On exception: updates row with error, emits `agent_error`, re-raises.
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog

from app.db import db
from app.streaming import publish

log = structlog.get_logger()


@asynccontextmanager
async def trace_agent(
    case_id: str,
    agent_name: str,
    input_payload: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """Wrap an agent invocation with full audit + streaming."""
    started = time.time()
    row_id = await db.fetchval(
        "INSERT INTO agent_runs (case_id, agent_name, started_at, input_json) "
        "VALUES ($1, $2, NOW(), $3) RETURNING id",
        case_id,
        agent_name,
        json.dumps(input_payload),
    )
    await publish(
        case_id,
        {"type": "agent_started", "agent_name": agent_name, "ts": time.time()},
    )

    result: dict[str, Any] = {}
    try:
        yield result
        latency_ms = int((time.time() - started) * 1000)
        await db.execute(
            """UPDATE agent_runs
               SET finished_at = NOW(),
                   output_json = $1,
                   latency_ms  = $2,
                   model_id    = $3,
                   input_tokens  = $4,
                   output_tokens = $5
               WHERE id = $6""",
            json.dumps(result.get("output", {})),
            latency_ms,
            result.get("model_id"),
            result.get("input_tokens"),
            result.get("output_tokens"),
            row_id,
        )
        await publish(
            case_id,
            {
                "type": "agent_finished",
                "agent_name": agent_name,
                "output": result.get("output", {}),
                "latency_ms": latency_ms,
                "model_id": result.get("model_id"),
                "ts": time.time(),
            },
        )
        log.info(
            "agent.finished",
            agent=agent_name,
            case_id=case_id,
            latency_ms=latency_ms,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
        )
    except Exception as e:
        latency_ms = int((time.time() - started) * 1000)
        await db.execute(
            """UPDATE agent_runs
               SET finished_at = NOW(), error_text = $1, latency_ms = $2
               WHERE id = $3""",
            str(e),
            latency_ms,
            row_id,
        )
        await publish(
            case_id,
            {
                "type": "agent_error",
                "agent_name": agent_name,
                "error": str(e),
                "ts": time.time(),
            },
        )
        log.error("agent.error", agent=agent_name, case_id=case_id, error=str(e))
        raise
