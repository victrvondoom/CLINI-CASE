"""DenialForecaster — parent agent (5 of 7).

Orchestrator on the production framework. Composes 3 sub-agents:

  1. probability_estimator    (LLM, Sonnet)  — payer-denial probability
  2. reason_predictor         (LLM, Haiku)   — top-3 likely payer reasons
  3. appeal_path_recommender  (LLM, Haiku)   — recommended appeal angle

The reason_predictor and appeal_path_recommender are gated by the
probability — empty / skipped when the predicted denial probability is below
their respective thresholds (0.15 and 0.35).
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.denial_forecaster.schemas import (
    AppealPathRecommenderInput,
    DenialForecasterInput,
    DenialForecasterOutput,
    ProbabilityEstimatorInput,
    ReasonPredictorInput,
)
from app.agents.denial_forecaster.sub_agents.appeal_path_recommender import appeal_path_recommender
from app.agents.denial_forecaster.sub_agents.probability_estimator import probability_estimator
from app.agents.denial_forecaster.sub_agents.reason_predictor import reason_predictor
from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.models.forecast import DenialForecast

SUB_AGENTS = [probability_estimator, reason_predictor, appeal_path_recommender]


class DenialForecasterAgent(Agent[DenialForecasterInput, DenialForecasterOutput]):
    name: ClassVar[str] = "denial_forecaster"
    parent: ClassVar = None
    role: ClassVar[str] = "denial_forecast_orchestration"
    description: ClassVar[str] = (
        "Predicts the *payer's* denial probability + top likely reasons + recommended "
        "appeal angle (KFF-2024 calibrated)."
    )

    input_schema: ClassVar[type] = DenialForecasterInput
    output_schema: ClassVar[type] = DenialForecasterOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(DenialForecasterOutput)]

    async def _execute_deterministic(
        self,
        input: DenialForecasterInput,
        ctx: AgentContext,
    ) -> DenialForecasterOutput:
        # 1) Probability (Sonnet)
        prob_result = await probability_estimator.invoke(
            ProbabilityEstimatorInput(
                decision=input.decision,
                assessment=input.assessment,
                snapshot=input.snapshot,
                excerpts=input.excerpts,
                payer_id=input.payer_id,
            ),
            ctx=ctx,
        )
        prob_out = prob_result.output

        # 2) Reasons (Haiku) — only if probability >= 0.15
        top_reasons = []
        if prob_out.denial_probability >= 0.15:
            reason_result = await reason_predictor.invoke(
                ReasonPredictorInput(
                    denial_probability=prob_out.denial_probability,
                    decision=input.decision,
                    assessment=input.assessment,
                    excerpts=input.excerpts,
                    payer_id=input.payer_id,
                ),
                ctx=ctx,
            )
            top_reasons = reason_result.output.top_reasons

        # 3) Appeal angle (Haiku) — only if probability >= 0.35
        strategy = None
        if prob_out.denial_probability >= 0.35:
            appeal_result = await appeal_path_recommender.invoke(
                AppealPathRecommenderInput(
                    denial_probability=prob_out.denial_probability,
                    decision=input.decision,
                    snapshot=input.snapshot,
                    top_reasons=top_reasons,
                    payer_id=input.payer_id,
                ),
                ctx=ctx,
            )
            strategy = appeal_result.output.strategy

        forecast = DenialForecast(
            denial_probability=prob_out.denial_probability,
            confidence=prob_out.estimator_confidence,
            top_reasons=top_reasons,
            appeal_strategy=strategy,
            summary=prob_out.summary,
        )

        return DenialForecasterOutput(
            forecast=forecast,
            n_reasons=len(top_reasons),
            appeal_strategy_present=strategy is not None,
        )


denial_forecaster = DenialForecasterAgent()



