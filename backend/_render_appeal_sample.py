"""Generate a sample appeal-letter PDF to visually verify the renderer.

Run with the project venv:
  D:\\xzashr.ai Files\\clincase-workspace\\ClinCase\\backend\\.venv\\Scripts\\python.exe _render_appeal_sample.py

Output: ops/aws/sample_appeal.pdf (kept out of the deploy artefact path; for review only).
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app.models.appeal import AppealArgument, AppealDraft  # noqa: E402
from app.render import render_appeal_pdf  # noqa: E402


def main() -> int:
    draft = AppealDraft(
        patient_initials="J.D.",
        payer_id="aetna",
        requested_treatment="trastuzumab (J9355)",
        denial_date="2026-05-04",
        appeal_body=(
            "This letter constitutes a formal appeal of your decision dated May 4, 2026 "
            "to deny coverage for trastuzumab (J9355) in this 57-year-old female patient "
            "with stage IIIA HER2-positive invasive ductal carcinoma of the right breast "
            "(ICD-10 C50.911). We respectfully request that your decision be overturned "
            "and that prior authorization be granted under Aetna CPB 0084 § II.B Initial "
            "Authorization Criteria.\n\n"
            "Clinical background: 57-year-old patient diagnosed August 2025 with HER2-"
            "positive (IHC 3+, FISH amplified ratio 6.4) stage IIIA invasive ductal "
            "carcinoma. The patient has completed standard adjuvant chemotherapy (AC-T "
            "regimen, four cycles, partial response on docetaxel) and is now eligible "
            "for HER2-targeted maintenance therapy. Baseline cardiac assessment shows "
            "LVEF 62% by transthoracic echocardiogram on April 15, 2026, well within the "
            "60-day window required by both the trastuzumab FDA label (§ 5.1) and Aetna "
            "policy. Performance status is ECOG 1.\n\n"
            "Argument summary: The denial appears to have been based on an absent "
            "documentation flag for HER2 confirmation testing, but pathology confirms "
            "HER2 IHC 3+ AND FISH amplification — both reflexively reported by Quest "
            "Diagnostics on September 5, 2025. We have attached the corresponding "
            "pathology report for the medical director's review.\n\n"
            "We respectfully request expedited reconsideration given the time-sensitivity "
            "of HER2-targeted adjuvant therapy initiation."
        ),
        structured_arguments=[
            AppealArgument(
                contested_criterion="HER2-positivity (Aetna CPB 0084 § II.B.1)",
                payer_position=(
                    "Denial cited insufficient documentation of HER2-positive status."
                ),
                counter_position=(
                    "HER2-positivity is unambiguously documented by both IHC (3+) and "
                    "reflex FISH (amplified, ratio 6.4) on the same specimen, satisfying "
                    "both ASCO/CAP 2018 testing guidelines and Aetna § II.B.1."
                ),
                cited_evidence=[
                    "HER2 IHC 3+ on Observation obs-her2 (test_date 2025-09-05)",
                    "HER2 FISH ratio 6.4 (amplified) on Observation obs-her2-fish (test_date 2025-09-05)",
                    "Quest Diagnostics pathology report dated 2025-09-05 (attachment 1)",
                ],
                cited_policy_text=(
                    "Coverage requires documented HER2-positivity by IHC 3+ OR ISH "
                    "amplified, per Aetna CPB 0084 v2024.3 (rev 2024-08) § II.B.1."
                ),
                cited_guideline=(
                    "NCCN Guidelines Breast Cancer v.4.2024 BINV-K — adjuvant trastuzumab "
                    "is standard of care for HER2-positive stage I-III breast cancer."
                ),
            ),
            AppealArgument(
                contested_criterion="Baseline LVEF assessment (Aetna § II.B.3)",
                payer_position=(
                    "(Inferred) Documentation of cardiac assessment may not have been "
                    "considered in the original review."
                ),
                counter_position=(
                    "Baseline transthoracic echocardiogram on April 15, 2026 documents "
                    "LVEF 62% — comfortably above the ≥ 50% threshold and well within "
                    "the 60-day pre-initiation window required by both the FDA label "
                    "and Aetna policy."
                ),
                cited_evidence=[
                    "LVEF 62% on Observation obs-lvef (test_date 2026-04-15)",
                    "Echocardiogram report (attachment 2)",
                ],
                cited_policy_text=(
                    "Baseline LVEF ≥ 50% by ECHO or MUGA within 60 days of initiation, "
                    "per Aetna CPB 0084 § II.B.3."
                ),
                cited_guideline=(
                    "Trastuzumab HCP § 5.1 Cardiomyopathy — baseline LVEF assessment "
                    "required prior to initiation; reassessment every 3 months on therapy."
                ),
            ),
        ],
        attachments_referenced=[
            "Quest Diagnostics pathology report dated 2025-09-05 (HER2 IHC + FISH)",
            "Echocardiogram report dated 2026-04-15 (LVEF 62%)",
            "AC-T treatment summary (cycles 1–4, completed 2026-01-15)",
            "ECOG performance status documentation dated 2026-04-20",
            "ASCO/CAP HER2 Testing Guideline 2018 (reference document)",
        ],
        requested_action=(
            "Overturn the denial and authorize trastuzumab (J9355) for adjuvant HER2-"
            "targeted therapy at standard dosing per the trastuzumab FDA label and "
            "NCCN BINV-K."
        ),
    )

    pdf_bytes = render_appeal_pdf(draft, case_id="case_8f4ad9c2")

    out = HERE.parent / "ops" / "aws" / "sample_appeal.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf_bytes)
    print(f"wrote {out}")
    print(f"size:  {len(pdf_bytes):,} bytes")
    print(f"magic: {pdf_bytes[:5]!r} (expect b'%PDF-')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
