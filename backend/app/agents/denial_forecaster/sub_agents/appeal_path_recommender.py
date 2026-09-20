"""AppealPathRecommender — Denial Forecaster sub-agent.

LLM-backed (Haiku). Recommends the best appeal angle (enum) + KFF-baseline-
calibrated overturn probability when denial_probability ≥ 0.35; otherwise
returns strategy=None with a skipped_reason.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.agents.denial_forecaster.schemas import (
    AppealPathRecommenderInput,
    AppealPathRecommenderOutput,
)
from app.agents.framework import (
    HAIKU_LITE,
    Agent,
    SchemaGuardrail,
)

_PROMPT = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "denial_forecaster" / "sub_agents" / "appeal_path_recommender.txt"
).read_text(encoding="utf-8")


class AppealPathRecommenderAgent(
    Agent[AppealPathRecommenderInput, AppealPathRecommenderOutput]
):
    name: ClassVar[str] = "appeal_path_recommender"
    parent: ClassVar[str] = "denial_forecaster"
    role: ClassVar[str] = "appeal_strategy_selection"
    description: ClassVar[str] = (
        "Recommends the best appeal angle (enum) + KFF-baseline-calibrated overturn "
        "probability when denial probability ≥ 0.35; otherwise skipped with a reason."
    )

    input_schema: ClassVar[type] = AppealPathRecommenderInput
    output_schema: ClassVar[type] = AppealPathRecommenderOutput

    primary_model: ClassVar = HAIKU_LITE
    system_prompt: ClassVar[str] = _PROMPT
    estimated_input_tokens: ClassVar[int] = 1500
    estimated_output_tokens: ClassVar[int] = 500
    max_iterations: ClassVar[int] = 2

    output_guardrails: ClassVar = [SchemaGuardrail(AppealPathRecommenderOutput)]


appeal_path_recommender = AppealPathRecommenderAgent()
