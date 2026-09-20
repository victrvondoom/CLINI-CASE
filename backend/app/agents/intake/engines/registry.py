"""Engine registry + selection logic.

Two layers of routing:

  1. **Selection** — given a classification, pick the SINGLE best engine
     for that document type. Used for the happy path.

  2. **Fallback chain** — given a classification, return an ordered list
     of engines to try in sequence on the unhappy path. The orchestrator
     iterates the chain on EngineUnavailableError / EngineQuotaExceededError
     until one succeeds (or all fail).

Registry order matters: when multiple engines could handle a document,
the EARLIER one in the registry wins. Override per-tenant by setting
`tenant_policies.preferred_intake_engine` (planned).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from app.agents.intake.engines.aws_textract import AWSTextractEngine
from app.agents.intake.engines.base import OCREngine
from app.agents.intake.engines.claude_vision import ClaudeVisionEngine
from app.agents.intake.engines.pypdf_engine import PyPDFEngine
from app.agents.intake.engines.tesseract import TesseractEngine
from app.models.intake import DocumentClassification

log = logging.getLogger(__name__)

# Order = priority. First match wins for happy-path selection; full list
# becomes the fallback chain on errors. Vision sits at the top because
# it's the only engine that handles handwriting reliably — and a typed
# print document still extracts well from it (just slower / more expensive).
ENGINE_REGISTRY: list[OCREngine] = [
    ClaudeVisionEngine(),   # 1st: LLM vision — best quality, handles all doc types
    PyPDFEngine(),          # 2nd: text-layer PDF extraction — free, no AWS needed
    AWSTextractEngine(),    # 3rd: Textract — image-only PDFs + typed print
    TesseractEngine(),      # 4th: last-resort local OCR
]


def _supports(engine: OCREngine, doc_type: str, *, is_pdf: bool = False) -> bool:
    cap = engine.capabilities
    # PDF gate — image-only engines (vision, tesseract) can't decode a PDF.
    # Only engines that declare handles_pdf=True are eligible when the bytes
    # are actually a PDF document.
    if is_pdf and not cap.handles_pdf:
        return False
    if doc_type == "handwritten":
        return cap.handles_handwriting
    if doc_type in ("typed_print", "structured_form"):
        return cap.handles_typed_print
    if doc_type == "mixed":
        # Need both — vision is the only one that genuinely handles mixed
        return cap.handles_handwriting and cap.handles_typed_print
    return cap.handles_typed_print  # safe default


def select_engine(
    classification: DocumentClassification, *, is_pdf: bool = False
) -> OCREngine | None:
    """Pick the single best engine for the document type. Returns None if
    nothing in the registry can handle it (caller should route to HITL)."""
    for eng in ENGINE_REGISTRY:
        if _supports(eng, classification.document_type, is_pdf=is_pdf):
            return eng
    return None


def select_fallback_chain(
    classification: DocumentClassification, *, is_pdf: bool = False
) -> list[OCREngine]:
    """Return all engines that can plausibly handle this doc, in priority order.

    For handwritten documents we ONLY return engines that declare
    handwriting support — no point falling back to Tesseract, which will
    silently produce garbage. For typed/mixed we include all candidates.

    When `is_pdf=True` (or the classification carries the `pdf-document`
    quality flag), only PDF-capable engines are included — vision and
    Tesseract get filtered out so we don't waste a Bedrock call on bytes
    they can't decode."""
    pdf = is_pdf or "pdf-document" in classification.quality_flags
    chain: list[OCREngine] = []
    for eng in ENGINE_REGISTRY:
        if _supports(eng, classification.document_type, is_pdf=pdf):
            chain.append(eng)
    return chain


def get_engine_by_name(name: str) -> OCREngine | None:
    """Lookup by engine name — used by tests + observability."""
    for eng in ENGINE_REGISTRY:
        if eng.name == name:
            return eng
    return None


# ---------------------------------------------------------------------------
# Test seam: replace the registry contents (used by contract tests so they
# can inject mock engines without monkey-patching the module).
# ---------------------------------------------------------------------------
def _reset_registry(engines: Iterable[OCREngine]) -> None:
    """For tests only. Replaces the registry contents in place."""
    ENGINE_REGISTRY.clear()
    ENGINE_REGISTRY.extend(engines)
