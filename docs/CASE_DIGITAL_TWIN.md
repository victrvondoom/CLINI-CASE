# Case Digital Twin and Case Intelligence ID

`GET /api/v1/cases/{case_id}/twin` returns one auditable object describing how an authorization case
evolved: FHIR state → policy → agents → model decision → human decision → queue events → outcome.
The UI shows it on the case page (`CaseTwinPanel`).

## Design

* **Derived, not stored.** The twin is a projection over `cases`, `case_jobs`, `agent_runs`,
  `decisions`, `appeals` and `reviewer_actions`. There is no new table, no second source of truth and
  no migration. A field with no source is `null`; nothing is guessed.
* **Case Intelligence ID** (`CI-…`) is a namespaced SHA-256 of (organisation, case). Any component that
  knows both computes the same value, so it can tag logs, spans and events without coordination.
  `agent_span` adds it as `clincase.case_intelligence_id` when OpenTelemetry is enabled.
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
| Case Intelligence ID, Case Digital Twin, evidence lineage, single case trace | **Added** (this change). |
| LangGraph orchestration, human review gate | Existing, unchanged. |
| Bedrock model gateway, guardrails, routing, cost tracking | Existing (`app/llm`, guardrails, `ModelRouter`). |
| Event-driven workers scaled by queue depth (KEDA) | Existing: `case_jobs` Postgres `SKIP LOCKED` queue + `ops/k8s/keda`. ADR-0002 chose this over SQS deliberately. |
| Amazon SQS as the queue | **Not built.** Reverses ADR-0002; needs an explicit decision (adapter + KEDA `aws-sqs-queue` scaler). |
| Bedrock AgentCore | Manifest stub only (`ops/aws/agentcore`); needs AgentCore enabled in the account. |
| OpenTelemetry / ADOT | Existing setup (`app/observability/otel.py`). `agent_span` exists but the agent framework does not call it yet, so spans are not emitted per agent today. |
| MCP tool fabric | Existing server (`app/mcp`). |
| FHIR R4 validation / PAS | Existing. A separate HAPI FHIR server is **not** present. |
| S3 + Textract document extraction | Textract engine exists in intake. |
| OpenSearch evidence retrieval | **Not present** (pgvector / Bedrock KB / S3 Vectors are used). |
| EKS, Argo CD, Trivy, Terraform | Manifests and workflows exist; none were deployed or executed as part of this change. |
| Next.js frontend | **Not applicable**: the UI is React + Vite; a rewrite was not done. |

Citations do not yet reference a stored source document or page, so `source_document` and `page`
are `null` until a document store is wired to the citation pipeline.
