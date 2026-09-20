"""Assemble stage — build the final IntakeResult from accumulated context.

Always runs last — even on short-circuit. Reads whatever upstream stages
populated and produces a complete, schema-valid IntakeResult. Extracts
the partial ClinicalSnapshot from the vision response when present.

This is the only stage that touches the IntakeResult Pydantic model
directly; every other stage works on the IntakeContext payload dict.
"""
from __future__ import annotations

from typing import Any, ClassVar

from app.agents.intake.pipeline.base import IntakeContext, IntakeStage
from app.agents.intake.pipeline.deduplicate import _store_in_cache
from app.models.intake import (
    DocumentClassification,
    IntakeResult,
    OCRResult,
)


class AssembleStage(IntakeStage):
    """Materialize the IntakeResult from accumulated context."""

    name: ClassVar[str] = "assemble"
    inputs_required: ClassVar[list[str]] = []  # works on whatever's there
    outputs_produced: ClassVar[list[str]] = ["assemble.intake_result"]

    async def run(self, ctx: IntakeContext) -> None:
        # Cache hit short-circuit returns the cached dict verbatim
        cached = ctx.payload.get("deduplicate.cached_intake_result")
        if cached is not None:
            ctx.payload["assemble.intake_result"] = IntakeResult.model_validate(cached)
            return

        classification: DocumentClassification | None = ctx.payload.get(
            "classify.classification"
        )
        ocr: OCRResult | None = ctx.payload.get("extract.ocr")

        # Best-effort fallback when classification missing (e.g. preprocess
        # failed) — produce an "unreadable" sentinel so the downstream
        # case_router can dispatch to HITL.
        if classification is None:
            classification = DocumentClassification(
                document_type="unreadable",
                confidence=0.0,
                rationale=ctx.short_circuit_reason or "Preprocessing failed.",
                quality_flags=[],
            )

        if ocr is None:
            ocr = OCRResult(
                engine="claude_vision_bedrock",  # default that's claimed but never invoked
                full_text="",
                extracted_fields=[],
                overall_confidence=0.0,
                phi_redactions_applied=0,
                pages=1,
            )

        # Vision engines stamp clinical_snapshot_partial onto the OCRResult;
        # OCR-only engines leave it empty and the FHIR shaper derives it
        # downstream from full_text.
        clinical_snapshot_partial: dict[str, Any] = (
            getattr(ocr, "clinical_snapshot_partial", None) or {}
        )

        requires_review = bool(
            ctx.payload.get("validate.requires_human_review", True)
            if ocr.extracted_fields
            else True
        )

        result = IntakeResult(
            classification=classification,
            ocr=ocr,
            clinical_snapshot_partial=clinical_snapshot_partial,
            risk_flags=list(dict.fromkeys(ctx.risk_flags)),  # dedupe preserve order
            requires_human_review=requires_review,
            audit={
                "document_sha256": ctx.sha256,
                "engines_used": _engines_from_attempts(ctx.payload),
                "latency_ms": sum(ctx.timings_ms.values()),
                "stage_timings_ms": ctx.timings_ms,
                "extract_attempts": ctx.payload.get("extract.attempts", []),
                "short_circuit_reason": ctx.short_circuit_reason,
                "schema_version": "v1",
            },
        )

        ctx.payload["assemble.intake_result"] = result

        # Populate the dedup cache on successful runs so the next call with
        # the same SHA-256 returns immediately. Skip caching of failures so
        # transient errors aren't sticky.
        if ocr.extracted_fields and not ctx.payload.get("deduplicate.cache_hit"):
            _store_in_cache(ctx.sha256, result.model_dump())


def _engines_from_attempts(payload: dict) -> list[str]:
    """Build the engines_used list from extract attempts + classifier."""
    out = ["pil_classifier"]
    for a in payload.get("extract.attempts", []):
        if a.get("ok") and a.get("engine") and a["engine"] not in out:
            out.append(a["engine"])
    if "extract.engine_used" in payload and payload["extract.engine_used"] not in out:
        out.append(payload["extract.engine_used"])
    return out
