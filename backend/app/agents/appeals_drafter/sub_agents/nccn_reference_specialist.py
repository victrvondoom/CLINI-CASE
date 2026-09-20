"""NCCNReferenceSpecialist — Appeals Drafter sub-agent.

LLM-backed (Haiku). Returns 1–5 precise NCCN Clinical Practice Guidelines
references that support the patient's counter-position (e.g.
'NCCN Breast 4.2025 § BINV-J').
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.appeals_drafter.schemas import (
    NCCNReferenceSpecialistInput,
    NCCNReferenceSpecialistOutput,
)
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "appeals_drafter" / "sub_agents" / "nccn_reference_specialist.txt"
).read_text(encoding="utf-8")


class NCCNReferenceSpecialistAgent(
    Agent[NCCNReferenceSpecialistInput, NCCNReferenceSpecialistOutput]
):
    name: ClassVar[str] = "nccn_reference_specialist"
    parent: ClassVar[str] = "appeals_drafter"
    role: ClassVar[str] = "nccn_citation"
    description: ClassVar[str] = (
        "Returns 1–5 precise NCCN Clinical Practice Guidelines references that "
        "support the patient's counter-position (e.g. 'NCCN Breast 4.2025 § BINV-J')."
    )

    input_schema: ClassVar[type] = NCCNReferenceSpecialistInput
    output_schema: ClassVar[type] = NCCNReferenceSpecialistOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 1500
    estimated_output_tokens: ClassVar[int] = 600
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(NCCNReferenceSpecialistOutput)]


nccn_reference_specialist = NCCNReferenceSpecialistAgent()
