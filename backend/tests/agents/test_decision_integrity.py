"""Adversarial, offline regressions for model-to-decision safety boundaries."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agents.decision_composer import derive_verdict
from app.agents.decision_composer.integrity import validate_citation_provenance
from app.agents.decision_composer.schemas import (
    CitationLinkerInput,
    CitationLinkerOutput,
    DecisionComposerInput,
    VerdictSynthesizerInput,
)
from app.agents.decision_composer.sub_agents.verdict_synthesizer import evaluate_verdict
from app.agents.necessity_reasoner.orchestrator import (
    criterion_splitter,
    evidence_matcher,
    necessity_reasoner,
)
from app.agents.necessity_reasoner.schemas import (
    AtomicCriterion,
    ConfidenceCalibratorOutput,
    CriterionSplitterOutput,
    EvidenceMatch,
    NecessityReasonerInput,
)
from app.models import (
    ClinicalSnapshot,
    CriterionAssessment,
    Diagnosis,
    NecessityAssessment,
    PolicyExcerpt,
    RequestedTreatment,
)


def match(status="MET", index=0):
    return EvidenceMatch(
        criterion=AtomicCriterion(text=f"criterion {index}", policy_excerpt_index=index),
        status=status,
        supporting_evidence=["documented"],
        rationale="rationale",
    )


def calibrate(scores, overall=0.99):
    return ConfidenceCalibratorOutput(confidences=scores, overall_confidence=overall, summary="summary")


def assessment(status="MET", confidence=0.95):
    return calibrate([confidence]).to_assessment([match(status)])


def snapshot():
    return ClinicalSnapshot(
        primary_diagnosis=Diagnosis(icd10_code="C50", description="test", source_resource_id="condition-1"),
        requested_treatment=RequestedTreatment(name="test treatment"),
        performance_status="1",
        free_text_summary="summary",
    )


def excerpt():
    return PolicyExcerpt(payer_id="payer", policy_id="0048", policy_title="title", section_heading="Eligibility", excerpt_text="criterion", relevance_score=1)


@pytest.mark.parametrize("scores", [[0.99], [0.99, 0.99, 0.99]])
def test_calibration_cannot_drop_or_add_criteria(scores):
    # Previously the shorter list silently removed NOT_MET and yielded APPROVE.
    matches = [match("MET"), match("NOT_MET", 1)]
    with pytest.raises(ValueError, match="exactly one"):
        calibrate(scores).to_assessment(matches)
    assert len(matches) == 2


def test_complete_calibration_retains_failed_criterion_and_denies():
    result = calibrate([0.99, 0.99]).to_assessment([match("MET"), match("NOT_MET", 1)])
    assert len(result.criteria) == 2
    assert derive_verdict(result) == "DENY"


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf"), -float("inf")])
def test_invalid_calibration_and_canonical_scores_rejected(score):
    with pytest.raises(ValidationError):
        calibrate([score])
    with pytest.raises(ValidationError):
        CriterionAssessment.model_validate({**assessment().criteria[0].model_dump(), "confidence": score})
    with pytest.raises(ValidationError):
        NecessityAssessment.model_validate({**assessment().model_dump(), "overall_confidence": score})


def test_empty_assessment_and_missing_criterion_fail_closed():
    with pytest.raises(ValidationError):
        NecessityAssessment(criteria=[], overall_confidence=1, summary="empty")
    with pytest.raises(ValueError, match="source criterion"):
        calibrate([0.99]).to_assessment([EvidenceMatch(status="MET", rationale="r")])


@pytest.mark.parametrize("status", ["MET", "NOT_MET", "AMBIGUOUS"])
def test_inflated_aggregate_cannot_bypass_review(status):
    result = assessment(status, confidence=0.2)
    assert result.overall_confidence == 0.2
    assert derive_verdict(result) == "REFER"
    assert evaluate_verdict(VerdictSynthesizerInput(assessment=result)).trace.triggered_rule == "low_overall_confidence"


def test_lower_aggregate_preserved():
    assert calibrate([0.9], overall=0.4).to_assessment([match()]).overall_confidence == 0.4


@pytest.mark.parametrize("status", ["MET", "NOT_MET", "AMBIGUOUS"])
@pytest.mark.parametrize("confidence", [0, 0.749, 0.75, 1])
def test_legacy_and_production_verdict_share_rule(status, confidence):
    result = assessment(status, confidence)
    assert derive_verdict(result) == evaluate_verdict(VerdictSynthesizerInput(assessment=result)).verdict


@pytest.mark.asyncio
@pytest.mark.parametrize("criteria", [
    [AtomicCriterion(text="criterion", policy_excerpt_index=1)],
    [AtomicCriterion(text="criterion", policy_excerpt_index=0), AtomicCriterion(text=" CRITERION ", policy_excerpt_index=0)],
    [AtomicCriterion(text="  ", policy_excerpt_index=0)],
])
async def test_invalid_splitter_sources_fail_before_evidence_calls(monkeypatch, criteria):
    monkeypatch.setattr(type(criterion_splitter), "invoke", AsyncMock(return_value=SimpleNamespace(output=CriterionSplitterOutput(atomic_criteria=criteria))))
    evidence = AsyncMock()
    monkeypatch.setattr(type(evidence_matcher), "invoke", evidence)
    with pytest.raises(ValueError):
        await necessity_reasoner._execute_deterministic(NecessityReasonerInput(snapshot=snapshot(), excerpts=[excerpt()]), None)
    evidence.assert_not_awaited()


def citation_input():
    return CitationLinkerInput(rationale="claim", assessment=assessment(), excerpts=[excerpt()], snapshot=snapshot())


def citation_output(pointer, kind="clinical", coverage=True):
    return CitationLinkerOutput(citations=[{"text": "claim", "pointer": pointer, "kind": kind}], every_claim_has_pointer=coverage)


@pytest.mark.parametrize("pointer", ["condition-1", "primary_diagnosis.description", "performance_status"])
def test_supplied_clinical_pointers_resolve(pointer):
    validate_citation_provenance(citation_input(), citation_output(pointer))


@pytest.mark.parametrize("pointer,kind", [("invented-observation", "clinical"), ("biomarkers[0]", "clinical"), ("policy_excerpts[1]", "policy"), ("FDA imaginary label", "fda_label"), ("payer 10048 Eligibility", "policy"), ("", "policy")])
def test_invented_citation_sources_rejected(pointer, kind):
    with pytest.raises(ValueError):
        validate_citation_provenance(citation_input(), citation_output(pointer, kind))


@pytest.mark.parametrize("pointer", ["policy_excerpts[0]", "payer 0048 Eligibility"])
def test_supplied_policy_pointers_resolve(pointer):
    validate_citation_provenance(citation_input(), citation_output(pointer, "policy"))


def test_linker_incomplete_coverage_rejected():
    with pytest.raises(ValueError, match="incomplete claim coverage"):
        validate_citation_provenance(citation_input(), citation_output("condition-1", coverage=False))


def test_linker_must_explicitly_attest_claim_coverage():
    with pytest.raises(ValidationError):
        CitationLinkerOutput(citations=[{
            "text": "claim", "pointer": "condition-1", "kind": "clinical",
        }])


def test_composer_rejects_out_of_range_assessment_source():
    result = calibrate([0.99]).to_assessment([match(index=1)])
    with pytest.raises(ValidationError, match="unavailable policy excerpt"):
        DecisionComposerInput(snapshot=snapshot(), excerpts=[excerpt()], assessment=result)

@pytest.mark.asyncio
@pytest.mark.parametrize("valid", [True, False])
async def test_composer_checks_provenance_before_emitting_decision(monkeypatch, valid):
    from app.agents.decision_composer.orchestrator import (
        citation_linker,
        decision_composer,
        rationale_writer,
        verdict_synthesizer,
    )
    from app.agents.decision_composer.schemas import RationaleWriterOutput

    monkeypatch.setattr(type(verdict_synthesizer), "invoke", AsyncMock(return_value=SimpleNamespace(output=evaluate_verdict(VerdictSynthesizerInput(assessment=assessment())))))
    monkeypatch.setattr(type(rationale_writer), "invoke", AsyncMock(return_value=SimpleNamespace(output=RationaleWriterOutput(rationale="claim"))))
    monkeypatch.setattr(type(citation_linker), "invoke", AsyncMock(return_value=SimpleNamespace(output=citation_output("condition-1" if valid else "invented"))))
    request = DecisionComposerInput(snapshot=snapshot(), excerpts=[excerpt()], assessment=assessment())
    if valid:
        result = await decision_composer._execute_deterministic(request, None)
        assert result.decision.verdict == "APPROVE"
        assert result.decision.citations[0].pointer == "condition-1"
        assert result.decision.confidence == 0.95
    else:
        with pytest.raises(ValueError, match="absent from the snapshot"):
            await decision_composer._execute_deterministic(request, None)


def test_missing_assessment_routes_to_review():
    from app.graph.build import _route_after_reasoner
    from app.graph.state import ClinCaseState

    state = ClinCaseState(case_id="test", fhir_bundle={}, requested_treatment={}, payer_id="payer")
    assert _route_after_reasoner(state) == "review_gate"
