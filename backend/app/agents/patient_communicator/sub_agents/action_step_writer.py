"""ActionStepWriter — Patient Communicator sub-agent.

LLM-backed (Haiku). Generates up to 5 concrete next-step imperatives with
timing tags (today/this_week/this_month/after_decision).
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    SchemaGuardrail,
)
from app.agents.patient_communicator.schemas import (
    ActionStepWriterInput,
    ActionStepWriterOutput,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "patient_communicator" / "sub_agents" / "action_step_writer.txt"
).read_text(encoding="utf-8")


class ActionStepWriterAgent(Agent[ActionStepWriterInput, ActionStepWriterOutput]):
    name: ClassVar[str] = "action_step_writer"
    parent: ClassVar[str] = "patient_communicator"
    role: ClassVar[str] = "next_step_generation"
    description: ClassVar[str] = (
        "Generates up to 5 concrete next-step imperatives with timing tags "
        "(today/this_week/this_month/after_decision)."
    )

    input_schema: ClassVar[type] = ActionStepWriterInput
    output_schema: ClassVar[type] = ActionStepWriterOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 1000
    estimated_output_tokens: ClassVar[int] = 500
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(ActionStepWriterOutput)]


action_step_writer = ActionStepWriterAgent()
