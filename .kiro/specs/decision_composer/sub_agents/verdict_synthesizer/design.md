# Design — `verdict_synthesizer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.328021+00:00.

## Architecture

This agent is a **sub-agent** of `decision_composer`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`VerdictSynthesizerInput`)

```json
{
  "$defs": {
    "CriterionAssessment": {
      "properties": {
        "criterion_text": {
          "title": "Criterion Text",
          "type": "string"
        },
        "criterion_type": {
          "default": "inclusion",
          "enum": [
            "inclusion",
            "exclusion"
          ],
          "title": "Criterion Type",
          "type": "string"
        },
        "policy_excerpt_index": {
          "title": "Policy Excerpt Index",
          "type": "integer"
        },
        "status": {
          "enum": [
            "MET",
            "NOT_MET",
            "AMBIGUOUS"
          ],
          "title": "Status",
          "type": "string"
        },
        "supporting_evidence": {
          "items": {
            "type": "string"
          },
          "title": "Supporting Evidence",
          "type": "array"
        },
        "missing_evidence": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Missing Evidence"
        },
        "confidence": {
          "title": "Confidence",
          "type": "number"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        }
      },
      "required": [
        "criterion_text",
        "policy_excerpt_index",
        "status",
        "supporting_evidence",
        "confidence",
        "rationale"
      ],
    
```

## Output schema (`VerdictSynthesizerOutput`)

```json
{
  "$defs": {
    "VerdictDecisionTrace": {
      "description": "The deterministic rule's full evaluation trace \u2014 fully audit-replayable.",
      "properties": {
        "triggered_rule": {
          "enum": [
            "inclusion_NOT_MET",
            "exclusion_MET",
            "any_AMBIGUOUS",
            "low_overall_confidence",
            "all_clear_approve"
          ],
          "title": "Triggered Rule",
          "type": "string"
        },
        "triggering_criterion_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Triggering Criterion Index"
        },
        "overall_confidence": {
          "title": "Overall Confidence",
          "type": "number"
        }
      },
      "required": [
        "triggered_rule",
        "overall_confidence"
      ],
      "title": "VerdictDecisionTrace",
      "type": "object"
    }
  },
  "properties": {
    "verdict": {
      "enum": [
        "APPROVE",
        "DENY",
        "REFER"
      ],
      "title": "Verdict",
      "type": "string"
    },
    "trace": {
      "$ref": "#/$defs/VerdictDecisionTrace"
    }
  },
  "required": [
    "verdict",
    "trace"
  ],
  "title": "VerdictSynthesizerOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- _(none configured)_

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `VerdictSynthesizerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `VerdictSynthesizerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="verdict_synthesizer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
