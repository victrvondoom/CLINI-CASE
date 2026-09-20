"""Abstract OCR engine — every concrete engine implements this contract.

Bounded responsibility: an OCREngine takes raw image bytes (+ classification
hint) and returns an `OCRResult` shaped exactly like what the pipeline's
`assemble` stage expects. It does NOT classify, validate confidence, or
build the full `IntakeResult` — those concerns live in dedicated stages.

`EngineCapabilities` is metadata the registry uses to route documents:
e.g. only Textract is good at extracting tables; only Claude vision can
read handwriting reliably.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.models.intake import DocumentClassification, OCRResult


@dataclass(frozen=True)
class EngineCapabilities:
    """Declarative capability matrix for an engine.

    The registry uses these flags to pick the right engine for a given
    classification + size. Flags are intentionally coarse — fine-grained
    routing belongs in tenant config, not here.
    """

    handles_handwriting: bool = False
    handles_typed_print: bool = True
    handles_tables: bool = False
    handles_pdf: bool = False
    requires_aws_credentials: bool = False
    requires_internet: bool = True
    typical_latency_ms: int = 5000
    cost_class: str = "medium"  # "low" / "medium" / "high"


class OCREngine(ABC):
    """Abstract OCR engine. Subclasses register with `registry.register()`.

    Stateless by contract — instances are reused across requests. If your
    engine needs warm state (e.g. an HTTP session), create it in __init__
    and never mutate per-request.
    """

    name: ClassVar[str] = "abstract"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities()

    @abstractmethod
    async def extract(
        self,
        *,
        image_bytes: bytes,
        image_format: str,
        classification: DocumentClassification,
    ) -> OCRResult:
        """Extract text + structured fields from the image.

        Args:
            image_bytes: raw bytes of the document.
            image_format: "png" / "jpeg" / "webp" / "pdf" (lowercased,
                          no `image/` prefix).
            classification: the upstream classifier's verdict, used as a
                            reading-strategy hint in the prompt.

        Returns:
            OCRResult with `engine` field set to this engine's `name`.

        Raises:
            EngineUnavailableError, EngineTimeoutError, EngineQuotaExceededError.
            Should NOT raise IntakeError subclasses for low-confidence or
            partial extraction — those flow through risk_flags downstream.
        """
        raise NotImplementedError

    async def healthcheck(self) -> bool:
        """Quick readiness probe. Default returns True; engines that need
        live credentials should override and ping the upstream service.
        """
        return True
