# Model gateway, verification, telemetry and evaluation plans (Phases 4–9)

Everything here is **off or inert by default**; no model, region, provider or AWS resource was changed or chosen.

## Phase 4 — Bedrock hardening (`app/llm/errors.py`, `bedrock_client.py`, `gateway.py`)
* botocore failures map to typed errors (`LLMThrottledError`, `LLMTimeoutError`, `LLMUnavailableError`,
  `LLMAccessDeniedError`, `LLMModelNotFoundError`, `LLMValidationError`, `LLMQuotaError`); each carries `retryable`.
* A guardrail intervention (`stopReason=guardrail_intervened` or trace `GUARDRAIL_INTERVENED`) raises
  `LLMGuardrailBlockedError` instead of returning blocked text as a model answer (also on the stream path).
* The circuit breaker counts only retryable (provider-health) failures; input-caused failures do not trip it.
* `GenAIGateway` now passes `complete_with_image` through (Bedrock vision was unreachable) and applies the PHI
  content pre-check to `stream`.
* Tested with a stubbed boto3 client (`tests/llm`). **Not verified:** any live Bedrock call (no AWS access here).
* Still open: the clinical extractor's direct `get_llm_client().complete()` bypasses `Agent.invoke` budget/cache;
  no tool use / native structured output; per-tenant guardrail ids are stored but not applied; pricing is duplicated
  in `gateway.py` and `framework/models.py`.

## Phases 5–6 — registry and deterministic routing (`app/llm/registry.py`)
* Registry = built-ins derived from existing settings (default behaviour unchanged) + optional `MODEL_REGISTRY_JSON`
  (inline JSON or file path). Entries: provider, tier, model_id, region, status (`active|unverified|disabled`),
  prices, explicit `fallbacks`.
* `route()` is pure and deterministic. Non-`active` entries are **refused** (`ModelRoutingError`), never silently
  replaced; a fallback is used only if configured and is recorded in the decision (`fallback_from`, `considered`).
* `resolve_model_id` now goes through it. Which models to activate, in which region, is an owner decision pending AWS
  availability verification.

## Phase 7 — independent verifier (`app/verification/verifier.py`)
* Deterministic, no LLM, never reads the composer rationale: derives the verdict the criteria support, checks decisive
  verdicts carry citations and that clinical citations resolve to the FHIR bundle. `agrees=false` →
  `verification_disagreement`; dangling/missing evidence → `evidence_conflict`; both pause via the existing human-review
  flow. Results persist in `decision_verifications` (shown in the twin).
* Enabled with `VERIFIER_ENABLED=true` (default **false**). A model-based second opinion can plug into the same comparator.

## Phase 8 — telemetry
* `Agent.invoke` now opens an `agent.<name>` span with `clincase.run_id`, `clincase.trace_id`,
  `clincase.case_intelligence_id`; gateway spans already exist. These are **attributes for correlation**, not a W3C
  trace propagated across the queue boundary — the worker does not yet restore a parent context from `trace_id`.
  Not verified against a live collector.

## Phase 9 — twin
* Adds `verifications` and `cost_reconciliation` (gateway-audited spend vs framework estimate; a gap = unaudited calls
  or price drift). MCP `clinical_extract` / `audit_query` now read `agent_runs` (they queried a non-existent table).

## ECS vs EKS (evaluation only — nothing migrated)
ECS Fargate today: no cluster ops, existing task-env/secret wiring, but the demo has no DB and queue-depth scaling needs
custom CloudWatch metrics. EKS adds KEDA queue scaling, network policies and external-secrets (manifests exist, not
deployed) at the cost of cluster operations and a larger security surface. Recommendation: stay on ECS until queue-depth
autoscaling or multi-tenant isolation requirements are measured; revisit with real load data.

## Retrieval and evaluation (plan — not run)
Measure on a labelled case set: citation resolution rate (twin `integrity`), verifier agreement rate, escalation rate,
cost per case (reconciliation), retrieval hit@k per payer. No numbers are claimed because no experiment was run.
