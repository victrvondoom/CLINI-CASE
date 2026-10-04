"""OpenRouter implementation of LLMClient.

OpenRouter is OpenAI-compatible, so we use the openai SDK pointed at
OpenRouter's API. Activated by setting LLM_PROVIDER=openrouter.
OPENROUTER_BASE_URL can point the same client at any OpenAI-compatible
endpoint (e.g. NVIDIA: https://integrate.api.nvidia.com/v1).

Model IDs follow OpenRouter's `provider/model` convention, e.g.:
    anthropic/claude-sonnet-4.6
    anthropic/claude-opus-4.6
    anthropic/claude-haiku-4.5
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import weakref
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from app.config import settings
from app.llm.base import LLMClient, LLMResponse


def _http_client() -> DefaultAsyncHttpxClient | None:
    """OS trust store for this client only (opt-in); verification stays on."""
    if not settings.LLM_SYSTEM_TRUST:
        return None
    import ssl

    import truststore

    return DefaultAsyncHttpxClient(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))


def _extra_body() -> dict[str, Any] | None:
    raw = settings.OPENROUTER_EXTRA_BODY.strip()
    if not raw:
        return None
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("OPENROUTER_EXTRA_BODY must be a JSON object")
    return body


_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def _slot() -> contextlib.AbstractAsyncContextManager[Any]:
    """Cap in-flight requests per event loop (free tiers reject bursts with 429)."""
    if settings.LLM_MAX_CONCURRENCY <= 0:
        return contextlib.nullcontext()
    loop = asyncio.get_running_loop()
    sem = _semaphores.get(loop)
    if sem is None:
        sem = _semaphores[loop] = asyncio.Semaphore(settings.LLM_MAX_CONCURRENCY)
    return sem


_windows: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, deque[float]] = (
    weakref.WeakKeyDictionary()
)


async def _respect_rpm() -> None:
    """Sliding 60 s window: wait until a request fits under LLM_MAX_RPM (per event loop)."""
    rpm = settings.LLM_MAX_RPM
    if rpm <= 0:
        return
    loop = asyncio.get_running_loop()
    window = _windows.get(loop)
    if window is None:
        window = _windows[loop] = deque()
    while True:
        now = loop.time()
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) < rpm:
            window.append(now)
            return
        await asyncio.sleep(60 - (now - window[0]) + 0.05)


class OpenRouterClient(LLMClient):
    def __init__(self) -> None:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Add it to .env or export it before starting the backend."
            )
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://clincase.local",
                "X-Title": "ClinCase",
            },
            http_client=_http_client(),
            # The SDK backs off exponentially and honours Retry-After on 429/5xx.
            max_retries=settings.LLM_MAX_RETRIES,
        )
        self._default_model = settings.OPENROUTER_MODEL
        self._extra_body = _extra_body()

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
        async with _slot():
            await _respect_rpm()
            completion = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                extra_body=self._extra_body,
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
            extra_body=self._extra_body,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
