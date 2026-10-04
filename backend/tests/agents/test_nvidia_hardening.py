"""Safety + parsing behaviour added for non-Claude models (NVIDIA Nemotron)."""

import pytest

from app.agents.necessity_reasoner.orchestrator import _conditional_not_met_to_ambiguous
from app.agents.necessity_reasoner.schemas import AtomicCriterion, EvidenceMatch
from app.agents.necessity_reasoner.sub_agents import confidence_calibrator


def _match(text, status, ctype="inclusion", rationale="r"):
    return EvidenceMatch(
        criterion=AtomicCriterion(text=text, criterion_type=ctype, policy_excerpt_index=0),
        status=status,
        supporting_evidence=["primary_diagnosis.stage = 'IIIA'"],
        missing_evidence=None,
        rationale=rationale,
    )


def test_conditional_marked_not_applicable_is_vacuously_met():
    m = _match("If prior anthracycline, LVEF within 30 days", "NOT_MET", rationale="Not applicable: prior_therapies is empty")
    assert _conditional_not_met_to_ambiguous(m).status == "MET"


def test_hard_requirement_with_not_applicable_text_is_not_rescued():
    m = _match("HER2-positive (IHC 3+)", "NOT_MET", rationale="Not applicable: HER2 negative")
    assert _conditional_not_met_to_ambiguous(m).status == "NOT_MET"


@pytest.mark.parametrize(
    "text", ["For metastatic (Stage IV) disease, single agent", "If prior anthracycline, LVEF", "When used adjuvantly, 12 months"]
)
def test_conditional_inclusion_not_met_goes_to_review(text):
    out = _conditional_not_met_to_ambiguous(_match(text, "NOT_MET"))
    assert out.status == "AMBIGUOUS"
    assert out.missing_evidence


@pytest.mark.parametrize(
    ("text", "status", "ctype"),
    [
        ("HER2-positive (IHC 3+ or ISH amplified)", "NOT_MET", "inclusion"),  # hard requirement: keep
        ("For metastatic disease, single agent", "MET", "inclusion"),
        ("For patients with LVEF below 50%", "NOT_MET", "exclusion"),
    ],
)
def test_other_matches_unchanged(text, status, ctype):
    m = _match(text, status, ctype)
    assert _conditional_not_met_to_ambiguous(m) == m


def test_calibrator_repairs_unquoted_summary_and_keeps_min_invariant():
    raw = '{\n  "confidences": [0.9, 0.6],\n  "overall_confidence": 0.9,\n  "summary": HER2 met; LVEF unclear.\n}'
    out = confidence_calibrator._parse_response(raw)
    assert out.summary == "HER2 met; LVEF unclear."
    assert out.overall_confidence == 0.6
