"""PyPDF text-extraction engine — zero-dependency PDF fallback.

Uses `pypdf` (already in requirements) to extract the text layer from a
PDF. Works on any machine without AWS credentials — ideal for local dev,
CI, and as a cheap fallback when Textract is unavailable.

Limitations vs Textract:
  - Extracts text layer only; purely scanned (image-only) PDFs return empty.
  - No table detection, no handwriting.
  - Field extraction is skipped — the Clinical Extractor agent downstream
    receives `full_text` and parses structured fields from it.
"""
from __future__ import annotations

import io
from typing import ClassVar

from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.errors import EngineUnavailableError
from app.models.intake import DocumentClassification, OCRResult


class PyPDFEngine(OCREngine):
    """pypdf text-layer extractor — handles PDFs that have a text layer."""

    name: ClassVar[str] = "pypdf_text"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=False,
        handles_typed_print=True,
        handles_tables=False,
        handles_pdf=True,
        requires_aws_credentials=False,
        requires_internet=False,
        typical_latency_ms=80,
        cost_class="free",
    )

    async def extract(
        self,
        *,
        image_bytes: bytes,
        image_format: str,
        classification: DocumentClassification,
    ) -> OCRResult:
        if image_format != "pdf":
            raise EngineUnavailableError(
                "PyPDFEngine only handles PDFs",
                detail={"image_format": image_format},
            )
        try:
            from pypdf import PdfReader  # local import so startup is unaffected if pypdf missing

            reader = PdfReader(io.BytesIO(image_bytes))
            page_texts = [page.extract_text() or "" for page in reader.pages]
            full_text = "\n\n".join(t for t in page_texts if t.strip())
            n_pages = len(reader.pages)
        except Exception as exc:
            raise EngineUnavailableError(
                "pypdf extraction failed",
                detail={"error": str(exc)[:200]},
            ) from exc

        if not full_text.strip():
            raise EngineUnavailableError(
                "pypdf extracted no text — this PDF may be scanned/image-only. "
                "Use AWSTextractEngine for image-only PDFs.",
                detail={"pages": n_pages},
            )

        return OCRResult(
            engine=self.name,
            full_text=full_text,
            extracted_fields=[],   # No field-level parsing; Clinical Extractor handles it
            overall_confidence=0.70,
            phi_redactions_applied=0,
            pages=n_pages,
        )
