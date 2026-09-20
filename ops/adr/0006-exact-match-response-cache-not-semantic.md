# ADR-0006 — Exact-match SHA-256 response cache, not semantic

## Status
Accepted · 2026-04-30

## Context

LLM call cost is the second-largest line item in ClinCase (after Bedrock Provisioned Throughput commitments). At 10K cases/day with a typical 8% retry rate, ~$300K/year is spent on calls that recompute identical inputs to identical outputs. Two caching options were on the table:

1. **Exact-match (deterministic) cache** — key on `sha256(qualified_name + organization_id + output_schema_version + input_json)`. Hit on byte-identical input, miss otherwise.
2. **Semantic cache** — embed inputs, cosine-similarity match within a threshold (typically 0.92). Hit on "similar enough" input.

## Decision

**Exact-match SHA-256 cache** (`backend/app/agents/framework/cache.py`). Per-row TTL (default 1 hour); per-org isolated; schema-pinned so prompt or schema drift invalidates immediately. Hooked into `Agent.invoke()` lifecycle as **step 0** — before guardrails, before LLM call.

Semantic cache is **deferred** to post-pilot.

## Consequences

**Positive**
- **Catches the highest-value 80% of dedup opportunity.** Retry storms (network blip, browser re-fire, audit-panel rerun) replay byte-identical inputs — the exact-match cache hits 100% of those.
- **Multi-tenant safe by construction.** Cache key includes `organization_id` — org A's cached output is never visible to org B even on byte-identical input.
- **No false positives.** A cache hit guarantees the cached output was produced for the exact same input. There's no "we thought it was similar but it actually had a different biomarker" failure mode. Critical in clinical decision support.
- **Schema-pinned invalidation.** When an agent's `output_schema` changes, the cache key changes — old entries are immediately invalidated. No stale-output risk.
- **Postgres-backed, not Redis.** Same RPO/RTO as the primary DB (ADR-0002 reasoning generalizes).

**Negative**
- **Misses the long tail.** A case with one different biomarker LOINC code gets a fresh LLM call even though 99% of the input is identical. ~12% of cases according to industry analysis.
- **No prefix or partial-match optimization.** A future "Bedrock prompt caching" integration could capture 60-80% of input-prefix dedup; that's an additive path, not a replacement.

**Neutral**
- Per-row TTL of 1 hour is conservative. A policy update propagates within an hour even on cache hits.

## Alternatives considered

| Alternative | Why rejected (for now) |
|---|---|
| Semantic cache | False-positive risk in clinical decision support is unacceptable. A 0.92 cosine threshold means ~0.08 chance of returning a cached output that doesn't actually correspond to the live input — for a CMS-0057-F § IV.B.2 specific-reason notice, that's a regulatory event waiting to happen. The 12% case-dedup opportunity is real but conditional on additional safety engineering (cohort segmentation, threshold tuning, override audit trail) — that's post-pilot scope. |
| No cache | $300K/year retry-storm cost is real money. Even the "easy" 80% of dedup pays for itself many times over. |
| Bedrock prompt caching only | Prompt caching applies to *prompt prefixes* — system prompt + first 1024 tokens. ClinCase's full retry-storm savings come from the entire (system + user) being identical; prompt caching alone misses that. We'll add prompt caching as a complement, not a replacement, when it's GA in our region. |

## References

- Implementation: `backend/app/agents/framework/cache.py`
- Integration into lifecycle: `backend/app/agents/framework/agent.py` (lifecycle step 0)
- Industry analysis on retry storms vs semantic dedup: industry knowledge anchored to AWS Bedrock prompt-caching docs
