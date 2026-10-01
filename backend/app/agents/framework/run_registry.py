"""Per-run shared `AgentContext` registry.

LangGraph rebuilds the pydantic state for every node, so a context stored on the state instance is lost
between nodes — each parent used to get a fresh budget and request id. The registry keys one context per
(run, job attempt) for the lifetime of a graph execution, giving every node the SAME budget, trace sink and
identity. Callers MUST `release()` in a `finally` (the worker and the sync run endpoint do).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.framework.context import AgentContext
    from app.identity import RunIdentity

_CONTEXTS: dict[tuple[str, int], AgentContext] = {}


def _key(identity: RunIdentity) -> tuple[str, int]:
    return identity.run_id, identity.job_attempt


def get_or_create(identity: RunIdentity) -> AgentContext:
    from app.agents.framework.context import new_agent_context

    key = _key(identity)
    ctx = _CONTEXTS.get(key)
    if ctx is None:
        ctx = new_agent_context(
            case_id=identity.case_id, organization_id=identity.organization_id, identity=identity
        )
        _CONTEXTS[key] = ctx
    return ctx


def peek(identity: RunIdentity) -> AgentContext | None:
    return _CONTEXTS.get(_key(identity))


def run_cost(identity: RunIdentity) -> tuple[float, float]:
    """(USD spent, seconds elapsed) from the run's shared context; (0.0, 0.0) if there is none."""
    ctx = _CONTEXTS.get(_key(identity))
    if ctx is None:
        return 0.0, 0.0
    try:
        return float(ctx.budget.spent_usd), float(ctx.budget.elapsed_ms) / 1000.0
    except Exception:  # noqa: BLE001 - cost reporting must never fail a run
        return 0.0, 0.0


def release(identity: RunIdentity) -> None:
    _CONTEXTS.pop(_key(identity), None)


def active_count() -> int:
    return len(_CONTEXTS)
