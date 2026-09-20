"""Tesseract OCR — local fallback engine.

Used only when both Bedrock vision and AWS Textract are unavailable
(e.g. dev environments without internet). Does NOT extract structured
fields — the FHIR shaper has to derive them from `full_text` downstream.

Optional dependency: `pytesseract` + Tesseract binary on the system. If
either is missing, the engine reports unhealthy and the registry skips
it. ClinCase never crashes because tesseract isn't installed.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.errors import EngineUnavailableError
from app.models.intake import DocumentClassification, OCRResult


class TesseractEngine(OCREngine):
    """Local Tesseract OCR — last-resort fallback."""

    name: ClassVar[str] = "tesseract_local"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=False,       # Tesseract on handwriting is poor
        handles_typed_print=True,
        handles_tables=False,
        handles_pdf=False,
        requires_aws_credentials=False,
        requires_internet=False,
        typical_latency_ms=1200,
        cost_class="low",
    )

    async def extract(
        self,
        *,
        image_bytes: bytes,
        image_format: str,
        classification: DocumentClassification,
    ) -> OCRResult:
        try:
            import io

            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise EngineUnavailableError(
                "pytesseract not installed",
                detail={"hint": "pip install pytesseract; install Tesseract binary"},
            ) from e

        def _call() -> dict[str, str | float]:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
            # `image_to_data` returns per-word confidences we can average.
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for w, c in zip(data.get("text", []), data.get("conf", []), strict=False):
                if not w or not w.strip():
                    continue
                try:
                    cf = float(c)
                    if cf < 0:
                        continue
                    confs.append(cf / 100.0)
                    words.append(w)
                except ValueError:
                    continue
            full_text = " ".join(words)
            overall = sum(confs) / len(confs) if confs else 0.0
            return {"full_text": full_text, "overall_confidence": overall}

        try:
            result = await asyncio.to_thread(_call)
        except Exception as e:  # noqa: BLE001
            raise EngineUnavailableError(
                "Tesseract execution failed",
                detail={"upstream_error": str(e)[:200]},
            ) from e

        return OCRResult(
            engine=self.name,
            full_text=str(result["full_text"]),
            extracted_fields=[],
            overall_confidence=round(float(result["overall_confidence"]), 3),
            phi_redactions_applied=0,
            pages=1,
        )

    async def healthcheck(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:  # noqa: BLE001 — any failure means engine unusable
            return False
