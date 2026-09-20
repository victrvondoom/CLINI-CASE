# Design — `citation_resolver`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.362109+00:00.

## Architecture

This agent is a **sub-agent** of `policy_retriever`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`CitationResolverInput`)

```json
{
  "$defs": {
    "CandidateSection": {
      "description": "A (policy, section) pair surviving the keyword filter.",
      "properties": {
        "policy_id": {
          "title": "Policy Id",
          "type": "string"
        },
        "payer_id": {
          "title": "Payer Id",
          "type": "string"
        },
        "policy_title": {
          "title": "Policy Title",
          "type": "string"
        },
        "section_heading": {
          "title": "Section Heading",
          "type": "string"
        },
        "section_text": {
          "title": "Section Text",
          "type": "string"
        },
        "source_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Url"
        },
        "page_number": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Number"
        }
      },
      "required": [
        "policy_id",
        "payer_id",
        "policy_title",
        "section_heading",
        "section_text"
      ],
      "title": "CandidateSection",
      "type": "object"
    }
  },
  "properties": {
    "candidates": {
      "items": {
        "$ref": "#/$defs/CandidateSection"
      },
      "title": "Candidates",
      "type": "array"
```

## Output schema (`CitationResolverOutput`)

```json
{
  "$defs": {
    "PolicyExcerpt": {
      "properties": {
        "payer_id": {
          "title": "Payer Id",
          "type": "string"
        },
        "policy_id": {
          "title": "Policy Id",
          "type": "string"
        },
        "policy_title": {
          "title": "Policy Title",
          "type": "string"
        },
        "section_heading": {
          "title": "Section Heading",
          "type": "string"
        },
        "excerpt_text": {
          "title": "Excerpt Text",
          "type": "string"
        },
        "source_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Url"
        },
        "page_number": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Number"
        },
        "relevance_score": {
          "title": "Relevance Score",
          "type": "number"
        }
      },
      "required": [
        "payer_id",
        "policy_id",
        "policy_title",
        "section_heading",
        "excerpt_text",
        "relevance_score"
      ],
      "title": "PolicyExcerpt",
      "type": "object"
    }
  },
  "properties": {
    "excerpts": {
      "items": {
        "$ref": "#/$defs/PolicyExcerpt"
      },
      "t
```

## Guardrails

### Input

- _(none configured)_

### Output

- _(none configured)_

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `CitationResolverInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `CitationResolverOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="citation_resolver",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
