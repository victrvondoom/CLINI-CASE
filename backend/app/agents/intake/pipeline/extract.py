"""Extract stage — runs OCR engines via the fallback chain.

Iterates the engines selected by the classify stage. The first engine
that returns successfully wins. On EngineUnavailableError /
EngineTimeoutError / EngineQuotaExceededError, we move to the next
engine and append `engine-fallback-used` to risk_flags.

If ALL engines fail, the stage short-circuits with `intake-failed` and
the assemble stage emits a HITL-routed empty result.
"""
from __future__ import annotations

import time
from typing import ClassVar

from app.agents.intake.errors import (
    SOFT_FLAG_ENGINE_FALLBACK,
    SOFT_FLAG_INTAKE_FAILED,
    EngineQuotaExceededError,
    EngineTimeoutError,
    EngineUnavailableError,
    IntakeError,
)
from app.agents.intake.pipeline.base import IntakeContext, IntakeStage


class ExtractStage(IntakeStage):
    """Run OCR engines until one succeeds, in priority order."""

    name: ClassVar[str] = "extract"
    inputs_required: ClassVar[list[str]] = ["classify.classification"]
    outputs_produced: ClassVar[list[str]] = ["extract.ocr", "extract.engine_used"]

    async def run(self, ctx: IntakeContext) -> None:
        classification = ctx.payload.get("classify.classification")
        if classification is None or not ctx.fallback_chain:
            ctx.short_circuit = True
            ctx.short_circuit_reason = "No engine in the fallback chain can handle this document."
            if SOFT_FLAG_INTAKE_FAILED not in ctx.risk_flags:
                ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
            return

        last_error: IntakeError | None = None
        attempts: list[dict] = []

        for i, engine in enumerate(ctx.fallback_chain):
            t0 = time.monotonic()
            try:
                ocr = await engine.extract(
                    image_bytes=ctx.image_bytes,
                    image_format=ctx.image_format,
                    classification=classification,
                )
                ctx.payload["extract.ocr"] = ocr
                ctx.payload["extract.engine_used"] = engine.name
                attempts.append({
                    "engine": engine.name,
                    "ok": True,
                    "elapsed_ms": int((time.monotonic() - t0) * 1000),
                })
                if i > 0:
                    # We had to fall back — flag it for downstream observability.
                    ctx.risk_flags.append(SOFT_FLAG_ENGINE_FALLBACK)
                ctx.payload["extract.attempts"] = attempts
                return
            except (EngineUnavailableError, EngineTimeoutError, EngineQuotaExceededError) as e:
                last_error = e
                attempts.append({
                    "engine": engine.name,
                    "ok": False,
                    "error_code": e.code,
                    "error_message": e.message[:160],
                    "elapsed_ms": int((time.monotonic() - t0) * 1000),
                })
                continue

        # All engines failed — graceful HITL routing
        ctx.payload["extract.attempts"] = attempts
        ctx.short_circuit = True
        ctx.short_circuit_reason = (
            f"All {len(ctx.fallback_chain)} engine(s) in the fallback chain failed. "
            f"Last error: {last_error.code if last_error else 'unknown'}."
        )
        if SOFT_FLAG_INTAKE_FAILED not in ctx.risk_flags:
            ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
