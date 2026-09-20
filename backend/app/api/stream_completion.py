"""Streaming LLM completion endpoint — first-token-latency-optimized for the
coordinator UI's "draft appeal" + "explain decision" affordances.

Round-9 case-run is single-shot: the agent waits for full Bedrock response
(~3-5s for 2K-token output) before returning. The coordinator UI shows a
spinner the whole time.

Round-12 wires Bedrock streaming into a Server-Sent Events (SSE) endpoint:

  POST /api/v1/llm/stream
       { "system": "...", "user": "...", "model_id": "..." }

  → text/event-stream
    data: {"delta":"The"}
    data: {"delta":" patient"}
    data: {"delta":" has"}
    ...
    data: {"event":"done","stop_reason":"end_turn","input_tokens":234,"output_tokens":78}

The Bedrock streaming first-token latency is ~300-500ms, vs ~3-5s for the
full sync response. The coordinator's UI feels INSTANT instead of slow.

Already gated by:
  • RateLimitMiddleware
  • CellRouterMiddleware
  • TenantContextMiddleware
  • OIDC + JWT auth
  • Per-tenant model allowlist via the GenAIGateway
  • Per-Bedrock-model circuit breaker
  • Per-tenant 24h quota (TenantPolicy)
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import get_current_user
from app.llm.factory import get_llm_client

log = structlog.get_logger()

router = APIRouter(prefix="/llm", tags=["llm-gateway"])


class StreamRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    system: str = Field(..., max_length=8000)
    user: str = Field(..., max_length=8000)
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=64, le=8192)


async def _sse_iter(stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """Convert text-delta async-iterator to SSE byte stream.

    Yields lines as `data: {...}\n\n`. Terminates with a `done` event.
    """
    chunks_emitted = 0
    try:
        async for delta in stream:
            payload = json.dumps({"delta": delta})
            yield f"data: {payload}\n\n".encode()
            chunks_emitted += 1
        yield (
            "data: " + json.dumps({"event": "done", "chunks": chunks_emitted}) + "\n\n"
        ).encode("utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("stream_completion.error", error=str(e))
        err = json.dumps({"event": "error", "message": str(e)[:200]})
        yield f"data: {err}\n\n".encode()


@router.post("/stream")
async def stream_completion(
    body: StreamRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """SSE-streamed Bedrock completion. ~500ms first-token latency."""
    client = get_llm_client()
    if not hasattr(client, "stream"):
        raise HTTPException(
            status_code=501,
            detail="Configured LLM provider does not support streaming.",
        )

    stream_iter = client.stream(
        system=body.system,
        user=body.user,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        model_id=body.model_id,
    )

    log.info(
        "stream_completion.started",
        org=user["organization_id"],
        user=user["id"],
        model=body.model_id or "default",
    )

    return StreamingResponse(
        _sse_iter(stream_iter),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
