"""EvidenceMatcher — evaluates ONE atomic criterion against the snapshot.

LLM-backed (Sonnet, REFLECTION enabled). Designed for parallel fan-out:
the orchestrator dispatches one invocation per atomic criterion via
asyncio.gather. Self-grades via the framework Grader; below quality_threshold
the agent retries with the grader's feedback embedded in the next call.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import (
    SONNET_REASONING,
    Agent,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)
from app.agents.necessity_reasoner.schemas import (
    EvidenceMatch,
    EvidenceMatcherInput,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "necessity_reasoner" / "sub_agents" / "evidence_matcher.txt"
)


class EvidenceMatcherAgent(Agent[EvidenceMatcherInput, EvidenceMatch]):
    name: ClassVar[str] = "evidence_matcher"
    parent: ClassVar[str] = "necessity_reasoner"
    role: ClassVar[str] = "criterion_evaluation"
    description: ClassVar[str] = (
        "For ONE atomic criterion, decides MET / NOT_MET / AMBIGUOUS against the "
        "ClinicalSnapshot with cited supporting evidence. Self-grades and retries "
        "if the grader flags hallucinated facts or weak evidence."
    )

    input_schema: ClassVar[type] = EvidenceMatcherInput
    output_schema: ClassVar[type] = EvidenceMatch

    primary_model: ClassVar = SONNET_REASONING
    system_prompt: ClassVar[str] = _PROMPT_PATH.read_text(encoding="utf-8")
    estimated_input_tokens: ClassVar[int] = 1500
    estimated_output_tokens: ClassVar[int] = 600

    quality_threshold: ClassVar[float] = 0.80
    max_iterations: ClassVar[int] = 3

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=8_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(EvidenceMatch)]


evidence_matcher = EvidenceMatcherAgent()
