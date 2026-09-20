# Design — `reading_level_tuner`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.353023+00:00.

## Architecture

This agent is a **sub-agent** of `patient_communicator`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`ReadingLevelTunerInput`)

```json
{
  "properties": {
    "headline": {
      "title": "Headline",
      "type": "string"
    },
    "body": {
      "title": "Body",
      "type": "string"
    },
    "target_grade": {
      "default": 7.0,
      "maximum": 12.0,
      "minimum": 3.0,
      "title": "Target Grade",
      "type": "number"
    }
  },
  "required": [
    "headline",
    "body"
  ],
  "title": "ReadingLevelTunerInput",
  "type": "object"
}
```

## Output schema (`ReadingLevelTunerOutput`)

```json
{
  "properties": {
    "grade": {
      "description": "Computed Flesch-Kincaid grade level.",
      "title": "Grade",
      "type": "number"
    },
    "meets_target": {
      "title": "Meets Target",
      "type": "boolean"
    },
    "body_with_substitutions": {
      "description": "Body with banned-phrase substitutions applied (we regret\u2026 \u2192 straight talk).",
      "title": "Body With Substitutions",
      "type": "string"
    }
  },
  "required": [
    "grade",
    "meets_target",
    "body_with_substitutions"
  ],
  "title": "ReadingLevelTunerOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- _(none configured)_

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `ReadingLevelTunerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `ReadingLevelTunerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="reading_level_tuner",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
