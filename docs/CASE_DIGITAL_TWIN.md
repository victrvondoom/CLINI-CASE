# Case Digital Twin and Case Intelligence ID

`GET /api/v1/cases/{case_id}/twin` returns one auditable object describing how an authorization case
evolved: FHIR state → policy → agents → model decision → human decision → queue events → outcome.
The UI shows it on the case page (`CaseTwinPanel`).

## Design

* **A projection, not a second source of truth.** The twin is computed on each request from `cases`,
  `case_runs`, `case_jobs`, `agent_runs`, `decisions`, `appeals` and `reviewer_actions`; nothing is stored
  *for* the twin and no snapshot is kept. Run identity itself is persisted (`case_runs` plus additive,
  nullable run/case/trace columns on the run artifacts — an idempotent migration applied at API and worker
  start, see [`RUN_IDENTITY.md`](RUN_IDENTITY.md)). A field with no source is `null`; nothing is guessed.
* **Case Intelligence ID** (`CI-…`) is a namespaced SHA-256 of (organisation, case), now **stored** on `cases`
  and on every run artifact and propagated through the queue, graph, agents, model calls and SSE events — see
  [`RUN_IDENTITY.md`](RUN_IDENTITY.md). The twin is run-aware (headline = latest execution run; `runs` lists every run).
* **Evidence IDs** (`EV-…`) identify each cited item. Each carries kind, pointer, resolved FHIR
  resource type, policy version and section (parsed from the pointer), the first agent run whose
  recorded output mentions it, that run's model and timestamp, and the decision confidence.
* **Integrity check.** Every clinical citation is resolved against the submitted FHIR bundle;
  pointers that resolve to nothing are listed as `dangling_citations`.
* **Case trace.** Per-stage offset and duration from `agent_runs`, the human-review wait (or a
  "waiting" stage while a case is `awaiting_review`), token totals and an estimated cost from the
  framework's own price table.
* **Tamper evidence.** `twin_sha256` is over the canonical twin (excluding `generated_at`).
* Tenant scoped; a case in another organisation returns 404. A database failure returns 503.

## Status against the target architecture

| Element of the brief | Status in this repository |
|---|---|
| Case Intelligence ID, run identity, Case Digital Twin, evidence lineage | **Added**; identity is stored and propagated (see `RUN_IDENTITY.md`). A distributed trace is **not** built: no OpenTelemetry spans use the stored `trace_id` yet. |
| LangGraph orchestration, human review gate | Orchestration existing. The review gate only sets a flag (no LangGraph interrupt/checkpoint), `HITL_CONFIDENCE_THRESHOLD` defaults to 0.0 so it never fires by default, and `/resume` records the human decision without re-entering the graph. |
| Bedrock model gateway, guardrails, routing, cost tracking | Partial: Converse client and gateway exist; the guardrail is optional and its outcome is not consumed, there is no tool use or native structured output, and routing is a two-tier escalation. |
| Event-driven workers scaled by queue depth (KEDA) | Queue exists (`case_jobs`, Postgres `SKIP LOCKED`; ADR-0002 chose it over SQS). The KEDA manifest is a design that is not deployable as-is (see the architecture audit). |
| Amazon SQS as the queue | **Not built.** Reverses ADR-0002; needs an explicit decision (adapter + KEDA `aws-sqs-queue` scaler). |
| Bedrock AgentCore | Manifest stub only (`ops/aws/agentcore`); needs AgentCore enabled in the account. |
| OpenTelemetry / ADOT | Existing setup (`app/observability/otel.py`). `agent_span` exists but the agent framework does not call it yet, so spans are not emitted per agent today. |
| MCP tool fabric | Server exists and is authenticated and tenant-scoped; `clinical_extract` and `audit_query` still query a non-existent table, and the agents do not use MCP. |
| FHIR R4 validation / PAS | Structural validation only on the prior-auth path; PAS submit is a stub. A separate HAPI FHIR server is **not** present. |
| S3 + Textract document extraction | Textract engine exists in intake. |
| OpenSearch evidence retrieval | **Not present** (pgvector / Bedrock KB / S3 Vectors are used). |
| EKS, Argo CD, Trivy, Terraform | Manifests and workflows exist; none were deployed or executed as part of this change. |
| Next.js frontend | **Not applicable**: the UI is React + Vite; a rewrite was not done. |

Citations do not yet reference a stored source document or page, so `source_document` and `page`
are `null` until a document store is wired to the citation pipeline.
