# ClinCase — Bedrock Cross-Region Fallback (in-process)

**Status:** Accepted (round-12)
**Audience:** TriZetto SRE · AWS account team · Gold-tier customer SRE

## Why we need it

Round-9 resilience: per-Bedrock-model circuit breaker. When `apac.anthropic.claude-sonnet-4-6-...` opens, ModelRouter escalates to `apac.anthropic.claude-haiku-4-5-...`.

The gap: when **both** open (entire region's Bedrock degraded), all calls
fail. Round-10 chaos.sh fixes this operationally — operator flips
`BEDROCK_MODEL_ID` env to `us.anthropic.*`, restarts pods. ~5 minutes.

Round-12 closes the in-process gap: the gateway can ESCALATE THE REGION as a
final resort, AUTOMATICALLY.

## Decision

When the per-tenant resolved model_id's breaker is OPEN AND the alternate
model in the same region's breaker is also OPEN:

1. Compute the fallback chain from `app/llm/cross_region_fallback.py`
2. Try the next region's inference profile (e.g., `apac.* → us.* → eu.*`)
3. Tag the invocation with `region_class=fallback` for FinOps tracking
4. Emit a metric: `clincase_bedrock_cross_region_fallback_total{from,to}`

## Trigger conditions

```python
should_cross_region = (
    primary_breaker_state == "open"
    and fallback_breaker_state == "open"
    and not feature_flag_disabled
    and tenant_tier in {"silver", "gold"}   # bronze fails-fast to keep cost predictable
)
```

## Cost note

Cross-region Bedrock data transfer is metered. From AWS pricing (May 2026):
- $0.02 per 1K input tokens (cross-region penalty)
- ~10% latency overhead

For a Gold-tier 1M-cases/year tenant: ~$200/month if 5% of calls fall
through to fallback. The FinOps dashboard breaks this out.

For Bronze tenants we deliberately do NOT enable cross-region — the
contractual RTO permits a 30-min manual operator response, and the cost
optimization matters more.

## Files

- `backend/app/llm/cross_region_fallback.py` — fallback chain logic
- ADR-AAA round 12

## Wiring (deferred to next round)

The chain is built; integrating it into `app/llm/gateway.py:complete()` is
straightforward:

```python
# In gateway.complete(), after the primary call fails with CircuitBreakerOpen
# and the alternate-model retry also fails:
from app.llm.cross_region_fallback import fallback_model_ids, is_cross_region_fallback_enabled

if is_cross_region_fallback_enabled() and tenant.tier in {"silver", "gold"}:
    for fallback_model_id in fallback_model_ids(home_model_id):
        try:
            return await self._try_with_breaker(fallback_model_id, ...)
        except CircuitBreakerOpen:
            continue
```

This wiring lands in round-13. The chain primitive is ready today.

## Sources

- AWS Bedrock cross-region inference — https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html
- Resilience patterns at AWS — https://aws.amazon.com/builders-library/avoiding-fallback-in-distributed-systems/
