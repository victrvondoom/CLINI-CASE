"""Classify stage — wraps the rule-based PIL classifier.

Thin adapter so the orchestrator + audit log treats classification as a
first-class hop. Picks the engine fallback chain for downstream stages.

PDF short-circuit: PIL can't decode PDFs natively, so we trust the
preprocess stage's magic-byte verdict and route directly to the PDF-capable
extraction engines (PyPDF + Textract). The PIL classifier never sees a PDF.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.intake.classifier import classify_document
from app.agents.intake.engines.registry import select_fallback_chain
from app.agents.intake.errors import SOFT_FLAG_INTAKE_FAILED
from app.agents.intake.pipeline.base import IntakeContext, IntakeStage
from app.models.intake import DocumentClassification


class ClassifyStage(IntakeStage):
    """Run the deterministic PIL classifier; populate engine fallback chain."""

    name: ClassVar[str] = "classify"
    inputs_required: ClassVar[list[str]] = ["preprocess.detected_mime"]
    outputs_produced: ClassVar[list[str]] = ["classify.classification"]

    async def run(self, ctx: IntakeContext) -> None:
        # PDF fast path — preprocess already verified the %PDF- magic bytes,
        # so we know it's a valid PDF. PIL cannot decode PDFs and will always
        # raise; bypass the classifier entirely and route to PDF engines.
        if ctx.image_format == "pdf" or ctx.payload.get("preprocess.detected_mime") == "application/pdf":
            classification = DocumentClassification(
                document_type="typed_print",
                confidence=0.90,
                rationale="PDF document — routed to PDF-capable extraction engine (PyPDF / Textract).",
                quality_flags=["pdf-document"],
            )
            ctx.payload["classify.classification"] = classification
            for q in classification.quality_flags:
                if q not in ctx.risk_flags:
                    ctx.risk_flags.append(q)
            ctx.fallback_chain = select_fallback_chain(classification)
            return

        classification = classify_document(ctx.image_bytes)
        ctx.payload["classify.classification"] = classification

        if classification.document_type == "unreadable":
            ctx.short_circuit = True
            ctx.short_circuit_reason = "Classifier marked the document unreadable."
            ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
            ctx.fallback_chain = []
            return

        # Fold quality flags into the running risk_flags so they survive
        # to the final IntakeResult.
        for q in classification.quality_flags:
            if q not in ctx.risk_flags:
                ctx.risk_flags.append(q)

        ctx.fallback_chain = select_fallback_chain(classification)
