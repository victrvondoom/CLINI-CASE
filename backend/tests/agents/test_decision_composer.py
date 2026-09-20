"""Contract tests for the Decision Composer agent.

Tests the deterministic verdict rule directly (no LLM needed) plus one
LLM contract test that exercises the full citation chain output.
"""
from __future__ import annotations

import pytest

from app.agents.decision_composer import (
    _PROMPT,
    _build_user_message,
    _strip_code_fence,
    derive_verdict,
)
from app.llm import get_llm_client
from app.models import (
    Biomarker,
    ClinicalSnapshot,
    CriterionAssessment,
    Decision,
    Diagnosis,
    NecessityAssessment,
    PolicyExcerpt,
    RequestedTreatment,
)

# ============================================================================
# Deterministic verdict rule (pure unit tests, no LLM)
# ============================================================================


def _crit(
    text: str,
    status: str = "MET",
    ctype: str = "inclusion",
    conf: float = 0.95,
) -> CriterionAssessment:
    return CriterionAssessment(
        criterion_text=text,
        criterion_type=ctype,
        policy_excerpt_index=0,
        status=status,
        supporting_evidence=["evidence"],
        missing_evidence=None if status != "AMBIGUOUS" else "needed",
        confidence=conf,
        rationale="r",
    )


def _na(criteria: list[CriterionAssessment], conf: float | None = None) -> NecessityAssessment:
    return NecessityAssessment(
        criteria=criteria,
        overall_confidence=conf if conf is not None else min(c.confidence for c in criteria),
        summary="s",
    )


def test_verdict_approve_when_all_inclusions_met_high_confidence():
    a = _na([_crit("HER2+", "MET"), _crit("ECOG 0-2", "MET")])
    assert derive_verdict(a) == "APPROVE"


def test_verdict_deny_when_inclusion_not_met():
    a = _na([_crit("HER2+", "NOT_MET", "inclusion"), _crit("ECOG 0-2", "MET")])
    assert derive_verdict(a) == "DENY"


def test_verdict_deny_when_exclusion_applies():
    a = _na([
        _crit("HER2+", "MET", "inclusion"),
        _crit("Active ILD", "MET", "exclusion"),
    ])
    assert derive_verdict(a) == "DENY"


def test_verdict_refer_on_ambiguous():
    a = _na([_crit("HER2+", "MET"), _crit("LVEF >= 50%", "AMBIGUOUS", "inclusion", 0.50)])
    assert derive_verdict(a) == "REFER"


def test_verdict_refer_on_low_confidence():
    a = _na([_crit("HER2+", "MET", "inclusion", 0.60)], conf=0.60)
    assert derive_verdict(a) == "REFER"


def test_verdict_approve_when_exclusion_not_applies():
    """An exclusion criterion that's NOT_MET means it doesn't apply - good."""
    a = _na([
        _crit("HER2+", "MET", "inclusion"),
        _crit("Active ILD", "NOT_MET", "exclusion"),
    ])
    assert derive_verdict(a) == "APPROVE"


# ============================================================================
# LLM contract test - full citation chain
# ============================================================================


@pytest.mark.asyncio
async def test_composer_produces_citation_chain_for_approve():
    snapshot = ClinicalSnapshot(
        patient_age=53,
        patient_sex="female",
        primary_diagnosis=Diagnosis(
            icd10_code="C50.911",
            description="Stage IIIA breast cancer",
            stage="IIIA",
            source_resource_id="condition-primary",
        ),
        biomarkers=[
            Biomarker(name="HER2", value="Positive (3+)", source_resource_id="obs-her2"),
        ],
        performance_status="1",
        requested_treatment=RequestedTreatment(name="trastuzumab", j_code="J9355"),
        free_text_summary="Stage IIIA HER2+ breast cancer, ECOG 1, requesting trastuzumab.",
    )
    excerpt = PolicyExcerpt(
        payer_id="aetna",
        policy_id="0048",
        policy_title="Trastuzumab",
        section_heading="Initial Authorization Criteria",
        excerpt_text="Trastuzumab approved when HER2 IHC 3+ AND ECOG 0-2.",
        relevance_score=1.0,
    )
    assessment = NecessityAssessment(
        criteria=[
            CriterionAssessment(
                criterion_text="HER2 IHC 3+ confirmed",
                criterion_type="inclusion",
                policy_excerpt_index=0,
                status="MET",
                supporting_evidence=["HER2 Positive (3+)"],
                confidence=0.98,
                rationale="HER2 IHC 3+ in obs-her2",
            ),
            CriterionAssessment(
                criterion_text="ECOG 0-2",
                criterion_type="inclusion",
                policy_excerpt_index=0,
                status="MET",
                supporting_evidence=["ECOG 1"],
                confidence=0.98,
                rationale="ECOG=1 documented",
            ),
        ],
        overall_confidence=0.98,
        summary="All criteria met.",
    )
    verdict = derive_verdict(assessment)
    assert verdict == "APPROVE"

    response = await get_llm_client().complete(
        system=_PROMPT,
        user=_build_user_message(verdict, snapshot, [excerpt], assessment),
        max_tokens=2000,
        temperature=0.0,
    )
    decision = Decision.model_validate_json(_strip_code_fence(response.text))

    assert decision.verdict == "APPROVE"
    assert len(decision.rationale.split(".")) >= 3, "rationale should be 3-5 sentences"
    assert len(decision.citations) >= 2, "expected >=2 citations (clinical + policy)"

    kinds = {c.kind for c in decision.citations}
    assert "clinical" in kinds, "missing clinical citation"
    assert "policy" in kinds, "missing policy citation"

    # Confidence wired through from the assessment
    assert decision.confidence == pytest.approx(0.98, abs=0.01)
