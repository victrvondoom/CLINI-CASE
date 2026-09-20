# Necessity Reasoner

Parent agent #3 of 7. Per-criterion MET/NOT_MET/AMBIGUOUS evaluation with calibrated confidence. Parallel fan-out across atomic criteria. Drives the HITL gate.

## Package layout

```
necessity_reasoner/
├── __init__.py        public exports
├── orchestrator.py    Necessity ReasonerAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `criterion_splitter` | LLM (sonnet) | — | Splits multi-clause policy criteria into atomic, individually-checkable statements with type tags (inclusion/exclusion) and section pointers. |
| `evidence_matcher` | LLM (sonnet) | reflection 0.8 | For ONE atomic criterion, decides MET / NOT_MET / AMBIGUOUS against the ClinicalSnapshot with cited supporting evidence. Self-grades and retries if the grader flags hallucinated facts or weak evidence. |
| `confidence_calibrator` | LLM (haiku) | — | Calibrates per-criterion confidence ∈ [0,1] and aggregates to overall (deterministic min — enforced post-LLM). Drives the HITL gate threshold. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[NecessityReasonerOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.necessity_reasoner import (
    necessity_reasoner,                      # the parent agent instance
    necessity_reasoner_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`necessity_reasoner`) plus one row per sub-agent invocation (`necessity_reasoner.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
