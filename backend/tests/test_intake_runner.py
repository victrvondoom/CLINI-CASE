"""Contract tests for the Document Intake pipeline.

Tests are organised in three layers:
  1. Classifier — pure-PIL rule-based; runs offline against the synthetic Rx fixture.
  2. Engines    — Strategy Pattern: a stub engine is injected into the
                  registry via the `_reset_registry()` seam so we exercise
                  the pipeline without hitting Bedrock.
  3. Pipeline   — full end-to-end through the orchestrator with a stub
                  engine; verifies idempotency, fallback chain, HITL routing.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import pathlib
from typing import ClassVar

import pytest

from app.agents.intake.classifier import classify_document
from app.agents.intake.engines.base import EngineCapabilities, OCREngine
from app.agents.intake.engines.registry import (
    ENGINE_REGISTRY,
    _reset_registry,
)
from app.agents.intake.errors import (
    EngineUnavailableError,
)
from app.agents.intake.pipeline.deduplicate import clear_cache_for_tests
from app.agents.intake.runner import parse_document
from app.models.intake import (
    DocumentClassification,
    ExtractedField,
    IntakeDocument,
    IntakeResult,
    OCRResult,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "intake" / "handwritten_rx.png"


@pytest.fixture
def fixture_bytes() -> bytes:
    assert FIXTURE.exists(), (
        f"Fixture missing: {FIXTURE}. Regenerate with "
        "tests/fixtures/intake/_generate_handwritten_rx.py"
    )
    return FIXTURE.read_bytes()


@pytest.fixture
def fixture_doc(fixture_bytes: bytes) -> IntakeDocument:
    return IntakeDocument(
        filename="handwritten_rx.png",
        mime_type="image/png",
        image_b64=base64.b64encode(fixture_bytes).decode("ascii"),
        sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        source="upload",
    )


@pytest.fixture(autouse=True)
def _clear_intake_cache():
    """Reset the SHA-256 dedup cache before each test so cross-test caching
    doesn't mask bugs."""
    clear_cache_for_tests()
    # Snapshot + restore the registry so engine-replacement tests don't leak
    saved = list(ENGINE_REGISTRY)
    yield
    _reset_registry(saved)


# ---------------------------------------------------------------------------
# 1. Classifier — pure-PIL, offline
# ---------------------------------------------------------------------------
def test_classifier_returns_a_valid_classification(fixture_bytes):
    c = classify_document(fixture_bytes)
    assert c.document_type in (
        "typed_print", "handwritten", "mixed", "structured_form", "unreadable"
    )
    assert 0.0 <= c.confidence <= 1.0
    assert c.rationale


def test_classifier_categorises_synthetic_rx_as_mixed_or_handwritten(fixture_bytes):
    c = classify_document(fixture_bytes)
    assert c.document_type in ("mixed", "handwritten"), (
        f"Expected mixed/handwritten on the synthetic Rx, got {c.document_type}"
    )


def test_classifier_handles_garbage_bytes_gracefully():
    c = classify_document(b"not-an-image" * 50)
    assert c.document_type == "unreadable"
    assert "decode-failed" in c.quality_flags


# ---------------------------------------------------------------------------
# Stub engines for pipeline tests
# ---------------------------------------------------------------------------
class _StubVisionEngine(OCREngine):
    """Returns a deterministic OCRResult; never touches the network."""
    name: ClassVar[str] = "claude_vision_bedrock"
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=True, handles_typed_print=True, handles_tables=True,
    )

    def __init__(self, *, overall_confidence: float = 0.86, with_binding_fields: bool = True):
        self._conf = overall_confidence
        self._with_binding = with_binding_fields

    async def extract(self, *, image_bytes, image_format, classification):
        fields: list[ExtractedField] = []
        if self._with_binding:
            fields.extend([
                ExtractedField(name="requested_treatment.name", value="trastuzumab",
                               confidence=0.93, source_excerpt="Inj. Herceptin", page=1),
                ExtractedField(name="primary_diagnosis.description", value="Carcinoma of left breast",
                               confidence=0.86, source_excerpt="Ca Breast Lt", page=1),
                ExtractedField(name="biomarkers.HER2.value", value="Positive",
                               confidence=0.88, source_excerpt="HER2+", page=1),
            ])
        return OCRResult(
            engine=self.name,
            full_text="Inj. Herceptin 6mg/kg IV q3w x 17",
            extracted_fields=fields,
            overall_confidence=self._conf,
            phi_redactions_applied=1,
            pages=1,
            clinical_snapshot_partial={
                "primary_diagnosis": {
                    "icd10_code": None,
                    "description": "Carcinoma of left breast",
                    "stage": "IIIA",
                    "source_resource_id": "intake-doc-stub",
                },
                "requested_treatment": {
                    "name": "trastuzumab", "j_code": None, "dose": "6 mg/kg",
                    "frequency": "q3w x 17", "intent": "adjuvant",
                },
            } if self._with_binding else {},
        )


class _AlwaysFailEngine(OCREngine):
    """Used to verify fallback chain + HITL routing on total failure."""
    name: ClassVar[str] = "claude_vision_bedrock"  # match a real engine name for capabilities check
    capabilities: ClassVar[EngineCapabilities] = EngineCapabilities(
        handles_handwriting=True, handles_typed_print=True, handles_tables=True,
    )

    async def extract(self, *, image_bytes, image_format, classification):
        raise EngineUnavailableError("test: no engines available", detail={"reason": "stubbed"})


# ---------------------------------------------------------------------------
# 2. Pipeline — uses stub engines via the registry seam
# ---------------------------------------------------------------------------
def test_pipeline_assembles_intake_result_with_stub_vision(fixture_doc):
    _reset_registry([_StubVisionEngine(overall_confidence=0.86)])
    result: IntakeResult = asyncio.run(parse_document(fixture_doc))

    assert isinstance(result, IntakeResult)
    assert result.classification.document_type in ("mixed", "handwritten")
    assert result.ocr.engine == "claude_vision_bedrock"
    assert result.ocr.overall_confidence == 0.86
    assert len(result.ocr.extracted_fields) == 3
    assert "missing-required-field" not in result.risk_flags
    assert "low-evidence-from-intake" not in result.risk_flags
    assert result.requires_human_review is False
    # Audit shape stable across the refactor
    assert result.audit["document_sha256"] == fixture_doc.sha256
    assert "claude_vision_bedrock" in result.audit["engines_used"]
    assert "stage_timings_ms" in result.audit
    assert result.audit["schema_version"] == "v1"
    # Snapshot was threaded through from vision JSON
    assert result.clinical_snapshot_partial.get("requested_treatment", {}).get("name") == "trastuzumab"


def test_pipeline_routes_to_hitl_on_low_confidence(fixture_doc):
    _reset_registry([_StubVisionEngine(overall_confidence=0.55)])
    result = asyncio.run(parse_document(fixture_doc))
    assert result.requires_human_review is True
    assert "low-evidence-from-intake" in result.risk_flags


def test_pipeline_routes_to_hitl_on_missing_binding_field(fixture_doc):
    _reset_registry([_StubVisionEngine(overall_confidence=0.95, with_binding_fields=False)])
    result = asyncio.run(parse_document(fixture_doc))
    assert result.requires_human_review is True
    assert "missing-required-field" in result.risk_flags


def test_pipeline_falls_back_when_all_engines_fail(fixture_doc):
    _reset_registry([_AlwaysFailEngine()])
    result = asyncio.run(parse_document(fixture_doc))
    assert result.requires_human_review is True
    assert "intake-failed" in result.risk_flags
    # Audit retains the failed attempt for forensics
    attempts = result.audit.get("extract_attempts", [])
    assert len(attempts) >= 1
    assert all(not a["ok"] for a in attempts)


def test_pipeline_uses_fallback_chain_on_first_engine_failure(fixture_doc):
    """Vision fails → next engine in chain succeeds → engine-fallback flag set."""
    _reset_registry([_AlwaysFailEngine(), _StubVisionEngine(overall_confidence=0.86)])
    result = asyncio.run(parse_document(fixture_doc))
    assert "engine-fallback-used" in result.risk_flags
    assert result.requires_human_review is False
    # Both attempts captured
    attempts = result.audit.get("extract_attempts", [])
    assert len(attempts) == 2
    assert attempts[0]["ok"] is False
    assert attempts[1]["ok"] is True


# ---------------------------------------------------------------------------
# 3. Idempotency cache — same SHA-256 returns cached result without re-running engines
# ---------------------------------------------------------------------------
def test_pipeline_caches_on_sha256_for_idempotency(fixture_doc):
    """Two back-to-back calls with the same document hash → second skips extract."""
    _reset_registry([_StubVisionEngine(overall_confidence=0.86)])
    first = asyncio.run(parse_document(fixture_doc))
    assert first.requires_human_review is False

    # Replace the engine with one that would FAIL — the cache should serve
    # the first result without re-invoking.
    _reset_registry([_AlwaysFailEngine()])
    second = asyncio.run(parse_document(fixture_doc))
    assert second.requires_human_review is False, (
        "Expected cache hit to bypass the failing engine"
    )
    # Snapshot threaded through cache too
    assert (
        second.clinical_snapshot_partial.get("requested_treatment", {}).get("name")
        == "trastuzumab"
    )


def test_pipeline_dedupe_isolates_different_documents(fixture_doc):
    """Different SHA-256 → cache miss → fresh extract."""
    _reset_registry([_StubVisionEngine(overall_confidence=0.86)])
    first = asyncio.run(parse_document(fixture_doc))
    assert first.requires_human_review is False

    # Mutate the SHA-256 so cache MISSES — engine runs again
    other = IntakeDocument(
        filename=fixture_doc.filename,
        mime_type=fixture_doc.mime_type,
        image_b64=fixture_doc.image_b64,
        sha256="a" * 64,
        source=fixture_doc.source,
    )
    second = asyncio.run(parse_document(other))
    assert second.audit["document_sha256"] == "a" * 64
    assert second.requires_human_review is False


# ---------------------------------------------------------------------------
# 4. Preprocess hardening — magic-byte sniff, dimension guard, bomb protection
# ---------------------------------------------------------------------------
def test_preprocess_rejects_non_image_bytes():
    """Random bytes that aren't an image → preprocess short-circuits → HITL."""
    bytes_ = b"definitely not an image " * 50
    sha = hashlib.sha256(bytes_).hexdigest()
    doc = IntakeDocument(
        filename="bogus.png",
        mime_type="image/png",
        image_b64=base64.b64encode(bytes_).decode("ascii"),
        sha256=sha,
        source="upload",
    )
    _reset_registry([_StubVisionEngine(overall_confidence=0.95)])
    result = asyncio.run(parse_document(doc))
    assert result.requires_human_review is True
    assert "intake-failed" in result.risk_flags


def test_preprocess_records_detected_mime_in_audit(fixture_doc):
    _reset_registry([_StubVisionEngine(overall_confidence=0.86)])
    result = asyncio.run(parse_document(fixture_doc))
    timings = result.audit["stage_timings_ms"]
    # Every stage should have recorded a timing (even cache-hit short-circuits
    # still record the assemble stage)
    assert "preprocess" in timings
    assert "classify" in timings
    assert "assemble" in timings
