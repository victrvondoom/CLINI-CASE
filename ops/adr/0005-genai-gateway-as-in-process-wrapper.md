# ADR-0005 — GenAI Gateway as in-process `LLMClient` wrapper

## Status
Accepted · 2026-05-02

## Context

AWS's published guidance for production Bedrock is *"API Gateway as governed entry point with IAM, quotas, network controls"* (AWS Architecture blog, Bedrock category). The literal AWS API Gateway sits in front of Bedrock at the network layer (VPC endpoints, IAM policies, per-model-id conditions — covered by ADR-0008 + the Terraform module `ops/terraform/bedrock-vpc-endpoint/`).

But the application also needs **in-process enforcement** for things AWS API Gateway doesn't see:

- Per-tenant 24h **rolling** token + USD quota (not per-request rate limit).
- Content-safety pre-check before the call leaves our process.
- **Per-call audit row** with the exact `(organization_id, case_id, agent_name, model_id, tokens, cost)` — pivot for Evidence Pack reproduction.
- **Per-tenant model allowlist** (a tenant may only invoke their declared models).

These need an *application-layer* gateway. Two options were on the table:

1. Add enforcement individually inside each agent (BudgetTracker, Guardrails, etc. as ad-hoc additions).
2. Compose a single named **GenAI Gateway** that wraps the underlying `LLMClient` and runs all enforcement uniformly.

## Decision

**The GenAI Gateway is a single class (`app/llm/gateway.py:GenAIGateway`) that implements `LLMClient` and wraps the configured underlying client.**

The factory (`app/llm/factory.py`) returns `GenAIGateway(BedrockClient())` instead of `BedrockClient()`. Every existing call site keeps working (same `LLMClient` interface). Tenant scope is passed via a `ContextVar` set at the start of `Agent.invoke()` and reset on exit.

## Consequences

**Positive**
- **Single audit point for every Bedrock call.** A CISO audits `app/llm/gateway.py` and the `llm_invocations` table — not 28 agent files.
- **Defense in depth.** AWS API Gateway (planned for prod) + AWS VPC endpoint policy + IAM least-privilege role + Gateway in-process enforcement + per-agent guardrails. Five layers; a bug in any one doesn't make a leak.
- **Provider-agnostic.** Wraps Bedrock today; tomorrow wraps Anthropic-direct, OpenRouter, or AgentCore Runtime — same enforcement applies.
- **Test mocks unchanged.** The `LLMClient` ABC was the test-mock contract before; it still is. Existing tests don't break.
- **Per-tenant policy live in DB.** `tenant_policies` table is editable per customer via ops API; no code change to tighten a quota.

**Negative**
- **One more class to read** to understand a Bedrock call. Mitigated by a long docstring at the top of `app/llm/gateway.py` explaining every enforcement step.
- **ContextVar can be footgun-prone.** A test that doesn't reset the context could leak tenant scope to the next test. Mitigated by `Agent.invoke()`'s `try/finally` always resetting.

**Neutral**
- Adds ~5 ms / call (one Postgres SELECT for the policy + one SELECT for the rolling quota). At p50 52 s / case dominated by Bedrock latency, this is statistical noise.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Per-agent enforcement | Cross-cutting concerns scattered across 28 files; impossible to tighten policy without touching every file. The whole point of "Gateway" is to centralize this. |
| AWS API Gateway only (no in-process) | API Gateway can't see per-tenant rolling token caps spanning a 24h window. It rate-limits per-request only. The two layers are complementary, not duplicative. |
| Bedrock AgentCore Gateway only | AgentCore Gateway is the network-edge analog of the in-process Gateway. Both should exist; in-process catches what AgentCore doesn't (per-call audit attribution, content-safety sniff). When AgentCore Runtime ships in prod (`ops/aws/agentcore/deployment.yaml`) it pairs with this Gateway, not replaces it. |
| Bedrock Provisioned Throughput as the rate limit | PT is a capacity primitive, not a per-tenant policy primitive. PT splits capacity across tenants; the Gateway enforces that any one tenant doesn't exhaust it. |

## References

- AWS Architecture blog (Bedrock category): https://aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/
- Implementation: `backend/app/llm/gateway.py`
- Factory wiring: `backend/app/llm/factory.py`
- Tenant context propagation: `backend/app/agents/framework/agent.py`
- Network-edge counterpart: `ops/terraform/bedrock-vpc-endpoint/`
- Live introspection: `GET /api/v1/llm-gateway/usage` · `GET /api/v1/llm-gateway/policy`
