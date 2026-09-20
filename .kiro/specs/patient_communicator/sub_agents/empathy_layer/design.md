# Design — `empathy_layer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.351314+00:00.

## Architecture

This agent is a **sub-agent** of `patient_communicator`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`EmpathyLayerInput`)

```json
{
  "$defs": {
    "AppealArgument": {
      "properties": {
        "contested_criterion": {
          "title": "Contested Criterion",
          "type": "string"
        },
        "payer_position": {
          "title": "Payer Position",
          "type": "string"
        },
        "counter_position": {
          "title": "Counter Position",
          "type": "string"
        },
        "cited_evidence": {
          "items": {
            "type": "string"
          },
          "title": "Cited Evidence",
          "type": "array"
        },
        "cited_policy_text": {
          "title": "Cited Policy Text",
          "type": "string"
        },
        "cited_guideline": {
          "title": "Cited Guideline",
          "type": "string"
        }
      },
      "required": [
        "contested_criterion",
        "payer_position",
        "counter_position",
        "cited_evidence",
        "cited_policy_text",
        "cited_guideline"
      ],
      "title": "AppealArgument",
      "type": "object"
    },
    "AppealDraft": {
      "properties": {
        "patient_initials": {
          "title": "Patient Initials",
          "type": "string"
        },
        "payer_id": {
          "title": "Payer Id",
          "type": "string"
        },
        "requested_treatment": {
          "title": "Requested Treatment",
          "type": "string"
        },
        "denial_date": {
          "title": "Denial Date",
          "type": "string"
        },
        "appeal_body
```

## Output schema (`EmpathyLayerOutput`)

```json
{
  "properties": {
    "headline": {
      "title": "Headline",
      "type": "string"
    },
    "body": {
      "description": "2\u20134 short paragraphs, plain language, no jargon.",
      "title": "Body",
      "type": "string"
    },
    "tone": {
      "enum": [
        "reassuring",
        "neutral",
        "urgent"
      ],
      "title": "Tone",
      "type": "string"
    }
  },
  "required": [
    "headline",
    "body",
    "tone"
  ],
  "title": "EmpathyLayerOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `EmpathyLayerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `EmpathyLayerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `sonnet` (patient_voice)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="empathy_layer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
