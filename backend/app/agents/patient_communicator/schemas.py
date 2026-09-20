"""Schemas for the patient_communicator package — orchestrator + sub-agents."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models import AppealDraft, ClinicalSnapshot, Decision
from app.models.communication import PatientCommunication, PatientNextStep

# =============================================================================
# Orchestrator I/O — parent agent contract
# =============================================================================

class PatientCommunicatorInput(BaseModel):
    snapshot: ClinicalSnapshot
    decision: Decision
    appeal: AppealDraft | None = None
    payer_id: str


class PatientCommunicatorOutput(BaseModel):
    communication: PatientCommunication
    grade_meets_target: bool
    n_next_steps: int


# -----------------------------------------------------------------------------
# 1. EmpathyLayer
# -----------------------------------------------------------------------------


class EmpathyLayerInput(BaseModel):
    decision: Decision
    snapshot: ClinicalSnapshot
    appeal: AppealDraft | None = None
    payer_id: str


class EmpathyLayerOutput(BaseModel):
    headline: str
    body: str = Field(..., description="2–4 short paragraphs, plain language, no jargon.")
    tone: Literal["reassuring", "neutral", "urgent"]


# -----------------------------------------------------------------------------
# 2. ReadingLevelTuner (deterministic)
# -----------------------------------------------------------------------------


class ReadingLevelTunerInput(BaseModel):
    headline: str
    body: str
    target_grade: float = Field(default=7.0, ge=3.0, le=12.0)


class ReadingLevelTunerOutput(BaseModel):
    grade: float = Field(..., description="Computed Flesch-Kincaid grade level.")
    meets_target: bool
    body_with_substitutions: str = Field(
        ...,
        description="Body with banned-phrase substitutions applied (we regret… → straight talk).",
    )


# -----------------------------------------------------------------------------
# 3. ActionStepWriter
# -----------------------------------------------------------------------------


class ActionStepWriterInput(BaseModel):
    decision: Decision
    appeal: AppealDraft | None = None


class ActionStepWriterOutput(BaseModel):
    next_steps: list[PatientNextStep] = Field(default_factory=list, max_length=5)
