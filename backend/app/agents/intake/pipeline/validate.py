"""Validate stage — confidence threshold + binding-field check.

Soft validation only — never raises. Sets risk_flags + requires_human_review
on the context so the assemble stage can propagate them to the IntakeResult.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.intake.errors import (
    SOFT_FLAG_LOW_CONFIDENCE,
    SOFT_FLAG_MISSING_BINDING,
)
from app.agents.intake.pipeline.base import IntakeContext, IntakeStage

# Critical fields whose absence forces requires_human_review=True
_BINDING_FIELD_NAMES = {
    "requested_treatment.name",
    "primary_diagnosis.description",
}

_HITL_CONFIDENCE_THRESHOLD = 0.7


class ValidateStage(IntakeStage):
    """Apply HITL routing rules + binding-field check."""

    name: ClassVar[str] = "validate"
    inputs_required: ClassVar[list[str]] = ["extract.ocr"]
    outputs_produced: ClassVar[list[str]] = ["validate.requires_human_review"]

    async def run(self, ctx: IntakeContext) -> None:
        ocr = ctx.payload.get("extract.ocr")
        if ocr is None:
            ctx.payload["validate.requires_human_review"] = True
            return

        overall = float(getattr(ocr, "overall_confidence", 0.0))
        field_names = {f.name for f in getattr(ocr, "extracted_fields", [])}
        missing_binding = _BINDING_FIELD_NAMES - field_names

        requires_review = False
        if overall < _HITL_CONFIDENCE_THRESHOLD:
            requires_review = True
            if SOFT_FLAG_LOW_CONFIDENCE not in ctx.risk_flags:
                ctx.risk_flags.append(SOFT_FLAG_LOW_CONFIDENCE)
        if missing_binding:
            requires_review = True
            if SOFT_FLAG_MISSING_BINDING not in ctx.risk_flags:
                ctx.risk_flags.append(SOFT_FLAG_MISSING_BINDING)

        ctx.payload["validate.requires_human_review"] = requires_review
        ctx.payload["validate.missing_binding_fields"] = sorted(missing_binding)
