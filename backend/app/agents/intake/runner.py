"""Intake runner — thin facade over the multi-stage pipeline.

Public API:
  parse_document(IntakeDocument) -> IntakeResult

This is the only function downstream code (the FastAPI endpoint, the
case-creation flow) imports. The implementation now lives in
`app/agents/intake/pipeline/` — six named stages connected by an
orchestrator with per-stage timing, a SHA-256 idempotency cache, MIME
sniffing, EXIF stripping, decompression-bomb protection, and an OCR
engine fallback chain.

Why the facade: callers don't care about the internal pipeline shape
and shouldn't have to import IntakeContext or the stage classes. Future
refactors (adding a stage, swapping orchestrator implementation) can
land without breaking any caller.
"""
from __future__ import annotations

from app.agents.intake.pipeline import run_intake_pipeline
from app.models.intake import IntakeDocument, IntakeResult


async def parse_document(doc: IntakeDocument) -> IntakeResult:
    """End-to-end intake. Always returns an IntakeResult; never raises.

    Pipeline (in order):
      1. preprocess  — magic-byte MIME sniff, EXIF strip, bomb guard
      2. deduplicate — SHA-256 cache (60 min TTL) → cache hit short-circuits
      3. classify    — PIL stats → typed/handwritten/mixed + engine chain
      4. extract     — runs OCR engines in fallback order; first wins
      5. validate    — confidence threshold + binding-field check → HITL
      6. assemble    — build IntakeResult + populate dedup cache

    Per-stage timing lands in IntakeResult.audit.stage_timings_ms.
    """
    return await run_intake_pipeline(doc)
