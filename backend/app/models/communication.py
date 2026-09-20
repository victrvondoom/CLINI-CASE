"""Patient Communicator output schema (7th agent in the LangGraph DAG).

Source of truth: Phase-1 deck Page 3 architecture flow ("Patient Communicator")
and Page 6 "Patient-friendly explanation generator" ClinCase-only feature.

The Patient Communicator runs at the end of every case — APPROVE, DENY, REFER
— and produces a 6th-grade-reading-level explanation the coordinator can hand
to the patient (or their caregiver). This addresses CMS-0057-F § IV.C
patient-accessible decision rationale and the JEHRA 2023 health-literacy
mandate.

Decomposed into 3 named sub-agents (declared in the agent file):
  1. Reading-Level Tuner  — calibrates language to ~6th-grade Flesch-Kincaid
  2. Empathy Layer        — adds compassionate framing (not robotic)
  3. Action-Step Writer   — concrete next steps the patient can take
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PatientNextStep(BaseModel):
    """One concrete action the patient or caregiver can take."""

    step_number: int = Field(..., ge=1, le=10)
    text: str = Field(..., description="One imperative sentence, plain language.")
    timing: Literal["today", "this_week", "this_month", "after_decision"] = "this_week"


class PatientCommunication(BaseModel):
    """Patient-facing summary of an ClinCase case outcome."""

    headline: str = Field(
        ...,
        description="One-sentence headline at 6th-grade reading level. e.g. 'Your insurance is reviewing your treatment.'",
    )
    body: str = Field(
        ...,
        description="2–4 short paragraphs explaining what happened, in plain language, no medical jargon.",
    )
    next_steps: list[PatientNextStep] = Field(default_factory=list, max_length=5)
    tone: Literal["reassuring", "neutral", "urgent"] = "neutral"
    reading_level_grade: float = Field(
        default=6.0, ge=3.0, le=12.0,
        description="Flesch-Kincaid grade level. Target ≤ 7.0.",
    )
    contains_phi: bool = Field(
        default=False,
        description="Always false — patient communications use initials and structured medical context only.",
    )
