# ClinCase — Architecture Decision Records

This directory contains the canonical Architecture Decision Records (ADRs) for ClinCase. Each ADR captures **one** non-obvious design choice, the alternatives considered, and the reason it was made — in the format a senior engineer expects to see during onboarding or a Cognizant solution architect expects to see during pilot review.

## Index

| ID | Title | Status | One-line rationale |
|---|---|---|---|
| [ADR-0001](./0001-langgraph-over-raw-orchestration.md) | Use LangGraph for the 7-agent DAG | Accepted | Conditional edges + checkpointing + topology-as-code, vs hand-rolled state machine. |
| [ADR-0002](./0002-postgres-skip-locked-queue.md) | Postgres SKIP LOCKED for the case queue | Accepted | One fewer dependency than Redis Streams / SQS, race-free at scale, RPO = primary DB. |
| [ADR-0003](./0003-per-tenant-bedrock-guardrails.md) | Per-tenant Bedrock Guardrail attached at InvokeModel | Accepted | Customer's PHI policy varies; attach at the edge, not in app code. |
| [ADR-0004](./0004-pluggable-retrieval-behind-one-schema.md) | Pluggable retrieval (Bedrock KB ↔ Q Business) behind one Pydantic schema | Accepted | Customer-onboarding velocity: drop into existing M365/SharePoint with one env flip. |
| [ADR-0005](./0005-genai-gateway-as-in-process-wrapper.md) | GenAI Gateway as in-process `LLMClient` wrapper | Accepted | Defense in depth: in-process gateway + AWS API Gateway + VPC endpoint policy + IAM. |
| [ADR-0006](./0006-exact-match-response-cache-not-semantic.md) | Exact-match SHA-256 response cache (not semantic) | Accepted | Catches retry storms (highest-value 80%); semantic cache deferred to post-pilot. |
| [ADR-0007](./0007-review-gate-as-langgraph-node.md) | HITL review_gate as a LangGraph node, not a separate workflow | Accepted | One DAG = one audit chain; SB 1120 signoff inline with the case_runs trace. |
| [ADR-0008](./0008-evidence-pack-sha256-bundle.md) | Evidence Pack as a single tamper-evident SHA-256 JSON bundle | Accepted | Auditor-grade artifact a CMS auditor can verify with one rehash; reproduces in 12 s. |

## Format

Every ADR follows the [Michael Nygard ADR format](https://github.com/joelparkerhenderson/architecture-decision-record/blob/main/locales/en/templates/decision-record-template-by-michael-nygard/index.md):

```
# Title
## Status
## Context
## Decision
## Consequences (positive · negative · neutral)
## Alternatives considered
## References
```

We don't ship ADRs for obvious choices (FastAPI for the API, Pydantic for schemas, React for the frontend). Only for choices a future maintainer might second-guess.
