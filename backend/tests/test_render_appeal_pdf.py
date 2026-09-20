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
