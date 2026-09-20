"""BiomarkerSpecialist — Clinical Extractor sub-agent.

LLM-backed (Haiku). Extracts a focused, treatment-relevant set of high-stakes
oncology biomarkers (HER2, EGFR, BRCA1/2, MSI, PD-L1, ALK, ROS1, BRAF, ECOG,
LVEF) from FHIR + redacted physician note.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from app.agents.clinical_extractor.schemas import (
    BiomarkerSpecialistInput,
    BiomarkerSpecialistOutput,
)
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "clinical_extractor" / "sub_agents" / "biomarker_specialist.txt"
).read_text(encoding="utf-8")


class BiomarkerSpecialistAgent(
    Agent[BiomarkerSpecialistInput, BiomarkerSpecialistOutput]
):
    name: ClassVar[str] = "biomarker_specialist"
    parent: ClassVar[str] = "clinical_extractor"
    role: ClassVar[str] = "biomarker_extraction"
    description: ClassVar[str] = (
        "Extracts a focused, treatment-relevant set of high-stakes oncology biomarkers "
        "(HER2, EGFR, BRCA1/2, MSI, PD-L1, ALK, ROS1, BRAF, ECOG, LVEF) from FHIR + note."
    )

    input_schema: ClassVar[type] = BiomarkerSpecialistInput
    output_schema: ClassVar[type] = BiomarkerSpecialistOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 4000
    estimated_output_tokens: ClassVar[int] = 1200
    max_iterations: ClassVar[int] = 2

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=20_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(BiomarkerSpecialistOutput)]

    def _build_user_message(self, input: BiomarkerSpecialistInput) -> str:
        parts = [
            "FHIR_BUNDLE:",
            json.dumps(input.fhir_bundle, indent=2),
            "",
            f"REQUESTED_TREATMENT: {input.requested_treatment_name}",
        ]
        if input.physician_note_redacted:
            parts += ["", "PHYSICIAN_NOTE_REDACTED:", input.physician_note_redacted]
        return "\n".join(parts)


biomarker_specialist = BiomarkerSpecialistAgent()
