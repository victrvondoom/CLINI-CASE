"""Document Intake — convert raw images / scans / handwritten notes into a
structured ClinicalSnapshot.

Sits BEFORE the Clinical Extractor in the pipeline. Real-world prior-auth
inputs are messy (handwritten Rx slips, phone-camera scans of pathology
reports, faxed denial letters) — the Document Intake layer is what turns
that mess into the typed FHIR-equivalent payload the rest of the DAG
expects. Per AAOSA bounded responsibility, this layer ONLY produces a
ClinicalSnapshot — it never reasons about coverage.

CMS-0057-F § IV.A: every intake artifact is hashed (SHA-256), persisted
to `intake_documents`, and referenced by source_resource_id in any
downstream agent_runs row that consumes it. A scanned-fax verdict is as
auditable as a clean-FHIR verdict.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class IntakeDocument(BaseModel):
    """A single uploaded document — image bytes + provenance.

    `image_b64` is base64-encoded so the same Pydantic schema can travel over
    JSON APIs, persist to Postgres bytea, and feed Bedrock Converse content
    blocks without separate field surgery.
    """

    filename: str
    mime_type: Literal[
        "image/png",
        "image/jpeg",
        "image/webp",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
    ]
    image_b64: str = Field(..., description="Base64-encoded raw bytes of the document")
    sha256: str = Field(..., description="Hex digest of the raw bytes — audit ledger anchor")
    source: Literal["upload", "fax-inbox", "fhir-attachment", "phone-camera"] = "upload"


# ---------------------------------------------------------------------------
# Sub-agent outputs
# ---------------------------------------------------------------------------
class DocumentClassification(BaseModel):
    """Output of the intake_classifier sub-agent.

    Drives downstream routing: typed → Textract path (cheap), handwritten →
    Vision path (Claude Sonnet 4.6 via Bedrock), mixed → both with reconcile.
    """

    document_type: Literal[
        "typed_print",        # Word/PDF-generated, scanned at high DPI
        "handwritten",        # pen-on-paper, photographed
        "mixed",              # typed letterhead + handwritten margins / Rx pad
        "structured_form",    # PA form / checkbox-heavy intake form
        "unreadable",         # severe blur / tilt / low resolution
    ]
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., description="One sentence why")
    quality_flags: list[str] = Field(
        default_factory=list,
        description="e.g. ['low-resolution', 'skewed', 'phone-camera-glare', 'multi-page']",
    )


class ExtractedField(BaseModel):
    """One structured field pulled from the document with per-field confidence."""

    name: str = Field(..., description="e.g. 'requested_treatment.name', 'biomarkers.HER2.value'")
    value: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_excerpt: str = Field(..., description="The verbatim text/region this came from")
    page: int = Field(default=1, ge=1)


class OCRResult(BaseModel):
    """Output of either the textract_extractor or vision_extractor sub-agent.

    Both adapters produce this shape so downstream consumers don't care which
    OCR strategy was used. `engine` is preserved for audit + cost analysis.

    `clinical_snapshot_partial` is populated by engines that derive structured
    snapshot fields in the same call as the OCR (Claude vision); engines that
    only do OCR (Textract, Tesseract) leave it empty and the FHIR shaper
    derives fields from `full_text` downstream.
    """

    engine: Literal[
        "aws_textract",
        "claude_vision_bedrock",
        "tesseract_local",
        "pypdf_text",
        "python_docx",
        "plain_text",
    ]
    full_text: str
    extracted_fields: list[ExtractedField]
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    phi_redactions_applied: int = Field(default=0, ge=0)
    pages: int = Field(default=1, ge=1)
    clinical_snapshot_partial: dict = Field(
        default_factory=dict,
        description=(
            "Partial ClinicalSnapshot extracted by vision-LLM engines in the "
            "same call as OCR. Empty for OCR-only engines (Textract, Tesseract)."
        ),
    )


# ---------------------------------------------------------------------------
# Top-level result returned by the API
# ---------------------------------------------------------------------------
class IntakeResult(BaseModel):
    """End-to-end intake output — the union of everything downstream needs.

    The `clinical_snapshot_partial` is intentionally a dict (not the full
    ClinicalSnapshot Pydantic) so this model can be returned even when the
    document has only a few fields. The case-creation flow merges this with
    any FHIR bundle / physician note that came alongside the upload.
    """

    classification: DocumentClassification
    ocr: OCRResult
    clinical_snapshot_partial: dict
    risk_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Routes propagated to downstream agents. Sub-0.7 confidence on a "
            "biomarker or drug name auto-adds 'low-evidence-from-intake'."
        ),
    )
    requires_human_review: bool = Field(
        default=False,
        description=(
            "True when overall_confidence < 0.7 OR a binding field "
            "(requested_treatment, primary_diagnosis) is missing. The case "
            "router uses this to short-circuit straight to the Reviewer queue."
        ),
    )
    audit: dict = Field(
        default_factory=dict,
        description=(
            "{document_sha256, engines_used, latency_ms, cost_usd}. Persisted "
            "verbatim into agent_runs for CMS-0057-F § IV.A reconstructibility."
        ),
    )
