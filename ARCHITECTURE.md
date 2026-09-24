# ClinCase Architecture (top-level pointer)

This file is the front door for "show me the architecture." It points at the canonical docs.

## TL;DR

ClinCase is a **5-named-layer enterprise architecture** with explicit AWS-pattern alignment, live introspection, and a per-tenant governed GenAI Gateway.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  1.  EXPERIENCE LAYER       — React 18 SPA · 17 routes · SSE trace       │
├──────────────────────────────────────────────────────────────────────────┤
│  2.  ORCHESTRATION & POLICY ENGINE                                       │
│      FastAPI · LangGraph 7-agent DAG · BudgetTracker · review_gate HITL  │
├──────────────────────────────────────────────────────────────────────────┤
│  3.  CONTEXT RETRIEVAL SERVICE  ("agentic capital")                      │
│      Bedrock KB / Amazon Q Business / S3 Vectors  (one Pydantic schema)  │
├──────────────────────────────────────────────────────────────────────────┤
│  4.  GENAI GATEWAY                                                       │
│      Per-tenant model allowlist · 24h quota · audit log · Bedrock VPCe   │
├──────────────────────────────────────────────────────────────────────────┤
│  5.  TELEMETRY & GOVERNANCE                                              │
│      Prometheus /metrics · 7 SLOs · Evidence Pack SHA-256 · Model Card   │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                       AWS Foundation
                       (Bedrock + Claude Sonnet 4.6 + Haiku 4.5 +
                        AgentCore Runtime + Aurora Global + KMS multi-region)
```

## Where to look

| You want to know | Doc |
|---|---|
| The 5 layers in detail | [`ops/architecture/TARGET_ARCHITECTURE.md`](ops/architecture/TARGET_ARCHITECTURE.md) |
| Per-component business outcomes | [`ops/architecture/BUSINESS_USE_CASE.md`](ops/architecture/BUSINESS_USE_CASE.md) |
| Why each design choice was made | [`ops/adr/`](ops/adr/) — 8 canonical ADRs |
| Mermaid + ASCII diagrams | [`docs/ARCHITECTURE_DIAGRAM.md`](docs/ARCHITECTURE_DIAGRAM.md) |
| AI adaptation gap framing | [`ops/architecture/AI_ADAPTATION_GAP.md`](ops/architecture/AI_ADAPTATION_GAP.md) |
| Goal → agent network → actions → outcome | [`ops/architecture/AGENTIC_ACTIONS.md`](ops/architecture/AGENTIC_ACTIONS.md) |
| Q vs Bedrock division of roles | [`ops/architecture/Q_vs_BEDROCK.md`](ops/architecture/Q_vs_BEDROCK.md) |
| Neuro-SAN AAOSA network | [`ops/neuro-san-integration/clincase-network.hocon`](ops/neuro-san-integration/clincase-network.hocon) |
| Agent Foundry manifest | [`ops/agent-foundry/agent-foundry-manifest.yaml`](ops/agent-foundry/agent-foundry-manifest.yaml) |
| AWS Bedrock AgentCore deployment | [`ops/aws/agentcore/deployment.yaml`](ops/aws/agentcore/deployment.yaml) |

## Live introspection

```bash
curl localhost:8000/api/v1/architecture/layers       # 5-layer descriptor
curl localhost:8000/api/v1/foundry/manifest          # Foundry compatibility
curl localhost:8000/api/v1/responsible-ai/model-card # NIST + ISO 42001 + EU AI Act
curl localhost:8000/api/v1/healthz/deep              # per-layer self-check
```

Frontend visualizations: `/architecture` · `/industrialize` · `/compliance` · `/roi`.
