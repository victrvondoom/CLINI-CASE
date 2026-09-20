"""TraceSink — pluggable persistence + streaming for agent invocations.

The framework's `Agent.invoke()` lifecycle no longer hard-imports `app.db`
or `app.streaming`. Instead it talks to a `TraceSink`, of which we ship two
implementations:

  • PostgresTraceSink   — writes to `agent_runs` and emits SSE events.
                           Production default. Reads `from app.db import db`
                           and `from app.streaming import publish` lazily so
                           tests don't need a live DB.
  • InMemoryTraceSink   — buffers spans + events in lists. Used by tests
                           where a real DB connection is unavailable or
                           undesirable. Zero side effects.

Both implementations share the same async interface so swapping them is a
one-line change at the call site (`new_agent_context(trace_sink=...)`).
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Sink protocol
# =============================================================================


@dataclass
class SpanHandle:
    """Opaque handle returned by `open_span` and consumed by `close_span`.

    Implementations may stash whatever they need on this — a DB row id, a
    list index, etc. The framework treats it as a black box.
    """

    sink_internal_id: Any


class TraceSink(ABC):
    """Pluggable persistence + SSE for `Agent.invoke()` lifecycle events."""

    @abstractmethod
    async def open_span(
        self,
        *,
        case_id: str,
        agent_name: str,
        input_payload: dict[str, Any],
    ) -> SpanHandle:
        """Open a new span. Returns a handle the framework will pass to
        `close_span_ok` or `close_span_error`."""

    @abstractmethod
    async def close_span_ok(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        output_payload: dict[str, Any],
        latency_ms: int,
        model_id: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Successful completion."""

    @abstractmethod
    async def close_span_error(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        error: str,
        latency_ms: int,
    ) -> None:
        """Failed completion."""


# =============================================================================
# Postgres implementation (production default)
# =============================================================================


class PostgresTraceSink(TraceSink):
    """Writes to `agent_runs` + publishes SSE events.

    Imports `app.db` and `app.streaming` lazily so the framework module
    stays decoupled at import time.
    """

    async def open_span(
        self,
        *,
        case_id: str,
        agent_name: str,
        input_payload: dict[str, Any],
    ) -> SpanHandle:
        from app.db import db
        from app.streaming import publish

        row_id = await db.fetchval(
            """INSERT INTO agent_runs
                  (case_id, agent_name, started_at, input_json)
               VALUES ($1, $2, NOW(), $3)
               RETURNING id""",
            case_id,
            agent_name,
            json.dumps(input_payload),
        )
        await publish(case_id, {
            "type": "agent_started",
            "agent_name": agent_name,
            "ts": time.time(),
        })
        return SpanHandle(sink_internal_id=row_id)

    async def close_span_ok(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        output_payload: dict[str, Any],
        latency_ms: int,
        model_id: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        from app.db import db
        from app.streaming import publish

        await db.execute(
            """UPDATE agent_runs SET
                   finished_at  = NOW(),
                   output_json  = $1,
                   latency_ms   = $2,
                   model_id     = $3,
                   input_tokens = $4,
                   output_tokens= $5
               WHERE id = $6""",
            json.dumps(output_payload),
            latency_ms,
            model_id,
            input_tokens,
            output_tokens,
            handle.sink_internal_id,
        )
        await publish(case_id, {
            "type": "agent_finished",
            "agent_name": agent_name,
            "output": output_payload,
            "latency_ms": latency_ms,
            "model_id": model_id,
            "ts": time.time(),
        })

    async def close_span_error(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        error: str,
        latency_ms: int,
    ) -> None:
        from app.db import db
        from app.streaming import publish

        await db.execute(
            """UPDATE agent_runs SET finished_at = NOW(),
                      error_text = $1, latency_ms = $2 WHERE id = $3""",
            error,
            latency_ms,
            handle.sink_internal_id,
        )
        await publish(case_id, {
            "type": "agent_error",
            "agent_name": agent_name,
            "error": error,
            "ts": time.time(),
        })


# =============================================================================
# In-memory implementation (tests)
# =============================================================================


@dataclass
class _InMemorySpan:
    case_id: str
    agent_name: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None = None
    latency_ms: int | None = None
    model_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    status: str = "open"


@dataclass
class InMemoryTraceSink(TraceSink):
    """Buffers spans in a list. Zero side effects. Use in unit tests."""

    spans: list[_InMemorySpan] = field(default_factory=list)

    async def open_span(
        self,
        *,
        case_id: str,
        agent_name: str,
        input_payload: dict[str, Any],
    ) -> SpanHandle:
        idx = len(self.spans)
        self.spans.append(_InMemorySpan(
            case_id=case_id,
            agent_name=agent_name,
            input_payload=input_payload,
        ))
        return SpanHandle(sink_internal_id=idx)

    async def close_span_ok(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        output_payload: dict[str, Any],
        latency_ms: int,
        model_id: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        s = self.spans[handle.sink_internal_id]
        s.output_payload = output_payload
        s.latency_ms = latency_ms
        s.model_id = model_id
        s.input_tokens = input_tokens
        s.output_tokens = output_tokens
        s.status = "ok"

    async def close_span_error(
        self,
        handle: SpanHandle,
        *,
        case_id: str,
        agent_name: str,
        error: str,
        latency_ms: int,
    ) -> None:
        s = self.spans[handle.sink_internal_id]
        s.error = error
        s.latency_ms = latency_ms
        s.status = "error"
