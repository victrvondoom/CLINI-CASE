"""AWS Bedrock implementation of LLMClient.

Activated by setting LLM_PROVIDER=bedrock. Requires AWS credentials in
the environment (via task role on ECS, or `aws configure` locally).

This client uses the Bedrock Converse API for vendor-neutral chat.
Guardrails (BEDROCK_GUARDRAIL_ID) are applied automatically when set.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings
from app.llm.base import LLMClient, LLMResponse


class BedrockClient(LLMClient):
    def __init__(self) -> None:
        cfg = Config(
            region_name=settings.AWS_REGION,
            retries={"max_attempts": 3, "mode": "adaptive"},
            read_timeout=120,
        )
        self._client = boto3.client("bedrock-runtime", config=cfg)
        self._default_model = settings.BEDROCK_MODEL_ID

    def _guardrail_kwargs(self) -> dict[str, Any]:
        if not settings.BEDROCK_GUARDRAIL_ID:
            return {}
        return {
            "guardrailConfig": {
                "guardrailIdentifier": settings.BEDROCK_GUARDRAIL_ID,
                "guardrailVersion": settings.BEDROCK_GUARDRAIL_VERSION,
                "trace": "enabled",
            }
        }

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> LLMResponse:
        # boto3 is sync; we run it in the thread pool to keep the event loop free.
        import asyncio

        model = model_id or self._default_model

        def _call() -> dict[str, Any]:
            return self._client.converse(
                modelId=model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
                **self._guardrail_kwargs(),
            )

        response = await asyncio.to_thread(_call)
        text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            stop_reason=response.get("stopReason", "unknown"),
            model_id=model,
            guardrail_action=response.get("trace", {}).get("guardrail"),
        )

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
        """Multimodal Bedrock invoke — Converse API with image content block.

        The Bedrock Converse API natively accepts image bytes inside the
        message content list (see AWS docs § Image Content). Used by the
        Document Intake layer's vision_extractor to read handwritten Rx
        slips, scanned echo reports, and faxed denial letters.

        image_format: "png", "jpeg", "webp", or "gif" (no `image/` prefix).
        """
        import asyncio

        model = model_id or self._default_model
        fmt = image_format.lower().replace("image/", "")
        if fmt not in {"png", "jpeg", "webp", "gif"}:
            raise ValueError(
                f"Bedrock vision supports png/jpeg/webp/gif; got {image_format!r}"
            )

        def _call() -> dict[str, Any]:
            return self._client.converse(
                modelId=model,
                system=[{"text": system}],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": fmt,
                                    "source": {"bytes": image_bytes},
                                }
                            },
                            {"text": user},
                        ],
                    }
                ],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
                **self._guardrail_kwargs(),
            )

        response = await asyncio.to_thread(_call)
        text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            stop_reason=response.get("stopReason", "unknown"),
            model_id=model,
            guardrail_action=response.get("trace", {}).get("guardrail"),
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
        import asyncio

        model = model_id or self._default_model

        def _call() -> Any:
            return self._client.converse_stream(
                modelId=model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
                **self._guardrail_kwargs(),
            )

        response = await asyncio.to_thread(_call)
        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    yield delta["text"]
            elif "messageStop" in event:
                return
