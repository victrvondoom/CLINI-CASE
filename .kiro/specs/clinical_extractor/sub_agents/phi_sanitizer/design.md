# Design — `phi_sanitizer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.321388+00:00.

## Architecture

This agent is a **sub-agent** of `clinical_extractor`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`PHISanitizerInput`)

```json
{
  "properties": {
    "text": {
      "title": "Text",
      "type": "string"
    }
  },
  "required": [
    "text"
  ],
  "title": "PHISanitizerInput",
  "type": "object"
}
```

## Output schema (`PHISanitizerOutput`)

```json
{
  "$defs": {
    "PHIMask": {
      "properties": {
        "type": {
          "enum": [
            "NAME",
            "DOB",
            "MRN",
            "SSN",
            "PHONE",
            "ADDRESS",
            "EMAIL"
          ],
          "title": "Type",
          "type": "string"
        },
        "masked_value": {
          "title": "Masked Value",
          "type": "string"
        },
        "char_offset": {
          "title": "Char Offset",
          "type": "integer"
        }
      },
      "required": [
        "type",
        "masked_value",
        "char_offset"
      ],
      "title": "PHIMask",
      "type": "object"
    }
  },
  "properties": {
    "sanitized_text": {
      "title": "Sanitized Text",
      "type": "string"
    },
    "masks": {
      "items": {
        "$ref": "#/$defs/PHIMask"
      },
      "title": "Masks",
      "type": "array"
    },
    "bedrock_guardrail_compatible": {
      "default": true,
      "title": "Bedrock Guardrail Compatible",
      "type": "boolean"
    }
  },
  "required": [
    "sanitized_text"
  ],
  "title": "PHISanitizerOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- _(none configured)_

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `PHISanitizerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `PHISanitizerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="phi_sanitizer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
