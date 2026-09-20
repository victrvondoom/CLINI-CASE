"""SSE endpoint for live agent trace events.

The frontend's ReasoningTracePanel opens an EventSource against
GET /api/v1/cases/{case_id}/stream and renders one card per agent
as events arrive.

Events emitted by `app.observability.trace.trace_agent` and
`app.streaming.publish`:
  - agent_started:  {agent_name, ts}
  - agent_finished: {agent_name, output, latency_ms, model_id, ts}
  - agent_error:    {agent_name, error, ts}
  - done:           {ts}
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.streaming import subscribe, unsubscribe

router = APIRouter(prefix="/cases", tags=["stream"])

_HEARTBEAT_SEC = 15.0
_IDLE_TIMEOUT_SEC = 600.0  # close stream after 10 minutes of no events


@router.get("/{case_id}/stream")
async def stream_case_events(case_id: str) -> EventSourceResponse:
    """Server-Sent Events stream of trace events for a case."""
    queue = subscribe(case_id)

    async def event_gen() -> AsyncIterator[dict]:
        idle_start = asyncio.get_event_loop().time()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SEC)
                except TimeoutError:
                    # No event in the heartbeat window — send a keepalive comment
                    # to prevent the client / proxy from closing the connection.
                    if asyncio.get_event_loop().time() - idle_start > _IDLE_TIMEOUT_SEC:
                        break
                    yield {"event": "heartbeat", "data": "{}"}
                    continue

                idle_start = asyncio.get_event_loop().time()
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event, default=str),
                }
                if event.get("type") == "done":
                    break
        finally:
            unsubscribe(case_id, queue)

    return EventSourceResponse(event_gen())
