"""LLM smoke-test endpoint.

Hit this once after `make backend.dev` to verify the LLM provider is
configured correctly:

    curl http://localhost:8000/api/v1/llm/ping
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.llm import get_llm_client

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/ping")
async def llm_ping() -> dict[str, object]:
    """Send a minimal completion to verify LLM connectivity end-to-end."""
    try:
        client = get_llm_client()
        response = await client.complete(
            system="You are a connectivity test. Reply in exactly three words.",
            user="Are you alive?",
            max_tokens=32,
            temperature=0.0,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"LLM error: {e}") from e

    return {
        "provider": settings.LLM_PROVIDER,
        "model": response.model_id,
        "reply": response.text,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "stop_reason": response.stop_reason,
    }
