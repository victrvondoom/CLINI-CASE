"""Contract tests for reading_level_tuner DeterministicSubAgent."""
from __future__ import annotations

from app.agents.patient_communicator.schemas import ReadingLevelTunerInput
from app.agents.patient_communicator.sub_agents.reading_level_tuner import (
    _flesch_kincaid_grade,
    reading_level_tuner,
)


def test_simple_sentences_score_low():
    grade = _flesch_kincaid_grade("The cat sat. The dog ran. We went home.")
    assert grade < 5.0


def test_complex_sentences_score_high():
    grade = _flesch_kincaid_grade(
        "The phenomenological hermeneutics of pharmacotherapeutic disposition "
        "necessitate exhaustive reconciliation of pharmacokinetic interaction "
        "matrices throughout the multimodal therapeutic continuum."
    )
    assert grade > 12.0


def test_strips_corporate_hedging():
    out = reading_level_tuner._execute(  # noqa: SLF001
        ReadingLevelTunerInput(
            headline="x",
            body="We regret to inform you that the system has decided.",
        )
    )
    assert "regret to inform" not in out.body_with_substitutions
    assert "the system" not in out.body_with_substitutions
    assert "your insurance company" in out.body_with_substitutions


def test_meets_target_when_simple():
    out = reading_level_tuner._execute(  # noqa: SLF001
        ReadingLevelTunerInput(
            headline="Good news.",
            body="Your treatment was approved. Call your doctor today. They will set up the next step.",
            target_grade=7.0,
        )
    )
    assert out.meets_target is True
    assert out.grade < 7.0


def test_grade_field_populated():
    out = reading_level_tuner._execute(  # noqa: SLF001
        ReadingLevelTunerInput(headline="x", body="The cat sat. The dog ran.")
    )
    # Flesch-Kincaid can go slightly negative for trivial text — that's fine.
    # The contract is just "produces a numeric grade ≤ 12 for trivial input".
    assert isinstance(out.grade, float)
    assert out.grade < 12.0
