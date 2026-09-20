"""AgentContext — the per-case object threaded through every agent invocation.

Production agents need a unified context that carries:
  • case_id + organization_id        (data scoping)
  • request_id                       (idempotency)
  • parent_span_id                   (tracing chain)
  • budget tracker                   (cost / latency / token enforcement)
  • trace_sink                       (where agent_runs rows + SSE events go)

The context is created at the top of the case (in `cases.run_full` or the
HITL resume endpoint) and passed down. Sub-agents inherit the same context
but record their own span_id under the parent_span_id chain.

ONE context per case. The framework's per-case budget claim only holds
because every parent and sub-agent draws from the same `BudgetTracker`
on this single object. Creating multiple contexts per case breaks the
ceiling invariant.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.framework.budget import BudgetTracker, new_default_budget
from app.agents.framework.types import AgentTrace

if TYPE_CHECKING:
    from app.agents.framework.trace_sink import TraceSink


@dataclass
class AgentContext:
    """Per-case agent invocation context.

    Construct ONE per case at the entry point. Pass to every Agent.invoke().
    Sub-agents inherit the same context (`child_for(span)` forks parent_span_id
    only — budget, trace_sink, working memory are SHARED).
    """

    case_id: str
    organization_id: str
    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    parent_span_id: uuid.UUID | None = None

    budget: BudgetTracker = field(default_factory=new_default_budget)

    # The trace sink is set by the entry-point factory `new_agent_context`.
    # Type-only-imported above to avoid circular import.
    trace_sink: TraceSink = field(default=None)  # type: ignore[assignment]

    # Per-invocation scratchpad — lives only as long as the context.
    working_memory: dict[str, Any] = field(default_factory=dict)

    # Root trace tree node — every span attaches under this
    root_trace: AgentTrace | None = None

    correlation: dict[str, str] = field(default_factory=dict)
    """OpenTelemetry-style baggage; propagates through the agent stack."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def child_for(self, span: AgentTrace) -> AgentContext:
        """Return a child context with parent_span_id set to span.span_id.

        Shares everything else (budget, trace_sink, working memory,
        root_trace) so sub-agent invocations charge the same per-case
        budget and emit traces under the same root tree.
        """
        return AgentContext(
            case_id=self.case_id,
            organization_id=self.organization_id,
            request_id=self.request_id,
            parent_span_id=span.span_id,
            budget=self.budget,
            trace_sink=self.trace_sink,
            working_memory=self.working_memory,
            root_trace=self.root_trace,
            correlation=dict(self.correlation),
        )

    def attach_root_trace(self, span: AgentTrace) -> None:
        if self.root_trace is None:
            self.root_trace = span

    def snapshot(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "organization_id": self.organization_id,
            "request_id": str(self.request_id),
            "parent_span_id": str(self.parent_span_id) if self.parent_span_id else None,
            "budget": self.budget.snapshot(),
            "correlation": self.correlation,
        }


def new_agent_context(
    *,
    case_id: str,
    organization_id: str,
    budget: BudgetTracker | None = None,
    trace_sink: TraceSink | None = None,
) -> AgentContext:
    """Factory at the top of every case. Use this — never construct directly."""
    from app.agents.framework.trace_sink import PostgresTraceSink

    return AgentContext(
        case_id=case_id,
        organization_id=organization_id,
        budget=budget or new_default_budget(),
        trace_sink=trace_sink or PostgresTraceSink(),
    )
