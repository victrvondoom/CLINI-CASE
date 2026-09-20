"""ClinCase production agent framework — public surface.

Modules:
  agent       — Agent[I, O] base class, full production lifecycle
  budget      — BudgetTracker (reservation pattern, BudgetExceeded)
  context     — AgentContext (per-case state threaded through invocations)
  grader      — LLMGrader (self-evaluation pattern for reflection)
  guardrails  — Guardrail ABC + concrete impls (Schema, PHI, Citation, Token-budget)
  models      — ModelSpec + ModelRouter (Haiku → Sonnet escalation)
  trace_sink  — TraceSink ABC + Postgres / InMemory impls
  types       — AgentResult, AgentMetadata, AgentTrace, Cost, TokenUsage
"""
from app.agents.framework.agent import (
    Agent,
    AgentExhausted,
    InputBlocked,
    OutputBlocked,
)
from app.agents.framework.budget import (
    BudgetExceeded,
    BudgetTracker,
    new_default_budget,
)
from app.agents.framework.context import (
    AgentContext,
    new_agent_context,
)
from app.agents.framework.grader import (
    GraderInput,
    GraderScore,
    LLMGrader,
    get_default_grader,
)
from app.agents.framework.guardrails import (
    CitationCompletenessGuardrail,
    Guardrail,
    GuardrailDecision,
    GuardrailResult,
    PHIInputGuardrail,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)
from app.agents.framework.models import (
    HAIKU_GRADER,
    HAIKU_LITE,
    SONNET_LETTER,
    SONNET_LONG_JSON,
    SONNET_MEDIUM_JSON,
    SONNET_REASONING,
    ModelRouter,
    ModelSpec,
    estimate_cost,
    resolve_model_id,
)
from app.agents.framework.trace_sink import (
    InMemoryTraceSink,
    PostgresTraceSink,
    TraceSink,
)
from app.agents.framework.types import (
    AgentMetadata,
    AgentResult,
    AgentTrace,
    Cost,
    SpanKind,
    SpanStatus,
    TokenUsage,
)
