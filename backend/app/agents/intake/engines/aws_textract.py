"""AWS Textract — printed-text + table extraction for typed scans.

Cheaper than vision-LLM on plain typed documents (lab reports, faxed
denial letters, structured forms). Fails gracefully if AWS creds are not
configured — the registry's fallback chain routes to ClaudeVisionEngine.

The Textract output is mapped into the same OCRResult shape every engine
produces, so the pipeline is engine-agnostic.

Notes on the mapping:
  - Textract returns text BLOCKS with confidence + bounding boxes.
  - We compute `overall_confidence` as the mean confidence of WORD blocks.
  - Structured fields are extracted from FORMS (KEY_VALUE_SET) when present;
    otherwise we surface the LINE blocks as `full_text` and leave the
    Vision/Shaper layer to do field naming.
"""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.errors import (
    EngineQuotaExceededError,
    EngineTimeoutError,
    EngineUnavailableError,
)
from app.config import settings
from app.models.intake import (
    DocumentClassification,
    ExtractedField,
    OCRResult,
)

# Map Textract block confidences (0-100) to our normalised [0, 1].
# Textract reports per-word confidence; we average across all WORD blocks
# for `overall_confidence`. A clean printed scan typically lands at 0.95+.
_MIN_CONFIDENCE_FOR_FIELD = 0.7


class AWSTextractEngine(OCREngine):
    """AWS Textract — printed-text path with table support."""

    name: ClassVar[str] = "aws_textract"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=True,        # Textract has a HANDWRITING feature, but accuracy is lower than Claude
        handles_typed_print=True,
        handles_tables=True,             # FORMS + TABLES feature types
        handles_pdf=True,                # async API path; sync API supports single-page PDFs
        requires_aws_credentials=True,
        requires_internet=True,
        typical_latency_ms=2500,
        cost_class="low",
    )

    def __init__(self) -> None:
        # Lazy boto3 client — created on first use so import never fails
        # when AWS creds are missing in dev.
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as e:  # pragma: no cover — boto3 is a project dep
                raise EngineUnavailableError(
                    "boto3 not installed",
                    detail={"hint": "pip install boto3"},
                ) from e
            self._client = boto3.client(
                "textract",
                config=Config(
                    region_name=settings.AWS_REGION,
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    read_timeout=30,
                ),
            )
        return self._client

    async def extract(
        self,
        *,
        image_bytes: bytes,
        image_format: str,
        classification: DocumentClassification,
    ) -> OCRResult:
        client = self._ensure_client()

        def _call() -> dict[str, Any]:
            return client.analyze_document(
                Document={"Bytes": image_bytes},
                # FORMS pulls KEY_VALUE_SETs (e.g. "Patient name: ___");
                # TABLES pulls structured tabular data (lab panels).
                FeatureTypes=["FORMS", "TABLES"],
            )

        try:
            response = await asyncio.to_thread(_call)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "throttl" in msg or "limitexceeded" in msg or "rate" in msg:
                raise EngineQuotaExceededError(
                    "Textract rate limit hit",
                    detail={"upstream_error": str(e)[:200]},
                ) from e
            if "timeout" in msg or "timed out" in msg:
                raise EngineTimeoutError(
                    "Textract call timed out",
                    detail={"upstream_error": str(e)[:200]},
                ) from e
            raise EngineUnavailableError(
                "Textract call failed",
                detail={"upstream_error": str(e)[:200]},
            ) from e

        return _map_textract_response(response, engine_name=self.name)

    async def healthcheck(self) -> bool:
        # Textract has no cheap ping endpoint; return True if creds load.
        # The first real call will surface auth errors via extract().
        try:
            self._ensure_client()
            return True
        except EngineUnavailableError:
            return False


def _map_textract_response(response: dict[str, Any], *, engine_name: str) -> OCRResult:
    """Translate Textract's block tree into our OCRResult shape."""
    blocks = response.get("Blocks", [])
    word_confidences: list[float] = []
    line_texts: list[str] = []

    # Build a dict of id → block for KEY_VALUE_SET resolution
    by_id = {b["Id"]: b for b in blocks if "Id" in b}

    for b in blocks:
        bt = b.get("BlockType")
        if bt == "WORD":
            conf = b.get("Confidence", 0.0)
            if isinstance(conf, int | float):
                word_confidences.append(conf / 100.0)
        elif bt == "LINE":
            text = b.get("Text") or ""
            if text:
                line_texts.append(text)

    # Compute overall confidence as mean of word confidences (graceful default)
    overall = (
        sum(word_confidences) / len(word_confidences)
        if word_confidences
        else 0.0
    )

    # Pull FORMS (KEY_VALUE_SET) into ExtractedField rows
    extracted: list[ExtractedField] = []
    for b in blocks:
        if (
            b.get("BlockType") == "KEY_VALUE_SET"
            and "KEY" in (b.get("EntityTypes") or [])
        ):
            key_text = _resolve_text(b, by_id)
            value_b = _find_value_for_key(b, by_id)
            value_text = _resolve_text(value_b, by_id) if value_b else ""
            conf = (b.get("Confidence", 0.0) / 100.0) if "Confidence" in b else 0.0
            if conf >= _MIN_CONFIDENCE_FOR_FIELD and key_text and value_text:
                extracted.append(
                    ExtractedField(
                        # Textract field names are free-text — pass through to
                        # the FHIR shaper for normalisation.
                        name=f"textract.{key_text.strip().lower().replace(' ', '_')[:60]}",
                        value=value_text.strip()[:200],
                        confidence=round(conf, 3),
                        source_excerpt=f"{key_text}: {value_text}"[:200],
                        page=int(b.get("Page", 1)),
                    )
                )

    return OCRResult(
        engine=engine_name,
        full_text="\n".join(line_texts),
        extracted_fields=extracted,
        overall_confidence=round(overall, 3),
        phi_redactions_applied=0,  # Textract doesn't redact — handled downstream
        pages=int(response.get("DocumentMetadata", {}).get("Pages", 1)),
    )


def _resolve_text(block: dict | None, by_id: dict) -> str:
    """Walk a block's CHILD relationships and concatenate WORD/SELECTION_ELEMENT text."""
    if not block:
        return ""
    pieces: list[str] = []
    for rel in block.get("Relationships", []) or []:
        if rel.get("Type") != "CHILD":
            continue
        for child_id in rel.get("Ids", []) or []:
            child = by_id.get(child_id)
            if not child:
                continue
            if child.get("BlockType") == "WORD":
                pieces.append(child.get("Text", ""))
            elif child.get("BlockType") == "SELECTION_ELEMENT" and child.get("SelectionStatus") == "SELECTED":
                pieces.append("[X]")
    return " ".join(pieces)


def _find_value_for_key(key_block: dict, by_id: dict) -> dict | None:
    for rel in key_block.get("Relationships", []) or []:
        if rel.get("Type") == "VALUE":
            for vid in rel.get("Ids", []) or []:
                v = by_id.get(vid)
                if v:
                    return v
    return None
