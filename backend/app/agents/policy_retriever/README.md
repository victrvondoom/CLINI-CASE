# Policy Retriever

Parent agent #2 of 7. Fetches the top-5 payer-specific PA policy sections relevant to this case from the 21-policy corpus (Bedrock KB in production).

## Package layout

```
policy_retriever/
├── __init__.py        public exports
├── orchestrator.py    Policy RetrieverAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `keyword_filter` | deterministic | — | Iterates the curated 21-policy corpus and returns all (policy, section) pairs whose payer matches and whose treatment_keywords fuzzy-match the requested treatment name. Pure Python, no LLM. |
| `llm_reranker` | LLM (sonnet) | — | Cross-encoder LLM rerank — fires only when keyword_filter returns >5 candidates. Outputs the top-K most-relevant indices for the case. |
| `citation_resolver` | deterministic | — | Deterministic mapping from ranked candidate indices to fully-pointered PolicyExcerpt objects (source URL, page number, section heading, decreasing relevance score). No LLM. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[PolicyRetrieverOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.policy_retriever import (
    policy_retriever,                      # the parent agent instance
    policy_retriever_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`policy_retriever`) plus one row per sub-agent invocation (`policy_retriever.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
