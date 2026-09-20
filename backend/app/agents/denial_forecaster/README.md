# Denial Forecaster

Parent agent #5 of 7. Predicts the *payer's* denial probability + top likely reasons + recommended appeal angle (KFF-2024 calibrated).

## Package layout

```
denial_forecaster/
├── __init__.py        public exports
├── orchestrator.py    Denial ForecasterAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `probability_estimator` | LLM (sonnet) | — | Base-rate-calibrated payer-denial probability ∈ [0,1] anchored against MA / oncology-PA denial rates. Outputs estimator_confidence and a one-line summary. |
| `reason_predictor` | LLM (haiku) | — | Up to 3 ranked payer denial rationales with policy-section pointers; empty when denial_probability < 0.15. |
| `appeal_path_recommender` | LLM (haiku) | — | Recommends the best appeal angle (enum) + KFF-baseline-calibrated overturn probability when denial probability ≥ 0.35; otherwise skipped with a reason. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[DenialForecasterOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.denial_forecaster import (
    denial_forecaster,                      # the parent agent instance
    denial_forecaster_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`denial_forecaster`) plus one row per sub-agent invocation (`denial_forecaster.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
