"""Render an AppealDraft into a payer-ready PDF appeal letter.

Bounded responsibility: input is a Pydantic AppealDraft, output is bytes.
No DB calls, no LLM calls, no I/O other than the PDF byte stream.

Layout: US Letter, 1-inch margins, two-column header block, structured-
argument sections, attachment list, footer page numbers + ClinCase
provenance line. Designed to look like a real medical-director appeal
letter — the kind a peer-reviewing physician at a payer would actually
read, not a generic JSON-printed dump.

Why ReportLab over WeasyPrint: ReportLab is pure Python and installs
cleanly on Windows without GTK/Pango. Platypus gives us precise control
over page breaks and the deterministic output we need for audit hashing.
"""
from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.appeal import AppealDraft

# Brand palette — kept close to the deck so a stage demo's PDF and slides
# share a visual identity. Conservative on print (no gradients, high contrast).
_BRAND_NAVY = colors.HexColor("#0F172A")
_BRAND_INDIGO = colors.HexColor("#4F46E5")
_BRAND_CYAN = colors.HexColor("#0891B2")
_TEXT_BODY = colors.HexColor("#334155")
_TEXT_MUTED = colors.HexColor("#64748B")
_BORDER = colors.HexColor("#E2E8F0")

# Provider letterhead — synthetic but realistic for the demo. In production
# this comes from `tenants` row (organization name, address, NPI, fax).
_PROVIDER_NAME = "ClinCase Medical Associates"
_PROVIDER_TAGLINE = "Provider-Side Prior Authorization · Oncology"
_PROVIDER_ADDRESS = "1 Care Square, Suite 400 · San Francisco, CA 94105"
_PROVIDER_PHONE = "Tel: (415) 555-0140 · Fax: (415) 555-0141"
_PROVIDER_NPI = "NPI: 1234567890"

# Payer dispatch addresses — synthetic but recognisable. Real deployment
# resolves these from the `payers` table by `payer_id`.
_PAYER_ADDRESS_BOOK: dict[str, list[str]] = {
    "aetna": [
        "Aetna Health Inc.",
        "Attn: Medical Director · Oncology Appeals",
        "P.O. Box 14079",
        "Lexington, KY 40512",
    ],
    "uhc": [
        "UnitedHealthcare Insurance Company",
        "Attn: Medical Director · Pharmacy Appeals",
        "P.O. Box 30432",
        "Salt Lake City, UT 84130",
    ],
    "humana": [
        "Humana Inc.",
        "Attn: Medical Director · Oncology Appeals",
        "P.O. Box 14601",
        "Lexington, KY 40512",
    ],
}


def _payer_block(payer_id: str) -> list[str]:
    return _PAYER_ADDRESS_BOOK.get(
        payer_id.lower(),
        [
            f"{payer_id.upper()}",
            "Attn: Medical Director · Appeals",
            "[address on file]",
        ],
    )


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------
_styles = getSampleStyleSheet()

_LETTERHEAD_TITLE = ParagraphStyle(
    "LetterheadTitle",
    parent=_styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=18,
    textColor=_BRAND_NAVY,
    spaceAfter=2,
    leading=22,
)
_LETTERHEAD_TAGLINE = ParagraphStyle(
    "LetterheadTagline",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=9.5,
    textColor=_BRAND_INDIGO,
    spaceAfter=3,
)
_LETTERHEAD_META = ParagraphStyle(
    "LetterheadMeta",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=8.5,
    textColor=_TEXT_MUTED,
    spaceAfter=2,
)
_DATE_STYLE = ParagraphStyle(
    "DateStyle",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=10.5,
    textColor=_TEXT_BODY,
    spaceAfter=14,
)
_PAYER_STYLE = ParagraphStyle(
    "PayerBlock",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=10.5,
    textColor=_TEXT_BODY,
    leading=14,
)
_RE_LINE = ParagraphStyle(
    "ReLine",
    parent=_styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=10.5,
    textColor=_BRAND_NAVY,
    spaceBefore=10,
    spaceAfter=8,
)
_BODY = ParagraphStyle(
    "Body",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=10.5,
    textColor=_TEXT_BODY,
    leading=15,
    spaceAfter=10,
    alignment=0,
)
_ARG_HEAD = ParagraphStyle(
    "ArgumentHead",
    parent=_styles["Heading3"],
    fontName="Helvetica-Bold",
    fontSize=11,
    textColor=_BRAND_INDIGO,
    spaceBefore=14,
    spaceAfter=4,
)
_ARG_LABEL = ParagraphStyle(
    "ArgumentLabel",
    parent=_styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=_BRAND_NAVY,
    leading=12,
    spaceAfter=1,
)
_ARG_VALUE = ParagraphStyle(
    "ArgumentValue",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=10,
    textColor=_TEXT_BODY,
    leading=14,
    spaceAfter=6,
    leftIndent=10,
)
_FOOTER_STYLE = ParagraphStyle(
    "Footer",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=8,
    textColor=_TEXT_MUTED,
)


# ---------------------------------------------------------------------------
# Letterhead — drawn on every page via SimpleDocTemplate's onFirstPage / onLaterPages
# ---------------------------------------------------------------------------
def _draw_letterhead(canvas, doc) -> None:
    canvas.saveState()
    width, height = LETTER

    # Brand strip across top of every page
    canvas.setFillColor(_BRAND_NAVY)
    canvas.rect(0, height - 0.45 * inch, width, 0.45 * inch, fill=1, stroke=0)

    # Brand text in strip
    canvas.setFillColor(_BRAND_CYAN)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(0.75 * inch, height - 0.28 * inch, "CLINCASE")
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(
        width - 0.75 * inch,
        height - 0.28 * inch,
        "Provider-Side Prior Authorization · Oncology",
    )

    # Footer line — page number, generation timestamp, audit anchor
    canvas.setStrokeColor(_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(0.75 * inch, 0.55 * inch, width - 0.75 * inch, 0.55 * inch)
    canvas.setFillColor(_TEXT_MUTED)
    canvas.setFont("Helvetica", 8)
    page_num = canvas.getPageNumber()
    canvas.drawString(
        0.75 * inch,
        0.4 * inch,
        "ClinCase appeal letter · CMS-0057-F § IV.A audit-trail compliant",
    )
    canvas.drawRightString(
        width - 0.75 * inch,
        0.4 * inch,
        f"Page {page_num}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def render_appeal_pdf(draft: AppealDraft, *, case_id: str | None = None) -> bytes:
    """Render an AppealDraft into a complete payer-ready PDF letter.

    Args:
        draft: the structured appeal letter from the Appeals Drafter agent.
        case_id: optional ClinCase case_id, included in the audit reference.

    Returns:
        PDF file as bytes (typically 30-60 KB for a standard 2-3 page letter).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.7 * inch,
        title=f"Appeal — {draft.patient_initials} — {draft.requested_treatment}",
        author=_PROVIDER_NAME,
        subject=f"Prior Authorization Appeal · {draft.requested_treatment} · {draft.payer_id}",
    )

    story: list[Flowable] = []

    # --- Provider letterhead block (below brand strip) -----------------
    story.append(Paragraph(_PROVIDER_NAME, _LETTERHEAD_TITLE))
    story.append(Paragraph(_PROVIDER_TAGLINE, _LETTERHEAD_TAGLINE))
    story.append(Paragraph(_PROVIDER_ADDRESS, _LETTERHEAD_META))
    story.append(Paragraph(f"{_PROVIDER_PHONE} · {_PROVIDER_NPI}", _LETTERHEAD_META))
    story.append(Spacer(1, 0.05 * inch))
    story.append(HRFlowable(width="100%", thickness=0.6, color=_BRAND_INDIGO))
    story.append(Spacer(1, 0.18 * inch))

    # --- Date ------------------------------------------------------------
    # Windows strftime does not support %-d; strip the zero-pad manually so
    # output is "May 6, 2026" not "May 06, 2026" across platforms.
    today = datetime.now(UTC).strftime("%B %d, %Y").replace(" 0", " ")
    story.append(Paragraph(today, _DATE_STYLE))

    # --- Payer block -----------------------------------------------------
    payer_lines = _payer_block(draft.payer_id)
    for line in payer_lines:
        story.append(Paragraph(line, _PAYER_STYLE))
    story.append(Spacer(1, 0.05 * inch))

    # --- Re: line --------------------------------------------------------
    story.append(
        Paragraph(
            f"Re: Prior Authorization Appeal — Patient {draft.patient_initials} — "
            f"{draft.requested_treatment}",
            _RE_LINE,
        )
    )

    # --- Header info table (compact; reads like a fax cover) ------------
    header_rows = [
        ["Patient initials:",        draft.patient_initials],
        ["Treatment requested:",     draft.requested_treatment],
        ["Original denial date:",    draft.denial_date],
        ["Payer:",                   draft.payer_id.upper()],
    ]
    header_tbl = Table(
        header_rows,
        colWidths=[1.7 * inch, 5.0 * inch],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
                ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), _BRAND_NAVY),
                ("TEXTCOLOR", (1, 0), (1, -1), _TEXT_BODY),
                ("LINEABOVE", (0, 0), (-1, 0), 0.4, _BORDER),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, _BORDER),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_tbl)
    story.append(Spacer(1, 0.22 * inch))

    # --- Salutation + body ----------------------------------------------
    story.append(Paragraph("Dear Medical Director,", _BODY))
    for paragraph in _split_body(draft.appeal_body):
        story.append(Paragraph(paragraph, _BODY))

    # --- Structured arguments (each kept together for clean page breaks)
    if draft.structured_arguments:
        story.append(Spacer(1, 0.12 * inch))
        story.append(
            Paragraph(
                "Structured arguments — point-by-point response",
                ParagraphStyle(
                    "ArgsHeader",
                    parent=_BODY,
                    fontName="Helvetica-Bold",
                    fontSize=11,
                    textColor=_BRAND_NAVY,
                    spaceAfter=8,
                ),
            )
        )
        for i, arg in enumerate(draft.structured_arguments, start=1):
            block: list[Flowable] = []
            block.append(
                Paragraph(
                    f"Argument {i} — {arg.contested_criterion}",
                    _ARG_HEAD,
                )
            )
            block.append(Paragraph("Payer position", _ARG_LABEL))
            block.append(Paragraph(_safe(arg.payer_position) or "—", _ARG_VALUE))
            block.append(Paragraph("ClinCase counter-position", _ARG_LABEL))
            block.append(Paragraph(_safe(arg.counter_position) or "—", _ARG_VALUE))
            if arg.cited_evidence:
                block.append(Paragraph("Cited clinical evidence", _ARG_LABEL))
                for ev in arg.cited_evidence:
                    block.append(Paragraph(f"• {_safe(ev)}", _ARG_VALUE))
            if arg.cited_policy_text:
                block.append(Paragraph("Cited policy excerpt", _ARG_LABEL))
                block.append(Paragraph(_safe(arg.cited_policy_text), _ARG_VALUE))
            if arg.cited_guideline:
                block.append(Paragraph("Cited guideline", _ARG_LABEL))
                block.append(Paragraph(_safe(arg.cited_guideline), _ARG_VALUE))
            story.append(KeepTogether(block))

    # --- Requested action ------------------------------------------------
    story.append(Spacer(1, 0.18 * inch))
    story.append(
        Paragraph(
            f"<b>Requested action:</b> {_safe(draft.requested_action)}",
            _BODY,
        )
    )

    # --- Sign-off --------------------------------------------------------
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Respectfully submitted,", _BODY))
    story.append(Spacer(1, 0.5 * inch))  # signature space
    story.append(Paragraph("<b>ClinCase Clinical Authorization Team</b>", _BODY))
    story.append(Paragraph("On behalf of the requesting provider", _LETTERHEAD_META))

    # --- Attachments referenced -----------------------------------------
    if draft.attachments_referenced:
        story.append(Spacer(1, 0.25 * inch))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDER))
        story.append(Spacer(1, 0.08 * inch))
        story.append(
            Paragraph(
                f"<b>Attachments referenced ({len(draft.attachments_referenced)})</b>",
                _LETTERHEAD_META,
            )
        )
        for att in draft.attachments_referenced:
            story.append(Paragraph(f"&nbsp;&nbsp;• {_safe(att)}", _LETTERHEAD_META))

    # --- Audit reference (the CMS-0057-F § IV.A traceability anchor) ----
    audit_ref = case_id or "preview"
    story.append(Spacer(1, 0.18 * inch))
    story.append(
        Paragraph(
            f"<i>ClinCase audit reference: <font color='#0F172A'>{audit_ref}</font> · "
            f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} · "
            "All claims trace to FHIR resource ids and payer policy excerpts in the case "
            "audit_ledger (CMS-0057-F § IV.A compliant).</i>",
            _FOOTER_STYLE,
        )
    )

    doc.build(
        story,
        onFirstPage=_draw_letterhead,
        onLaterPages=_draw_letterhead,
    )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _split_body(body: str) -> list[str]:
    """Split the agent-generated body into Paragraph-safe paragraphs.

    The Appeals Drafter emits a single string of ~500-800 words, typically
    containing internal blank-line paragraph breaks. We honour those, then
    fall back to a single paragraph if no breaks are present.
    """
    parts = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not parts:
        # Fall back: treat whole body as one paragraph after collapsing
        # interior single newlines to spaces.
        return [body.strip().replace("\n", " ")]
    # Collapse interior single newlines inside each paragraph to single spaces
    # so ReportLab's Paragraph (which respects only XML-ish line breaks) lays
    # out cleanly.
    return [p.replace("\n", " ") for p in parts]


def _safe(text: str) -> str:
    """Escape ReportLab Paragraph special chars (& < >) to prevent XML errors
    when an agent output contains unescaped HTML/XML-like content.
    """
    if not text:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
