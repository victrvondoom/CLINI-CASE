# ADR-0001 — Use LangGraph for the 7-agent DAG

## Status
Accepted · 2026-04-12

## Context

The ClinCase 7-agent oncology PA pipeline has **conditional edges** that don't fit a linear sequence:

- After `necessity_reasoner`, the DAG branches on `overall_confidence < HITL_CONFIDENCE_THRESHOLD` → `review_gate` (terminal).
- After `decision_composer`, the DAG branches on `verdict == DENY` → `denial_forecaster` → `appeals_drafter`, otherwise direct to `patient_communicator`.
- A paused (HITL-routed) case must **resume** mid-graph after the reviewer signs off.

Three serious orchestration options were on the table:

1. **Hand-rolled async Python state machine** — full control, no dependencies.
2. **LangGraph 0.2.x** (StateGraph, conditional edges, checkpointing).
3. **Bedrock Agents** (managed action groups, native AgentCore support).

## Decision

**LangGraph 0.2.x.**

The DAG topology lives in `app/graph/build.py` as declarative `add_node` / `add_conditional_edges` calls. State is the single `ClinCaseState` Pydantic model. Conditional edges drive the HITL pause and DENY-path branch.

## Consequences

**Positive**
- DAG topology is **inspectable** (`graph.get_graph().draw_mermaid()`); a solution architect can read the architecture from the code in 30 seconds.
- Checkpointing comes for free — a stalled case resumes mid-graph after a deploy without bespoke state-machine logic.
- Existing Anthropic + LangGraph documentation is the second-largest agentic-orchestration corpus on GitHub; junior engineers ramp fast.
- AWS Bedrock AgentCore (GA Oct 2025) is **framework-agnostic and explicitly supports LangGraph** — porting to AgentCore Runtime is configuration, not a rewrite (`ops/aws/agentcore/deployment.yaml`).

**Negative**
- LangGraph adds a dependency we'd otherwise not need.
- LangGraph's pinned LangChain version sometimes lags model updates; we mitigate via the `LLMClient` ABC + GenAI Gateway, which keep model-version churn out of LangGraph's path.

**Neutral**
- Performance is identical to a hand-rolled state machine at our scale (DAG run is dominated by Bedrock latency, not orchestration).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Hand-rolled async state machine | No checkpointing primitive; conditional edges become if/else mazes; Agent Foundry can't ingest a hand-rolled DAG as a recognizable agent network. |
| Bedrock Agents (managed) | Forces the action-group config model; doesn't support arbitrary Python orchestration; reflection-with-grader pattern is awkward to express. We do plan to map our 7 parents onto AgentCore Runtimes for production deployment (`ops/aws/agentcore/deployment.yaml`) — but that's *runtime fan-out*, not the orchestration substrate. |
| Microsoft Semantic Kernel | Not Bedrock-native; would need a Python-binding shim. |

## References

- AWS Bedrock AgentCore framework-agnostic support: https://aws.amazon.com/bedrock/agentcore/
- DAG file: `backend/app/graph/build.py`
- Apply-ready AgentCore mapping: `ops/aws/agentcore/deployment.yaml`
