"""Contract test for app.render.appeal_pdf.render_appeal_pdf.

Verifies the renderer produces:
  - Valid PDF bytes (PDF magic header)
  - A reasonable size (4-200 KB for a typical appeal)
  - At least one page, parseable by pypdf
  - Critical text fields embedded in the document (patient initials,
    payer, treatment, audit reference) so a payer reviewing it sees
    exactly what the structured AppealDraft promised

This test is purely local — no DB, no LLM, no network. Runs in <2s.
"""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

from app.models.appeal import AppealArgument, AppealDraft
from app.render import render_appeal_pdf


def _sample_draft() -> AppealDraft:
    return AppealDraft(
        patient_initials="J.D.",
        payer_id="aetna",
        requested_treatment="trastuzumab (J9355)",
        denial_date="2026-05-04",
        appeal_body=(
            "This letter constitutes a formal appeal of the denial dated "
            "May 4, 2026 for trastuzumab in this 57-year-old female patient "
            "with stage IIIA HER2-positive breast cancer.\n\n"
            "We respectfully request reconsideration."
        ),
        structured_arguments=[
            AppealArgument(
                contested_criterion="HER2-positivity (Aetna § II.B.1)",
                payer_position="Insufficient documentation of HER2-positive status.",
                counter_position="HER2 IHC 3+ + FISH amplified ratio 6.4 documented.",
                cited_evidence=["HER2 IHC 3+ on obs-her2"],
                cited_policy_text="HER2-positive (IHC 3+ or ISH amplified) required.",
                cited_guideline="NCCN Breast Cancer v.4.2024 BINV-K",
            ),
        ],
        attachments_referenced=["Pathology report 2025-09-05"],
        requested_action="Overturn the denial and authorise trastuzumab.",
    )


def test_render_appeal_pdf_returns_valid_pdf_bytes():
    pdf = render_appeal_pdf(_sample_draft())
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-"), "should start with PDF magic header"
    # %%EOF marker must terminate a well-formed PDF
    assert b"%%EOF" in pdf[-2048:], "should end with %%EOF marker"


def test_render_appeal_pdf_size_is_reasonable():
    pdf = render_appeal_pdf(_sample_draft())
    # Empty schema would still produce a few KB of letterhead + boilerplate;
    # a real letter is typically 7-50 KB. Cap at 200 KB to flag template bloat.
    assert 4_000 < len(pdf) < 200_000, f"unexpected pdf size: {len(pdf)} bytes"


def test_render_appeal_pdf_has_pages():
    pdf = render_appeal_pdf(_sample_draft())
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 1
    # 2-arg appeal letter should fit in 1-3 pages — guard against runaway layout
    assert len(reader.pages) <= 5


def test_render_appeal_pdf_contains_payer_grade_fields():
    """Critical fields the payer's medical director will look for."""
    pdf = render_appeal_pdf(_sample_draft(), case_id="case_8f4ad9c2")
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(p.extract_text() for p in reader.pages)
    # Patient identifier (initials, not full name — PHI discipline)
    assert "J.D." in text
    # Treatment + code
    assert "trastuzumab" in text.lower()
    assert "J9355" in text
    # Payer identification
    assert "AETNA" in text or "Aetna" in text
    # Audit anchor — CMS-0057-F § IV.A reference + case_id
    assert "CMS-0057-F" in text
    assert "case_8f4ad9c2" in text


def test_unreviewed_appeal_is_labeled_on_every_page():
    draft = _sample_draft()
    draft.appeal_body = "\n\n".join([draft.appeal_body] * 12)
    reader = PdfReader(io.BytesIO(render_appeal_pdf(draft, requires_review=True)))
    assert len(reader.pages) > 1
    for page in reader.pages:
        assert "DRAFT - clinician review required before use" in page.extract_text()


def test_preview_endpoint_always_labels_unverified_document_as_draft():
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).post("/api/v1/appeals/render.pdf", json=_sample_draft().model_dump())
    assert response.status_code == 200
    assert response.headers["X-ClinCase-Document-Status"] == "draft"
    reader = PdfReader(io.BytesIO(response.content))
    assert "DRAFT - clinician review required" in reader.pages[0].extract_text()


@pytest.mark.parametrize("scenario", ["pending", "stale_appeal", "other_tenant", "current"])
async def test_case_pdf_uses_owned_current_run_and_preserves_draft_label(monkeypatch, scenario):
    from datetime import UTC, datetime

    from fastapi import HTTPException

    from app.api.appeals import render_case_appeal_pdf
    from app.db import db

    class Connection:
        async def fetchrow(self, sql, *args):
            if "FROM cases WHERE" in sql:
                assert args == ("case-pdf", "org-owner")
                if scenario == "other_tenant":
                    return None
                return {
                    "id": "case-pdf",
                    "payer_id": "aetna",
                    "patient_initials": "J.D.",
                    "requested_treatment_name": "trastuzumab",
                    "created_at": datetime.now(UTC),
                    "status": "awaiting_review" if scenario == "pending" else "denied",
                }
            if "FROM case_runs" in sql:
                return {
                    "run_id": "newest-run",
                    "status": "paused" if scenario == "pending" else "completed",
                }
            if "FROM case_run_states" in sql:
                assert args == ("newest-run",)
                return {
                    "pause_kind": "ai_denial",
                    "pause_reason": "Review required",
                    "schema_version": 1,
                    "state_json": {"draft_outputs": {"appeal_draft": _sample_draft().model_dump()}},
                }
            assert "run_id IS NOT DISTINCT FROM $2" in sql
            assert args == ("case-pdf", "newest-run")
            if scenario == "stale_appeal":
                return None
            return {
                "appeal_body": _sample_draft().appeal_body,
                "structured_arguments_json": [],
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    class Pool:
        def acquire(self):
            return Connection()

    monkeypatch.setattr(db, "_pool", Pool())
    if scenario in {"other_tenant", "stale_appeal"}:
        with pytest.raises(HTTPException) as caught:
            await render_case_appeal_pdf("case-pdf", {"organization_id": "org-owner"})
        assert caught.value.status_code == 404
    else:
        response = await render_case_appeal_pdf("case-pdf", {"organization_id": "org-owner"})
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.body)).pages)
        assert ("DRAFT - clinician review required" in text) == (scenario == "pending")
        assert response.headers["X-ClinCase-Document-Status"] == (
            "draft" if scenario == "pending" else "case-record"
        )


def test_render_appeal_pdf_with_unknown_payer():
    """Unknown payer_id should NOT crash — uses generic fallback block."""
    draft = _sample_draft()
    object.__setattr__(draft, "payer_id", "obscure-payer-xyz")
    pdf = render_appeal_pdf(draft)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "OBSCURE-PAYER-XYZ" in text or "obscure-payer-xyz" in text.lower()


def test_render_appeal_pdf_escapes_xml_special_chars():
    """An agent might emit '<', '>', '&' inside body text. Renderer must
    escape them or ReportLab Paragraph throws."""
    draft = _sample_draft()
    object.__setattr__(
        draft,
        "appeal_body",
        "The criterion <Aetna § II.B.1> requires HER2 IHC 3+ AND FISH "
        "amplified > 2.0. Patient's value > threshold — fully met.",
    )
    pdf = render_appeal_pdf(draft)  # must not raise
    assert pdf.startswith(b"%PDF-")


@pytest.mark.parametrize("payer_id", ["aetna", "uhc", "humana"])
def test_render_appeal_pdf_per_payer(payer_id: str):
    draft = _sample_draft()
    object.__setattr__(draft, "payer_id", payer_id)
    pdf = render_appeal_pdf(draft)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 4_000
