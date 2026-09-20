"""Core types for the ClinCase production agent framework.

Hierarchy of objects an `Agent.invoke()` produces:

    AgentResult[O]
      ├── output: O                  the validated, schema-conforming result
      ├── metadata: AgentMetadata    cost / tokens / latency / retries / score
      └── trace:    AgentTrace       hierarchical span tree (parent_span_id chain)

Every cross-cutting concern (tracing, budget, retries, grader) writes into
these structures so the audit trail is rich enough to reconstruct any
decision and prove HIPAA + CMS-0057-F compliance.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Generic type vars for Agent[I, O]
I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


# =============================================================================
# Cost & token bookkeeping
# =============================================================================


class TokenUsage(BaseModel):
    """Per-model token usage. Aggregated across retries and tool-driven LLM calls."""

    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class Cost(BaseModel):
    """Dollar cost calculator. Authoritative pricing lives in ModelSpec."""

    usd: float = 0.0
    breakdown: dict[str, float] = Field(default_factory=dict)
    """Per-model breakdown: {"sonnet-4-6": 0.012, "haiku-4-5": 0.001}."""

    def __add__(self, other: Cost) -> Cost:
        merged = dict(self.breakdown)
        for k, v in other.breakdown.items():
            merged[k] = merged.get(k, 0.0) + v
        return Cost(usd=self.usd + other.usd, breakdown=merged)

    def __ge__(self, other: float) -> bool:  # type: ignore[override]
        return self.usd >= other


# =============================================================================
# Tracing — hierarchical span tree
# =============================================================================


class SpanKind(str, Enum):
    AGENT = "agent"           # parent agent invocation
    SUB_AGENT = "sub_agent"   # child agent invocation
    TOOL_CALL = "tool_call"   # tool/function call
    LLM_CALL = "llm_call"     # raw LLM completion call
    GUARDRAIL = "guardrail"   # input/output guardrail check
    GRADER = "grader"         # self-evaluation pass


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    RETRYING = "retrying"


class AgentTrace(BaseModel):
    """One node in the hierarchical execution trace.

    Same shape as an OpenTelemetry span: span_id + parent_span_id make the
    tree, and `events` carries point-in-time facts. The audit UI renders this
    as a flame graph.
    """

    span_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent_span_id: uuid.UUID | None = None
    case_id: str
    name: str
    kind: SpanKind
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    latency_ms: int | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    children: list[AgentTrace] = Field(default_factory=list)

    def add_event(self, name: str, **attrs: Any) -> None:
        self.events.append({
            "name": name,
            "ts": datetime.now(UTC).isoformat(),
            **attrs,
        })

    def finalize(self, status: SpanStatus = SpanStatus.OK) -> None:
        self.finished_at = datetime.now(UTC)
        self.latency_ms = int((self.finished_at - self.started_at).total_seconds() * 1000)
        self.status = status


# =============================================================================
# Per-invocation metadata
# =============================================================================


class AgentMetadata(BaseModel):
    """Per-invocation rollup of cost, latency, retries, grader score, etc.

    Persisted to `agent_runs` plus exposed in `AgentResult.metadata` so the
    caller can render telemetry without re-querying the DB.
    """

    model_config = ConfigDict(protected_namespaces=())

    invocation_id: uuid.UUID
    parent_invocation_id: uuid.UUID | None
    agent_name: str
    case_id: str

    started_at: datetime
    finished_at: datetime
    latency_ms: int

    cost: Cost = Field(default_factory=Cost)
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    model_id: str | None = None
    model_size_used: Literal["sonnet", "haiku", "deterministic"] = "sonnet"

    retries: int = 0
    grader_score: float | None = None
    quality_threshold: float | None = None

    sub_invocations: list[uuid.UUID] = Field(default_factory=list)

    status: SpanStatus = SpanStatus.OK
    error: str | None = None

    idempotency_key: str | None = None
    cache_hit: bool = False


# =============================================================================
# AgentResult: what every Agent.invoke() returns
# =============================================================================


class AgentResult(BaseModel, Generic[O]):
    """Wrap an agent's typed output with full metadata + trace.

    Callers downstream pull `.output` for the typed payload; the audit UI,
    cost dashboard, and reflection grader pull `.metadata` and `.trace`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: O
    metadata: AgentMetadata
    trace: AgentTrace
