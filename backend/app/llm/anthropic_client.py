"""Anthropic direct API implementation of LLMClient.

Used until May 6 (the hackathon day). On May 6 we swap LLM_PROVIDER=bedrock
without touching any agent code.
"""
from __future__ import annotations

from typing import AsyncIterator

from anthropic import AsyncAnthropic

from app.config import settings
from app.llm.base import LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to .env or export it before starting the backend."
            )
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._default_model = settings.ANTHROPIC_MODEL

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> LLMResponse:
        model = model_id or self._default_model
        message = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return LLMResponse(
            text="".join(text_blocks),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            stop_reason=message.stop_reason or "unknown",
            model_id=model,
        )

    async def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> AsyncIterator[str]:
        model = model_id or self._default_model
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
