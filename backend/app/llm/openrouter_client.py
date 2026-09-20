"""OpenRouter implementation of LLMClient.

OpenRouter is OpenAI-compatible, so we use the openai SDK pointed at
OpenRouter's API. Activated by setting LLM_PROVIDER=openrouter.

Model IDs follow OpenRouter's `provider/model` convention, e.g.:
    anthropic/claude-sonnet-4.6
    anthropic/claude-opus-4.6
    anthropic/claude-haiku-4.5
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.llm.base import LLMClient, LLMResponse


class OpenRouterClient(LLMClient):
    def __init__(self) -> None:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Add it to .env or export it before starting the backend."
            )
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://clincase.local",
                "X-Title": "ClinCase",
            },
        )
        self._default_model = settings.OPENROUTER_MODEL

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
        completion = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = completion.choices[0]
        usage = completion.usage
        return LLMResponse(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            stop_reason=choice.finish_reason or "unknown",
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
        stream = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
