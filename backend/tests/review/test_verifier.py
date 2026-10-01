from app.models import Citation, Decision, NecessityAssessment
from app.models.necessity import CriterionAssessment
from app.verification.verifier import derive_verdict, verify


def _na(*pairs):
    cs = [
        CriterionAssessment(criterion_text="c", criterion_type=t, policy_excerpt_index=0, status=s,
                            supporting_evidence=[], confidence=0.9, rationale="r")
        for t, s in pairs
    ]  # fmt: skip
    return NecessityAssessment(criteria=cs, overall_confidence=0.9, summary="s")


def _dec(v, cites=()):
    return Decision(verdict=v, rationale="r", citations=list(cites), confidence=0.9, risk_flags=[])


BUNDLE = {"entry": [{"resource": {"id": "obs-1"}}]}


def test_derivation():
    assert derive_verdict(_na(("inclusion", "MET"), ("exclusion", "NOT_MET"))) == "APPROVE"
    assert derive_verdict(_na(("inclusion", "NOT_MET"))) == "DENY"
    assert derive_verdict(_na(("exclusion", "MET"))) == "DENY"
    assert derive_verdict(_na(("inclusion", "MET"), ("inclusion", "AMBIGUOUS"))) == "REFER"


def test_agreement_has_no_pause():
    c = Citation(kind="clinical", pointer="obs-1", text="x")
    v = verify(_dec("APPROVE", [c]), _na(("inclusion", "MET")), BUNDLE)
    assert v.agrees and v.pause_kind is None


def test_disagreement_escalates():
    c = Citation(kind="clinical", pointer="obs-1", text="x")
    v = verify(_dec("APPROVE", [c]), _na(("inclusion", "NOT_MET")), BUNDLE)
    assert not v.agrees and v.pause_kind == "verification_disagreement"


def test_dangling_citation_is_evidence_conflict():
    c = Citation(kind="clinical", pointer="nope", text="x")
    v = verify(_dec("APPROVE", [c]), _na(("inclusion", "MET")), BUNDLE)
    assert v.pause_kind == "evidence_conflict" and v.dangling_citations == ["nope"]
