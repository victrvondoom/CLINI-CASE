"""ReadingLevelTuner — Patient Communicator sub-agent.

Deterministic. Pure-Python Flesch-Kincaid grade calculator + banned-phrase
substitution. Enforces ≤7th-grade reading level on patient-facing copy.
"""
from __future__ import annotations

import re
from typing import ClassVar

from app.agents.framework import Agent, AgentContext
from app.agents.patient_communicator.schemas import (
    ReadingLevelTunerInput,
    ReadingLevelTunerOutput,
)

_BANNED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bwe regret to inform you\b", re.I), "Your insurance has said no for now"),
    (re.compile(r"\bthe system\b",                re.I), "your insurance company"),
    (re.compile(r"\bthe AI\b",                    re.I), "the review"),
    (re.compile(r"\bthe payer\b",                 re.I), "your insurance company"),
    (re.compile(r"\brequesting provider\b",       re.I), "your doctor"),
]


def _count_syllables(word: str) -> int:
    word = word.lower()
    vowels = "aeiouy"
    count = 0
    prev = False
    for c in word:
        is_v = c in vowels
        if is_v and not prev:
            count += 1
        prev = is_v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def _flesch_kincaid_grade(text: str) -> float:
    sentences = max(len(re.findall(r"[.!?]+", text)) or 1, 1)
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 6.0
    n_words = len(words)
    n_syl = sum(_count_syllables(w) for w in words)
    return 0.39 * (n_words / sentences) + 11.8 * (n_syl / n_words) - 15.59


class ReadingLevelTunerAgent(
    Agent[ReadingLevelTunerInput, ReadingLevelTunerOutput]
):
    name: ClassVar[str] = "reading_level_tuner"
    parent: ClassVar[str] = "patient_communicator"
    role: ClassVar[str] = "reading_level_enforcement"
    description: ClassVar[str] = (
        "Pure-Python Flesch-Kincaid grade calculator + banned-phrase substitution. "
        "Enforces ≤7th-grade reading level on patient-facing copy."
    )

    input_schema: ClassVar[type] = ReadingLevelTunerInput
    output_schema: ClassVar[type] = ReadingLevelTunerOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: ReadingLevelTunerInput,
        ctx: AgentContext,
    ) -> ReadingLevelTunerOutput:
        body = input.body
        for pat, repl in _BANNED:
            body = pat.sub(repl, body)
        grade = round(_flesch_kincaid_grade(body), 2)
        return ReadingLevelTunerOutput(
            grade=grade,
            meets_target=grade <= input.target_grade,
            body_with_substitutions=body,
        )


reading_level_tuner = ReadingLevelTunerAgent()
