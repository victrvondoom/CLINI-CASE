# ClinCase Architecture (top-level pointer)

This file is the front door for "show me the architecture." It points at the canonical docs.

## TL;DR

ClinCase is a **5-named-layer enterprise architecture** with explicit AWS-pattern alignment, live introspection, and a per-tenant governed GenAI Gateway.

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  1.  EXPERIENCE LAYER       â€” React 18 SPA Â· 17 routes Â· SSE trace       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  2.  ORCHESTRATION & POLICY ENGINE                                       â”‚
â”‚      FastAPI Â· LangGraph 7-agent DAG Â· BudgetTracker Â· review_gate HITL  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  3.  CONTEXT RETRIEVAL SERVICE  ("agentic capital")                      â”‚
â”‚      Bedrock KB / Amazon Q Business / S3 Vectors  (one Pydantic schema)  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  4.  GENAI GATEWAY                                                       â”‚
â”‚      Per-tenant model allowlist Â· 24h quota Â· audit log Â· Bedrock VPCe   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  5.  TELEMETRY & GOVERNANCE                                              â”‚
â”‚      Prometheus /metrics Â· 7 SLOs Â· Evidence Pack SHA-256 Â· Model Card   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                  â”‚
                                  â–¼
                       AWS Foundation
                       (Bedrock + Claude Sonnet 4.6 + Haiku 4.5 +
                        AgentCore Runtime + Aurora Global + KMS multi-region)
```

## Where to look

| You want to know | Doc |
|---|---|
| The 5 layers in detail | [`ops/architecture/TARGET_ARCHITECTURE.md`](ops/architecture/TARGET_ARCHITECTURE.md) |
| Per-component business outcomes | [`ops/architecture/BUSINESS_USE_CASE.md`](ops/architecture/BUSINESS_USE_CASE.md) |
| Why each design choice was made | [`ops/adr/`](ops/adr/) â€” 8 canonical ADRs |
| Mermaid + ASCII diagrams | [`docs/ARCHITECTURE_DIAGRAM.md`](docs/ARCHITECTURE_DIAGRAM.md) |
| AI velocity gap framing | [`ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md`](ops/industrialization/AI_VELOCITY_GAP_BUSINESS_CASE.md) |
| AI adaptation gap framing | [`ops/architecture/AI_ADAPTATION_GAP.md`](ops/architecture/AI_ADAPTATION_GAP.md) |
| Goal â†’ agent network â†’ actions â†’ outcome | [`ops/architecture/AGENTIC_ACTIONS.md`](ops/architecture/AGENTIC_ACTIONS.md) |
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

Frontend visualizations: `/architecture` Â· `/industrialize` Â· `/compliance` Â· `/roi`.
