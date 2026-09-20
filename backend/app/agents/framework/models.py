"""Model spec + cost-aware router.

Each Agent declares a `primary_model` (its default). On a schema-validation
failure or a grader-fail, the router escalates to a stronger model
(typically Sonnet) and retries with a "you previously produced this invalid
output: <text>; correct it" suffix in the user message.

The router is also where Bedrock-vs-OpenRouter-vs-Anthropic provider
routing happens — agents never name a provider directly; they name a
size + a role and the router resolves to a concrete model id at call time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import settings


@dataclass(frozen=True)
class ModelSpec:
    """Logical model identifier independent of provider.

    Attributes:
      size:           "haiku" | "sonnet" — capability tier.
      role:           "reasoning" | "extraction" | "summarization" | "grading"
                      Free-form descriptor for telemetry / cost analysis.
      max_tokens:     output ceiling.
      temperature:    0.0 = deterministic; raise for tone-heavy work.
      cost_per_million_input_tokens:  USD per 1M input tokens for this size.
      cost_per_million_output_tokens: USD per 1M output tokens for this size.
    """

    size: Literal["haiku", "sonnet"]
    role: str = "reasoning"
    # Round-15 systemic fix: default bumped from 1500 → 3000.
    # Empirical measurement showed 1500 truncates JSON output for nearly
    # every structured-JSON-producing agent (4 separate truncation bugs
    # surfaced sequentially in 5 test runs). 3000 gives 2x margin while
    # keeping cost reasonable. Agents needing more declare it explicitly.
    max_tokens: int = 3000
    temperature: float = 0.0
    cost_per_million_input_tokens: float = 3.0
    cost_per_million_output_tokens: float = 15.0


# =============================================================================
# Standard model tiers — agents pick from these.
# =============================================================================
# Sizing rule of thumb (post round-15 audit):
#   • Agents producing single floats or short text         → SONNET_REASONING (3000)
#   • Agents producing 600-word letters                    → SONNET_LETTER    (3500)
#   • Agents producing 5-15 structured items               → SONNET_MEDIUM_JSON (4000)
#   • Agents producing 600-word letters in JSON envelope   → SONNET_LONG_JSON  (8000)
#   • Lightweight extraction (small JSON, fast)            → HAIKU_LITE       (3000)
#   • Output grading (5-field score + paragraph feedback)  → HAIKU_GRADER     (1500)

SONNET_REASONING = ModelSpec(
    size="sonnet", role="reasoning",
    # max_tokens defaults to 3000 (post-round-15 base)
    cost_per_million_input_tokens=3.0,
    cost_per_million_output_tokens=15.0,
)
SONNET_LETTER = ModelSpec(
    size="sonnet", role="letter_writing",
    max_tokens=3500, temperature=0.2,
    cost_per_million_input_tokens=3.0,
    cost_per_million_output_tokens=15.0,
)
SONNET_MEDIUM_JSON = ModelSpec(
    # Round-15: for agents that produce 5-15 structured items per call
    # (criterion_splitter, evidence_matcher per-criterion result, etc.).
    # 4000 tokens ~= 8-15 structured criteria with text + pointer + tags.
    size="sonnet", role="medium_json_output",
    max_tokens=4000, temperature=0.0,
    cost_per_million_input_tokens=3.0,
    cost_per_million_output_tokens=15.0,
)
SONNET_LONG_JSON = ModelSpec(
    # Round-15: dedicated spec for agents that produce large structured JSON
    # (counter_evidence_finder, letter_composer). 8000 tokens avoids the
    # mid-string truncation that broke parsing on DENY cases.
    size="sonnet", role="large_json_output",
    max_tokens=8000, temperature=0.0,
    cost_per_million_input_tokens=3.0,
    cost_per_million_output_tokens=15.0,
)
HAIKU_LITE = ModelSpec(
    size="haiku", role="lightweight_extraction",
    # Round-15: bumped from 2000 → 3000 to give safety margin to
    # appeal_path_recommender (nested AppealStrategy + reasoning),
    # citation_linker (1-10 citations + claim text), reason_predictor
    # (top-3 reasons), confidence_calibrator (per-criterion floats).
    max_tokens=3000, temperature=0.0,
    cost_per_million_input_tokens=1.0,
    cost_per_million_output_tokens=5.0,
)
HAIKU_GRADER = ModelSpec(
    size="haiku", role="grading",
    # Round-15 (CRITICAL FIX): bumped from 400 → 1500.
    # GraderScore = 4 floats + 1 paragraph string ≈ 350-500 tokens of JSON.
    # Old 400-token cap truncated the `feedback` field on EVERY grader call,
    # causing AgentExhausted retries on every LLM agent. This is a global
    # bug because the grader is invoked after every LLM agent's output.
    max_tokens=1500, temperature=0.0,
    cost_per_million_input_tokens=1.0,
    cost_per_million_output_tokens=5.0,
)


def estimate_cost(spec: ModelSpec, *, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for given token counts under this spec."""
    return (
        input_tokens * spec.cost_per_million_input_tokens / 1_000_000
        + output_tokens * spec.cost_per_million_output_tokens / 1_000_000
    )


def resolve_model_id(spec: ModelSpec) -> str | None:
    """Map a logical ModelSpec to a provider-specific model id.

    Round-15: also routes Haiku for OpenRouter and Anthropic-direct providers.
    Without this, every Haiku-tagged agent (phi_sanitizer, biomarker_specialist,
    evidence_matcher, etc.) silently fell through to Sonnet on OpenRouter,
    multiplying observed cost ~3x and inflating latency.
    """
    if settings.LLM_PROVIDER == "bedrock":
        if spec.size == "haiku":
            return settings.BEDROCK_HAIKU_MODEL_ID
        return settings.BEDROCK_MODEL_ID
    if settings.LLM_PROVIDER == "openrouter":
        if spec.size == "haiku":
            return "anthropic/claude-haiku-4.5"
        return settings.OPENROUTER_MODEL  # Sonnet by default
    if settings.LLM_PROVIDER == "anthropic":
        if spec.size == "haiku":
            return "claude-haiku-4-5"
        return settings.ANTHROPIC_MODEL
    return None


# =============================================================================
# Router
# =============================================================================


class ModelRouter:
    """Cost-aware model router.

    Responsibilities:
      • Resolve a ModelSpec to a concrete model id at call time.
      • Provide an escalation rule: when a Haiku call fails (schema or grader),
        the next attempt uses a Sonnet ModelSpec.
      • Track usage for telemetry.
    """

    @staticmethod
    def primary(spec: ModelSpec) -> ModelSpec:
        return spec

    @staticmethod
    def escalate(spec: ModelSpec) -> ModelSpec:
        """Return a stronger model than `spec` for retry attempts."""
        if spec.size == "haiku":
            # Promote to Sonnet, keep the role + temperature so the agent's
            # behavior is consistent.
            return ModelSpec(
                size="sonnet",
                role=spec.role + "_escalated",
                max_tokens=max(spec.max_tokens, 1500),
                temperature=spec.temperature,
                cost_per_million_input_tokens=3.0,
                cost_per_million_output_tokens=15.0,
            )
        # Already Sonnet — best we have on this tier.
        return spec
