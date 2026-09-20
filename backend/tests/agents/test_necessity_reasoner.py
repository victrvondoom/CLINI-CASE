"""Contract test for the Necessity Reasoner agent.

Bypasses trace_agent (no DB needed) - validates the LLM contract directly.
Targets the canonical demo case (HER2+ stage IIIA breast cancer, requesting
trastuzumab) against an Aetna trastuzumab policy excerpt.
"""
from __future__ import annotations

import pytest

from app.agents.necessity_reasoner import _PROMPT, _build_user_message, _strip_code_fence
from app.llm import get_llm_client
from app.models import (
    Biomarker,
    ClinicalSnapshot,
    Diagnosis,
    NecessityAssessment,
    PolicyExcerpt,
    RequestedTreatment,
)


@pytest.mark.asyncio
async def test_assesses_her2_trastuzumab_criteria():
    snapshot = ClinicalSnapshot(
        patient_age=53,
        patient_sex="female",
        primary_diagnosis=Diagnosis(
            icd10_code="C50.911",
            description="Malignant neoplasm of right female breast",
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
            "53-year-old female with newly diagnosed Stage IIIA invasive ductal carcinoma "
            "of the right breast. HER2-positive (IHC 3+), ER and PR negative. ECOG "
            "performance status 1. No prior systemic therapy. Treatment plan requesting "
            "trastuzumab in the neoadjuvant setting."
        ),
    )
    excerpt = PolicyExcerpt(
        payer_id="aetna",
        policy_id="0048",
        policy_title="Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
        section_heading="Initial Authorization Criteria",
        excerpt_text=(
            "Aetna considers trastuzumab medically necessary for the treatment of "
            "patients with HER2-positive breast cancer when ALL of the following are "
            "met: (1) Pathologic confirmation of HER2 overexpression (IHC 3+ or ISH "
            "amplified). (2) For early-stage (Stage I-III), given in adjuvant or "
            "neoadjuvant setting with chemotherapy. (3) Adequate baseline cardiac "
            "function defined as LVEF >= 50% by echocardiogram or MUGA within 90 "
            "days. (4) ECOG performance status 0, 1, or 2."
        ),
        relevance_score=1.0,
    )

    response = await get_llm_client().complete(
        system=_PROMPT,
        user=_build_user_message(snapshot, [excerpt]),
        max_tokens=3500,
        temperature=0.0,
    )
    assess = NecessityAssessment.model_validate_json(_strip_code_fence(response.text))

    assert len(assess.criteria) >= 3, (
        f"Expected at least 3 criteria, got {len(assess.criteria)}"
    )

    # HER2 should be MET (snapshot has IHC 3+)
    her2 = next(
        (c for c in assess.criteria if "her2" in c.criterion_text.lower()),
        None,
    )
    assert her2 is not None, "HER2 criterion missing from assessment"
    assert her2.status == "MET", f"HER2 should be MET, got {her2.status}"

    # LVEF should be AMBIGUOUS (snapshot has no LVEF data)
    lvef = next(
        (
            c
            for c in assess.criteria
            if "lvef" in c.criterion_text.lower() or "ejection" in c.criterion_text.lower()
        ),
        None,
    )
    assert lvef is not None, "LVEF criterion missing from assessment"
    assert lvef.status == "AMBIGUOUS", (
        f"LVEF should be AMBIGUOUS (no LVEF in snapshot), got {lvef.status}"
    )
    assert lvef.missing_evidence is not None

    # ECOG should be MET (snapshot has ECOG=1, in 0-2 range)
    ecog = next(
        (
            c
            for c in assess.criteria
            if "ecog" in c.criterion_text.lower() or "performance" in c.criterion_text.lower()
        ),
        None,
    )
    assert ecog is not None, "ECOG criterion missing from assessment"
    assert ecog.status == "MET", f"ECOG should be MET (ECOG=1), got {ecog.status}"

    # overall_confidence is the MIN — must be at most the AMBIGUOUS criterion's confidence
    assert 0.0 <= assess.overall_confidence <= 1.0
    assert assess.overall_confidence == min(c.confidence for c in assess.criteria)
