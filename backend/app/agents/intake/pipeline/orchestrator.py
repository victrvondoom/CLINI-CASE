"""Pipeline orchestrator — runs stages in order with per-stage timing.

The orchestrator is the only place that knows the stage order. Stages
themselves are independent and don't import each other. To re-order or
swap a stage, edit `_STAGES` here.

Per-stage timing accumulates into `ctx.timings_ms` and lands in the
IntakeResult.audit.stage_timings_ms — observable in the audit ledger.
"""
from __future__ import annotations

import logging
import time

from app.agents.intake.errors import SOFT_FLAG_INTAKE_FAILED
from app.agents.intake.pipeline.assemble import AssembleStage
from app.agents.intake.pipeline.base import IntakeContext, IntakeStage
from app.agents.intake.pipeline.classify import ClassifyStage
from app.agents.intake.pipeline.deduplicate import DeduplicateStage
from app.agents.intake.pipeline.extract import ExtractStage
from app.agents.intake.pipeline.preprocess import PreprocessStage
from app.agents.intake.pipeline.validate import ValidateStage
from app.models.intake import IntakeDocument, IntakeResult

log = logging.getLogger(__name__)

# Pipeline order. The assemble stage ALWAYS runs last (even on short-circuit)
# so the audit ledger reconstructs every hop.
_STAGES: list[IntakeStage] = [
    PreprocessStage(),
    DeduplicateStage(),
    ClassifyStage(),
    ExtractStage(),
    ValidateStage(),
    AssembleStage(),
]


async def run_intake_pipeline(doc: IntakeDocument) -> IntakeResult:
    """Run all pipeline stages and return the IntakeResult.

    Never raises. Any unexpected exception in a stage is caught, logged,
    converted into a risk_flag, and the pipeline continues to assemble.
    The case_router downstream uses requires_human_review to dispatch.
    """
    import base64

    ctx = IntakeContext(
        image_bytes=base64.b64decode(doc.image_b64),
        image_format=doc.mime_type.split("/")[-1].replace("jpg", "jpeg"),
        filename=doc.filename,
        mime_type=doc.mime_type,
        sha256=doc.sha256,
        source=doc.source,
    )

    for stage in _STAGES:
        # Every stage runs except non-essential ones when short-circuit is
        # set. Assemble ALWAYS runs (it's the IntakeResult builder).
        if ctx.short_circuit and stage.name not in ("assemble",):
            continue

        t0 = time.monotonic()
        try:
            await stage.run(ctx)
        except Exception as e:  # noqa: BLE001
            log.exception("intake.stage.crashed", extra={
                "stage": stage.name,
                "error": str(e)[:200],
                "sha256_prefix": ctx.sha256[:12],
            })
            ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
            ctx.short_circuit = True
            ctx.short_circuit_reason = (
                f"Stage '{stage.name}' crashed: {type(e).__name__}: {str(e)[:120]}"
            )
        finally:
            ctx.timings_ms[stage.name] = int((time.monotonic() - t0) * 1000)

    # The assemble stage guarantees ctx.payload["assemble.intake_result"] is set
    result = ctx.payload.get("assemble.intake_result")
    if result is None:
        # Defensive — should never happen because AssembleStage runs even on short-circuit.
        # If it does, manufacture a HITL result so the API never returns nothing.
        from app.agents.intake.pipeline.assemble import AssembleStage as _A
        await _A().run(ctx)
        result = ctx.payload["assemble.intake_result"]
    return result
