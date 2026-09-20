"""Contract tests for the verdict_synthesizer DeterministicSubAgent.

Demonstrates that a sub-agent is independently testable, no LLM calls,
no DB needed. The same pattern applies to every other sub-agent — each
has its own input/output schema, prompt (LLM ones), and contract tests.
"""
from __future__ import annotations

from app.agents.decision_composer.schemas import VerdictSynthesizerInput
from app.agents.decision_composer.sub_agents.verdict_synthesizer import verdict_synthesizer
from app.models import CriterionAssessment, NecessityAssessment


def _assess(criteria: list[CriterionAssessment], overall: float = 0.95) -> NecessityAssessment:
    return NecessityAssessment(
        criteria=criteria,
        overall_confidence=overall,
        summary="test",
    )


def _crit(
    *,
    text: str = "criterion",
    ctype: str = "inclusion",
    status: str = "MET",
    confidence: float = 0.9,
) -> CriterionAssessment:
    return CriterionAssessment(
        criterion_text=text,
        criterion_type=ctype,  # type: ignore[arg-type]
        policy_excerpt_index=0,
        status=status,  # type: ignore[arg-type]
        supporting_evidence=["e1"],
        missing_evidence=None,
        confidence=confidence,
        rationale="r",
    )


def _run(input: VerdictSynthesizerInput):
    """Helper: invoke the sub-agent. trace_agent will fail without a DB connection,
    but the deterministic _execute method can be called directly for unit testing.
    """
    return verdict_synthesizer._execute(input)  # noqa: SLF001 — testing internal pure function


def test_deny_on_inclusion_not_met():
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([
                _crit(status="MET"),
                _crit(text="LVEF ≥ 50% within 60d", status="NOT_MET"),
            ])
        )
    )
    assert out.verdict == "DENY"
    assert out.trace.triggered_rule == "inclusion_NOT_MET"
    assert out.trace.triggering_criterion_index == 1


def test_deny_on_exclusion_met():
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([
                _crit(status="MET"),
                _crit(text="active uncontrolled infection", ctype="exclusion", status="MET"),
            ])
        )
    )
    assert out.verdict == "DENY"
    assert out.trace.triggered_rule == "exclusion_MET"
    assert out.trace.triggering_criterion_index == 1


def test_refer_on_ambiguous():
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([
                _crit(status="MET"),
                _crit(text="appropriate candidate", status="AMBIGUOUS"),
            ])
        )
    )
    assert out.verdict == "REFER"
    assert out.trace.triggered_rule == "any_AMBIGUOUS"


def test_refer_on_low_confidence():
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([_crit(status="MET", confidence=0.6)], overall=0.6)
        )
    )
    assert out.verdict == "REFER"
    assert out.trace.triggered_rule == "low_overall_confidence"


def test_approve_when_clean():
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([
                _crit(text="HER2+", status="MET", confidence=0.97),
                _crit(text="LVEF 58%", status="MET", confidence=0.95),
            ], overall=0.95)
        )
    )
    assert out.verdict == "APPROVE"
    assert out.trace.triggered_rule == "all_clear_approve"


def test_threshold_is_inclusive_lower_bound():
    """At exactly 0.75, the rule says REFER (we use strict <).

    Verifies the contract: <0.75 → REFER. Exactly 0.75 → not low-conf, but the
    rule has the form `< approve_threshold` so 0.75 itself does NOT trigger
    low_overall_confidence and falls through to APPROVE if all clear.
    """
    out = _run(
        VerdictSynthesizerInput(
            assessment=_assess([_crit(status="MET", confidence=0.75)], overall=0.75)
        )
    )
    assert out.verdict == "APPROVE"


def test_manifest_entry_self_describes():
    """Every sub-agent must be able to self-describe for the manifest."""
    entry = verdict_synthesizer.manifest_entry()
    assert entry["name"] == "verdict_synthesizer"
    assert entry["parent_agent"] == "decision_composer"
    assert entry["is_llm_backed"] is False
    assert entry["input_schema"] == "VerdictSynthesizerInput"
    assert entry["output_schema"] == "VerdictSynthesizerOutput"
    # JSON Schema is exposed so MCP clients can validate inputs
    assert entry["input_schema_json"]["type"] == "object"
    assert "properties" in entry["input_schema_json"]
