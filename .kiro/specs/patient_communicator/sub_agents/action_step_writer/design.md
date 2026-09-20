# Design — `action_step_writer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.355021+00:00.

## Architecture

This agent is a **sub-agent** of `patient_communicator`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`ActionStepWriterInput`)

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

## Output schema (`ActionStepWriterOutput`)

```json
{
  "$defs": {
    "PatientNextStep": {
      "description": "One concrete action the patient or caregiver can take.",
      "properties": {
        "step_number": {
          "maximum": 10,
          "minimum": 1,
          "title": "Step Number",
          "type": "integer"
        },
        "text": {
          "description": "One imperative sentence, plain language.",
          "title": "Text",
          "type": "string"
        },
        "timing": {
          "default": "this_week",
          "enum": [
            "today",
            "this_week",
            "this_month",
            "after_decision"
          ],
          "title": "Timing",
          "type": "string"
        }
      },
      "required": [
        "step_number",
        "text"
      ],
      "title": "PatientNextStep",
      "type": "object"
    }
  },
  "properties": {
    "next_steps": {
      "items": {
        "$ref": "#/$defs/PatientNextStep"
      },
      "maxItems": 5,
      "title": "Next Steps",
      "type": "array"
    }
  },
  "title": "ActionStepWriterOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `ActionStepWriterInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `ActionStepWriterOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="action_step_writer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
