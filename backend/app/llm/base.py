"""LLM provider interface contract.

Every provider implementation (Anthropic direct, AWS Bedrock) must
implement `LLMClient` and return `LLMResponse`. Agent code depends only
on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    """Structured LLM response. Keep this stable across providers."""

    model_config = ConfigDict(protected_namespaces=())

    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    model_id: str
    guardrail_action: dict | None = None


class LLMClient(ABC):
    """Abstract LLM client. Implementations: AnthropicClient, BedrockClient."""

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> LLMResponse:
        """Synchronous (single-shot) completion. Returns full response when done."""

    @abstractmethod
    async def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Streaming completion. Yields text deltas as they arrive."""
        if False:
            yield ""  # pragma: no cover (typing hint for AsyncIterator)

    async def complete_with_image(
        self,
        *,
        system: str,
        user: str,
        image_bytes: bytes,
        image_format: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> LLMResponse:
        """Multimodal completion — text prompt + one image.

        Default implementation raises NotImplementedError so providers that
        don't yet support vision (e.g. older OpenRouter routes) fail loudly.
        Bedrock + Anthropic implement this for real; the Document Intake
        layer's vision_extractor sub-agent depends on it.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image inputs. "
            f"Set LLM_PROVIDER=bedrock or LLM_PROVIDER=anthropic for "
            f"Document Intake."
        )
