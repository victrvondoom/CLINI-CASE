"""Contract test for the Denial Forecaster agent.

Bypasses trace_agent / DB — calls the probability_estimator sub-agent's LLM
contract directly. Validates that for a high-risk DENY case, the agent
returns a valid ProbabilityEstimatorOutput with denial_probability in
[0.5, 1.0] and a coordinator-friendly summary.

Per PROPOSAL.md §9.5 — the Denial Forecaster runs on EVERY case (regardless
of ClinCase's verdict) so the coordinator can see "what will the payer do?"
and pre-load the appeal pipeline.
"""
from __future__ import annotations

import json

import pytest

from app.agents.denial_forecaster.schemas import ProbabilityEstimatorOutput
from app.agents.denial_forecaster.sub_agents.probability_estimator import (
    _PROMPT as PROBABILITY_PROMPT,
)
from app.llm import get_llm_client
from app.models import (
    Biomarker,
    Citation,
    ClinicalSnapshot,
    Decision,
    Diagnosis,
    NecessityAssessment,
    PolicyExcerpt,
    RequestedTreatment,
)
from app.models.necessity import CriterionAssessment


def _strip_code_fence(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json fences. Strip them."""
    text = text.strip()
    if text.startswith("```"):
        # remove first line (```json or ```) and trailing ```
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


@pytest.mark.asyncio
async def test_high_risk_deny_yields_high_denial_probability():
    """Scenario: HER2-NEGATIVE patient denied trastuzumab (clear policy violation
    per UHC ONC.00043). The probability_estimator MUST predict a high payer-denial
    probability (>= 0.5) and produce a one-line coordinator summary."""

    # 1. Construct the case context
    snapshot = ClinicalSnapshot(
        patient_age=61,
        patient_sex="female",
        primary_diagnosis=Diagnosis(
            icd10_code="C50.912",
            description="Malignant neoplasm of left breast, female",
            stage="IIB",
            source_resource_id="condition-primary",
        ),
        biomarkers=[
            Biomarker(name="HER2 IHC", value="0", source_resource_id="obs-her2-ihc"),
            Biomarker(name="HER2 FISH", value="non-amplified (ratio 1.1)",
                      source_resource_id="obs-her2-fish"),
            Biomarker(name="ER", value="positive (88%)",
                      source_resource_id="obs-er"),
        ],
        performance_status="0",
        requested_treatment=RequestedTreatment(name="trastuzumab", j_code="J9355"),
        free_text_summary=(
            "61-year-old female with stage IIB invasive ductal carcinoma. "
            "HER2-NEGATIVE by both IHC (0) and FISH (non-amplified, ratio 1.1) "
            "per ASCO/CAP 2018. Strongly hormone-receptor positive. Provider "
            "requests trastuzumab — inconsistent with NCCN BINV-N pathway."
        ),
    )

    excerpt = PolicyExcerpt(
        payer_id="uhc",
        policy_id="ONC.00043",
        policy_title="Trastuzumab — Coverage Criteria",
        section_heading="Coverage Criteria §3.1",
        excerpt_text=(
            "Coverage requires documented HER2-positivity by IHC 3+ OR FISH "
            "HER2/CEP17 ratio ≥ 2.0. HER2-negative disease (IHC 0/1+ with "
            "non-amplified FISH) is an exclusion."
        ),
        relevance_score=1.0,
    )

    assessment = NecessityAssessment(
        criteria=[
            CriterionAssessment(
                criterion_text="HER2-positive disease (IHC 3+ or FISH ≥ 2.0)",
                criterion_type="inclusion",
                policy_excerpt_index=0,
                status="NOT_MET",
                supporting_evidence=["HER2 IHC 0", "HER2 FISH ratio 1.1 (non-amplified)"],
                missing_evidence=None,
                confidence=0.97,
                rationale="HER2 IHC 0, FISH ratio 1.1 — definitively HER2-negative per ASCO/CAP 2018",
            ),
        ],
        overall_confidence=0.97,
        summary=(
            "All inclusion criteria fail because the tumour is definitively "
            "HER2-negative. UHC ONC.00043 §3.1 explicitly excludes."
        ),
    )

    decision = Decision(
        verdict="DENY",
        rationale=(
            "The patient's tumour is definitively HER2-negative per ASCO/CAP "
            "2018. UHC ONC.00043 §3.1 explicitly excludes HER2-negative disease."
        ),
        citations=[
            Citation(kind="clinical", text="HER2 IHC 0", pointer="obs-her2-ihc"),
            Citation(kind="policy", text="UHC ONC.00043 §3.1 exclusion",
                     pointer="policy:ONC.00043#3.1"),
        ],
        confidence=0.97,
        risk_flags=["biomarker-mismatch", "exclusion-criterion-failed"],
    )

    # 2. Build the user message exactly as the framework does (JSON dump)
    user_message = json.dumps({
        "decision": decision.model_dump(),
        "assessment": assessment.model_dump(),
        "snapshot": snapshot.model_dump(),
        "excerpts": [excerpt.model_dump()],
        "payer_id": "uhc",
    }, default=str)

    # 3. Direct LLM call — bypasses trace_agent / DB
    response = await get_llm_client().complete(
        system=PROBABILITY_PROMPT,
        user=user_message,
        max_tokens=500,
        temperature=0.0,
    )
    forecast = ProbabilityEstimatorOutput.model_validate_json(
        _strip_code_fence(response.text)
    )

    # 4. Assertions on the contract
    # High-confidence DENY for a clear policy violation should yield a HIGH
    # payer denial probability — Aetna/UHC are very unlikely to overturn.
    assert forecast.denial_probability >= 0.5, (
        f"For an HER2-negative trastuzumab DENY case, expected payer "
        f"denial probability >= 0.5, got {forecast.denial_probability}. "
        f"Summary: {forecast.summary}"
    )

    # Probability is in valid range (Pydantic enforces, but assert for clarity)
    assert 0.0 <= forecast.denial_probability <= 1.0

    # Estimator confidence should be reasonably high (we gave clear inputs)
    assert forecast.estimator_confidence >= 0.5, (
        f"Estimator confidence too low for clear case: "
        f"{forecast.estimator_confidence}"
    )

    # Summary is a non-empty single sentence
    assert forecast.summary
    assert len(forecast.summary.split()) >= 5, (
        f"Summary too short: '{forecast.summary}'"
    )
    assert len(forecast.summary) <= 300, (
        f"Summary too long for coordinator dashboard: '{forecast.summary}'"
    )
