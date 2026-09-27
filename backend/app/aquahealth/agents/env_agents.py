"""The seven AquaHealth agents — real `Agent[I, O]` subclasses of the ClinCase framework.

They are deterministic (no LLM): every finding they emit is computed by
`app.aquahealth.assess`, so assessments are reproducible and auditable, and
the module runs with no model credentials configured. That is deliberate — an
environmental triage signal that changes between two identical observations
cannot meaningfully be reviewed by a human.

They live in `app.aquahealth.agents` (NOT `app.agents`) on purpose: ClinCase's
manifest auto-discovers parents under `app.agents`, and AquaHealth must not
change the 7-agent / 21-sub-agent ClinCase manifest. This mirrors the choice
`app.oncotwin.agents.twin_agents` already makes for the digital-twin layer.

Each agent owns exactly one stage, and they share one in-flight assessment
through the AgentContext working memory, the same way ClinCase parents share
one AgentContext per case.
"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.agents.framework import Agent, AgentContext
from app.aquahealth import assess
from app.aquahealth.models import AgentFinding, EarlyWarning, Observation
from app.aquahealth.vocab import Confidence, DataQuality, EcosystemStatus

WM_KEY = "aquahealth"


# =============================================================================
# Shared schemas
# =============================================================================


class JsonSafeTraceMixin:
    """Make trace payloads JSON-safe for inputs that contain datetimes.

    The framework's `Agent._safe_dump` uses `model_dump()` (Python mode), and
    `TraceSink.open_span` then calls `json.dumps` on the result with no
    `default=`. Clinical agent inputs happen to carry no datetimes, so this
    never surfaced there; an `Observation` carries `observed_at`, which would
    make every traced AquaHealth run fall back to the untraced path.

    Overriding here rather than changing the shared framework keeps ClinCase's
    agents byte-for-byte unchanged. `mode="json"` yields ISO-8601 strings,
    which is also what the trace viewer wants to display.
    """

    def _safe_dump(self, payload: BaseModel) -> dict[str, Any]:
        try:
            return payload.model_dump(mode="json")
        except Exception:  # noqa: BLE001 — tracing must never fail a run
            return {"_unrepresentable": True}


class EnvAgentInput(BaseModel):
    """Input to every AquaHealth agent.

    The observation travels as a model instance rather than an id because the
    agents are pure: they must not reach into the store mid-assessment.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    observation: Observation
    history: list[Observation] = Field(default_factory=list)


class FindingOutput(BaseModel):
    """Output of the six single-finding agents."""

    finding: AgentFinding


class StatusOutput(BaseModel):
    """Output of the explanation agent — the aggregate verdict."""

    status: EcosystemStatus
    status_reason: str
    confidence: Confidence
    data_quality: DataQuality
    completeness: float
    findings: list[AgentFinding]
    one_health_note: str | None = None
    early_warning: EarlyWarning | None = None


# =============================================================================
# Stage agents
# =============================================================================


class EnvironmentalValidationAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Data-quality gate: missing data, impossible values, contradictions."""

    name: ClassVar[str] = "environmental_validation"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "data_quality_validation"
    description: ClassVar[str] = (
        "Checks a freshwater observation for missing fields, implausible "
        "measurements and internally inconsistent answers. Produces a "
        "reviewable data-quality finding rather than rejecting the record, so "
        "a citizen's typo never costs the observation."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(finding=assess.validate_observation(input.observation))


class WaterQualityAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Interprets pH, turbidity, dissolved oxygen, temperature, colour and odour."""

    name: ClassVar[str] = "water_quality"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "water_quality_analysis"
    description: ClassVar[str] = (
        "Interprets whichever water-quality signals exist — instrument "
        "measurements when supplied, otherwise the citizen's visual and "
        "olfactory observations — and states which ones drove the finding."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(finding=assess.assess_water_quality(input.observation))


class BiodiversityAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Reads presence, absence and unusual-organism signals."""

    name: ClassVar[str] = "biodiversity"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "biodiversity_analysis"
    description: ClassVar[str] = (
        "Analyses biodiversity observations, treating a checked-but-absent "
        "group as real evidence rather than a gap, and flags dead or unusual "
        "organisms as adverse signals."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(finding=assess.assess_biodiversity(input.observation))


class EnvironmentalContextAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Weather and land-use context that can explain or compound a signal."""

    name: ClassVar[str] = "environmental_context"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "context_analysis"
    description: ClassVar[str] = (
        "Analyses rainfall, flooding, drought, construction, waste and "
        "suspected-discharge context. Names a plausible natural cause when one "
        "exists, so a reviewer is not sent chasing a discharge that was rain."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(finding=assess.assess_context(input.observation))


class TrendAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Compares against history at the same waterbody — or declines to."""

    name: ClassVar[str] = "trend"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "temporal_analysis"
    description: ClassVar[str] = (
        "Compares an observation against the same waterbody's recent baseline. "
        f"Reports 'insufficient historical observations' below "
        f"{assess.MIN_TREND_OBSERVATIONS} records rather than drawing a trend "
        "through too few points."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(
            finding=assess.assess_trend(input.observation, input.history)
        )


class OneHealthAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, FindingOutput]):
    """Ecosystem -> animal -> community relevance, in cautious language."""

    name: ClassVar[str] = "one_health"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "one_health_linkage"
    description: ClassVar[str] = (
        "Connects ecosystem signals to animal and potential community "
        "relevance. States potential relevance only — it does not diagnose "
        "disease, assert causation, or issue public-health advice."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = FindingOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> FindingOutput:
        return FindingOutput(finding=assess.assess_one_health(input.observation))


class ExplanationAgent(JsonSafeTraceMixin, Agent[EnvAgentInput, StatusOutput]):
    """Aggregates every stage into the explainable verdict.

    Reads the findings the earlier agents left in working memory, so the
    aggregate verdict is built from exactly what the user is shown — the
    explanation can never disagree with the findings listed above it.
    """

    name: ClassVar[str] = "explanation"
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = "explanation_synthesis"
    description: ClassVar[str] = (
        "Produces the Prototype Ecosystem Observation Status with its finding, "
        "evidence, confidence, data quality, uncertainty and recommended next "
        "step. Emits no chain-of-thought."
    )

    input_schema: ClassVar[type] = EnvAgentInput
    output_schema: ClassVar[type] = StatusOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self, input: EnvAgentInput, ctx: AgentContext
    ) -> StatusOutput:
        obs = input.observation
        findings: list[AgentFinding] = list(
            ctx.working_memory.get(WM_KEY, {}).get("findings", [])
        )

        status, reason, confidence = assess.derive_status(obs)
        warning = assess.derive_early_warning(obs, input.history, status)

        one_health = next((f for f in findings if f.agent == "one_health"), None)

        return StatusOutput(
            status=status,
            status_reason=reason,
            confidence=confidence,
            data_quality=assess.data_quality(obs),
            completeness=assess.completeness(obs),
            findings=findings,
            one_health_note=one_health.finding if one_health else None,
            early_warning=warning if warning.active else None,
        )


# =============================================================================
# Manifest
# =============================================================================

#: Ordered pipeline. `service.run_assessment` walks this list.
AQUAHEALTH_AGENTS: tuple[type[Agent[Any, Any]], ...] = (
    EnvironmentalValidationAgent,
    WaterQualityAgent,
    BiodiversityAgent,
    EnvironmentalContextAgent,
    TrendAgent,
    OneHealthAgent,
    ExplanationAgent,
)


def aquahealth_manifest() -> dict[str, Any]:
    """Introspection payload for the AquaHealth agents panel.

    Separate from ClinCase's `/agents/manifest`, which keeps reporting its own
    7 clinical agents unchanged.
    """
    return {
        "module": "aquahealth",
        "deterministic": True,
        "n_agents": len(AQUAHEALTH_AGENTS),
        "note": (
            "AquaHealth agents are deterministic: identical observations "
            "always produce identical assessments, so a human reviewer is "
            "auditing a rule rather than a sample from a model."
        ),
        "agents": [
            {
                "name": a.name,
                "role": a.role,
                "description": a.description,
                "uses_llm": a.primary_model is not None,
            }
            for a in AQUAHEALTH_AGENTS
        ],
    }
