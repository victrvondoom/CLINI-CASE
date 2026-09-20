"""Claude Sonnet 4.6 vision via AWS Bedrock — primary OCR engine.

Handles BOTH typed scans and handwritten content in a single call. The
Bedrock multimodal Converse API is wrapped via `LLMClient.complete_with_image()`
so the agent code stays provider-agnostic (per AAOSA gateway-plane rules).

Output shape: same `OCRResult` every engine returns. The structured field
extraction lives in the prompt at `app/prompts/intake/vision_extractor.txt`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.errors import (
    EngineQuotaExceededError,
    EngineTimeoutError,
    EngineUnavailableError,
)
from app.llm.factory import get_llm_client
from app.models.intake import (
    DocumentClassification,
    ExtractedField,
    OCRResult,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "intake" / "vision_extractor.txt"
).read_text(encoding="utf-8")


def _strip_code_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return s.strip()


def _classification_hint(c: DocumentClassification) -> str:
    flags = ", ".join(c.quality_flags) if c.quality_flags else "none"
    return (
        f"Document classification: {c.document_type} "
        f"(classifier confidence {c.confidence:.2f}). "
        f"Quality flags: {flags}. Reading strategy: see Reading-strategy section "
        f"for {c.document_type} in the system prompt. "
        f"Now read this document and emit the structured JSON."
    )


class ClaudeVisionEngine(OCREngine):
    """Bedrock multimodal Sonnet 4.6 — handles all document types."""

    name: ClassVar[str] = "claude_vision_bedrock"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=True,
        handles_typed_print=True,
        handles_tables=True,
        handles_pdf=False,
        requires_aws_credentials=True,
        requires_internet=True,
        typical_latency_ms=9000,
        cost_class="medium",
    )

    async def extract(
        self,
        *,
        image_bytes: bytes,
        image_format: str,
        classification: DocumentClassification,
    ) -> OCRResult:
        client = get_llm_client()
        try:
            response = await client.complete_with_image(
                system=_PROMPT,
                user=_classification_hint(classification),
                image_bytes=image_bytes,
                image_format=image_format,
                max_tokens=2000,
                temperature=0.0,
            )
        except NotImplementedError as e:
            raise EngineUnavailableError(
                f"Provider {client.__class__.__name__} does not support vision",
                detail={"provider": client.__class__.__name__},
            ) from e
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            # Crude classification of upstream errors — refined later by
            # the registry's circuit breaker. ThrottlingException →
            # quota; TimeoutError / ReadTimeoutError → timeout; everything
            # else → unavailable.
            if "throttl" in msg or "quota" in msg or "rate" in msg:
                raise EngineQuotaExceededError(
                    "Bedrock rate limit hit on vision call",
                    detail={"upstream_error": str(e)[:200]},
                ) from e
            if "timeout" in msg or "timed out" in msg:
                raise EngineTimeoutError(
                    "Bedrock vision call timed out",
                    detail={"upstream_error": str(e)[:200]},
                ) from e
            raise EngineUnavailableError(
                "Bedrock vision call failed",
                detail={"upstream_error": str(e)[:200]},
            ) from e

        try:
            parsed = json.loads(_strip_code_fence(response.text))
        except json.JSONDecodeError as e:
            raise EngineUnavailableError(
                "Vision extractor returned non-JSON",
                detail={"first_chars": response.text[:160], "json_error": str(e)},
            ) from e

        extracted = [ExtractedField(**f) for f in parsed.get("extracted_fields", [])]

        return OCRResult(
            engine=self.name,
            full_text=parsed.get("full_text", ""),
            extracted_fields=extracted,
            overall_confidence=float(parsed.get("overall_confidence", 0.0)),
            phi_redactions_applied=int(parsed.get("phi_redactions_applied", 0)),
            pages=int(parsed.get("pages", 1)),
            clinical_snapshot_partial=parsed.get("clinical_snapshot_partial") or {},
        )
