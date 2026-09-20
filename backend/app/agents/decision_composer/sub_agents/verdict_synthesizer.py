"""VerdictSynthesizer — Decision Composer sub-agent.

DeterministicSubAgent. No LLM. The deterministic verdict rule:
    inclusion NOT_MET   → DENY
    exclusion MET       → DENY
    any AMBIGUOUS       → REFER
    overall_confidence < approve_threshold (default 0.75) → REFER
    otherwise           → APPROVE

Returns the verdict + a `VerdictDecisionTrace` describing exactly which rule
fired and on which criterion. Byte-for-byte replayable from the
NecessityAssessment alone.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.decision_composer.schemas import (
    VerdictDecisionTrace,
    VerdictSynthesizerInput,
    VerdictSynthesizerOutput,
)
from app.agents.framework import Agent, AgentContext


class VerdictSynthesizerAgent(
    Agent[VerdictSynthesizerInput, VerdictSynthesizerOutput]
):
    name: ClassVar[str] = "verdict_synthesizer"
    parent: ClassVar[str] = "decision_composer"
    role: ClassVar[str] = "deterministic_verdict_rule"
    description: ClassVar[str] = (
        "Maps a NecessityAssessment to APPROVE / DENY / REFER and emits a full "
        "audit trace of which rule fired. No LLM. Microsecond latency. "
        "Byte-for-byte replayable."
    )

    input_schema: ClassVar[type] = VerdictSynthesizerInput
    output_schema: ClassVar[type] = VerdictSynthesizerOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: VerdictSynthesizerInput,
        ctx: AgentContext,
    ) -> VerdictSynthesizerOutput:
        a = input.assessment
        for i, c in enumerate(a.criteria):
            if c.criterion_type == "inclusion" and c.status == "NOT_MET":
                return VerdictSynthesizerOutput(
                    verdict="DENY",
                    trace=VerdictDecisionTrace(
                        triggered_rule="inclusion_NOT_MET",
                        triggering_criterion_index=i,
                        overall_confidence=a.overall_confidence,
                    ),
                )
            if c.criterion_type == "exclusion" and c.status == "MET":
                return VerdictSynthesizerOutput(
                    verdict="DENY",
                    trace=VerdictDecisionTrace(
                        triggered_rule="exclusion_MET",
                        triggering_criterion_index=i,
                        overall_confidence=a.overall_confidence,
                    ),
                )
        for i, c in enumerate(a.criteria):
            if c.status == "AMBIGUOUS":
                return VerdictSynthesizerOutput(
                    verdict="REFER",
                    trace=VerdictDecisionTrace(
                        triggered_rule="any_AMBIGUOUS",
                        triggering_criterion_index=i,
                        overall_confidence=a.overall_confidence,
                    ),
                )
        if a.overall_confidence < input.approve_threshold:
            return VerdictSynthesizerOutput(
                verdict="REFER",
                trace=VerdictDecisionTrace(
                    triggered_rule="low_overall_confidence",
                    triggering_criterion_index=None,
                    overall_confidence=a.overall_confidence,
                ),
            )
        return VerdictSynthesizerOutput(
            verdict="APPROVE",
            trace=VerdictDecisionTrace(
                triggered_rule="all_clear_approve",
                triggering_criterion_index=None,
                overall_confidence=a.overall_confidence,
            ),
        )


verdict_synthesizer = VerdictSynthesizerAgent()
