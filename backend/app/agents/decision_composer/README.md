# Decision Composer

Parent agent #4 of 7. Deterministic verdict + LLM-written rationale + LLM-validated citation chain.

## Package layout

```
decision_composer/
├── __init__.py        public exports
├── orchestrator.py    Decision ComposerAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `verdict_synthesizer` | deterministic | — | Maps a NecessityAssessment to APPROVE / DENY / REFER and emits a full audit trace of which rule fired. No LLM. Microsecond latency. Byte-for-byte replayable. |
| `rationale_writer` | LLM (sonnet) | — | Composes a 2–4 sentence executive rationale paragraph that justifies the (already-determined) verdict using snapshot fields and policy phrases. |
| `citation_linker` | LLM (haiku) | — | Builds the citation chain so every factual claim in the rationale points to either a clinical evidence resource or a policy excerpt. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[DecisionComposerOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.decision_composer import (
    decision_composer,                      # the parent agent instance
    decision_composer_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`decision_composer`) plus one row per sub-agent invocation (`decision_composer.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
