"""EmpathyLayer — Patient Communicator sub-agent.

LLM-backed (Sonnet, slightly raised temperature for tone variety). Picks
tone (reassuring/neutral/urgent) by verdict and writes a patient-facing
headline + 2–4 paragraph body in plain language.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.framework import (
    Agent,
    ModelSpec,
    SchemaGuardrail,
)
from app.agents.patient_communicator.schemas import EmpathyLayerInput, EmpathyLayerOutput

# Custom model spec — slightly raised temperature for tone variety
SONNET_PATIENT_VOICE = ModelSpec(
    size="sonnet",
    role="patient_voice",
    max_tokens=1200,
    temperature=0.2,
    cost_per_million_input_tokens=3.0,
    cost_per_million_output_tokens=15.0,
)


_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "patient_communicator" / "sub_agents" / "empathy_layer.txt"
).read_text(encoding="utf-8")


class EmpathyLayerAgent(Agent[EmpathyLayerInput, EmpathyLayerOutput]):
    name: ClassVar[str] = "empathy_layer"
    parent: ClassVar[str] = "patient_communicator"
    role: ClassVar[str] = "patient_voice_synthesis"
    description: ClassVar[str] = (
        "Picks tone (reassuring/neutral/urgent) by verdict and writes a "
        "patient-facing headline + 2–4 paragraph body in plain language."
    )

    input_schema: ClassVar[type] = EmpathyLayerInput
    output_schema: ClassVar[type] = EmpathyLayerOutput

    primary_model: ClassVar = SONNET_PATIENT_VOICE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 2000
    estimated_output_tokens: ClassVar[int] = 1000
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(EmpathyLayerOutput)]


empathy_layer = EmpathyLayerAgent()
