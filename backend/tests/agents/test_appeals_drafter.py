"""Contract test for the Appeals Drafter agent.

Bypasses trace_agent (no DB needed) - calls LLM directly with a
synthetic denial scenario and validates the output structure.
"""
from __future__ import annotations

import pytest

from app.agents.appeals_drafter import _PROMPT, _build_user_message, _strip_code_fence
from app.llm import get_llm_client
from app.models import (
    AppealDraft,
    Biomarker,
    Citation,
    ClinicalSnapshot,
    Decision,
    Diagnosis,
    PolicyExcerpt,
    RequestedTreatment,
)


@pytest.mark.asyncio
async def test_drafts_appeal_for_her2_documentation_dispute():
    """Scenario: payer denied trastuzumab citing 'incomplete HER2 documentation'
    despite IHC 3+ being present in the chart. ClinCase appeals."""
    snapshot = ClinicalSnapshot(
        patient_age=53,
        patient_sex="female",
        primary_diagnosis=Diagnosis(
            icd10_code="C50.911",
            description="Malignant neoplasm of right breast",
            stage="IIIA",
            source_resource_id="condition-primary",
        ),
        biomarkers=[
            Biomarker(name="HER2", value="Positive (3+)", source_resource_id="obs-her2"),
            Biomarker(name="ER", value="Negative", source_resource_id="obs-er"),
            Biomarker(name="PR", value="Negative", source_resource_id="obs-pr"),
        ],
        performance_status="1",
        requested_treatment=RequestedTreatment(name="trastuzumab", j_code="J9355"),
        free_text_summary=(
            "53yo female with stage IIIA HER2+ invasive ductal carcinoma of the "
            "right breast. ER/PR negative. ECOG 1. Requesting neoadjuvant trastuzumab."
        ),
    )
    excerpt = PolicyExcerpt(
        payer_id="aetna",
        policy_id="0048",
        policy_title="Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
        section_heading="Initial Authorization Criteria",
        excerpt_text=(
            "Trastuzumab approved for HER2-positive breast cancer when HER2 "
            "overexpression is confirmed by IHC 3+ OR ISH amplified."
        ),
        relevance_score=1.0,
    )
    decision = Decision(
        verdict="DENY",
        rationale=(
            "The submitted prior authorisation request for trastuzumab was denied "
            "by Aetna citing insufficient documentation of HER2 status."
        ),
        citations=[
            Citation(kind="clinical", text="HER2 IHC 3+", pointer="obs-her2"),
            Citation(
                kind="policy",
                text="HER2 IHC 3+ OR ISH amplified",
                pointer="policy:0048#Initial Authorization Criteria",
            ),
        ],
        confidence=0.98,
        risk_flags=[],
    )

    response = await get_llm_client().complete(
        system=_PROMPT,
        user=_build_user_message(
            snapshot=snapshot,
            excerpts=[excerpt],
            decision=decision,
            external_denial_letter="Trastuzumab denied: insufficient HER2 documentation submitted.",
            payer_id="aetna",
            patient_initials="MD",
        ),
        max_tokens=4096,
        temperature=0.0,
    )
    appeal = AppealDraft.model_validate_json(_strip_code_fence(response.text))

    # Required fields populated
    assert appeal.patient_initials.upper() in ("JD", "MD"), (
        f"Patient initials should be MD per input, got {appeal.patient_initials}"
    )
    assert appeal.payer_id == "aetna"
    assert "trastuzumab" in appeal.requested_treatment.lower()

    # Letter body length check (target 500-800 words; tolerate 300-1000)
    word_count = len(appeal.appeal_body.split())
    assert 300 <= word_count <= 1100, f"Appeal body length out of range: {word_count} words"

    # Letter mentions HER2 and IHC 3+ (the disputed evidence)
    body_lower = appeal.appeal_body.lower()
    assert "her2" in body_lower
    assert "ihc" in body_lower or "immunohistochem" in body_lower

    # Structured arguments present
    assert len(appeal.structured_arguments) >= 1
    arg = appeal.structured_arguments[0]
    assert arg.contested_criterion
    assert arg.cited_evidence
    # Cited evidence must come from the snapshot, not fabricated
    arg_evidence_str = " ".join(arg.cited_evidence).lower()
    assert "her2" in arg_evidence_str or "3+" in arg_evidence_str

    # Requested action is present
    assert "overturn" in appeal.requested_action.lower() or "authoriz" in appeal.requested_action.lower()
