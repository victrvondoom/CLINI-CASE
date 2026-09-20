"""OCR engines — Strategy Pattern.

Every concrete engine implements `OCREngine.extract(image_bytes, hint)`
and returns the same `OCRResult` shape, so the pipeline layer can swap
engines without conditional branches.

Built-in engines:
  - ClaudeVisionEngine   (Bedrock multimodal Sonnet 4.6 — handles all)
  - AWSTextractEngine    (printed text + tables; cheaper for typed scans)
  - TesseractEngine      (local fallback when AWS is unreachable)

Add a new engine by subclassing `OCREngine` and registering with
`registry.register(...)`. The pipeline never imports concrete engines.
"""
from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.engines.registry import (
    ENGINE_REGISTRY,
    select_engine,
    select_fallback_chain,
)

__all__ = [
    "OCREngine",
    "EngineCapabilities",
    "ENGINE_REGISTRY",
    "select_engine",
    "select_fallback_chain",
]
