"""In-process Bedrock cross-region fallback.

Round-9: per-Bedrock-model circuit breaker fast-fails an OPEN model. The
ModelRouter then escalates to the alternate model (Haiku ↔ Sonnet) IN THE
SAME REGION. If the entire region's Bedrock service is degraded, BOTH
breakers open and the call fails.

Round-10 chaos.sh handles this OPERATIONALLY (operator changes
BEDROCK_MODEL_ID env to a different region). That's seconds-to-minutes.

Round-12 closes the in-process gap: when both primary AND fallback model
breakers in the home region are OPEN, the gateway escalates to a
**cross-region inference profile** of the same model. From `apac.anthropic.*`
home, fallback to `us.anthropic.*`.

Cost note: cross-region Bedrock data transfer IS charged. We account for
this by tagging cross-region invocations with `region_class=fallback` so
the FinOps dashboard breaks them out.

Pairs with: ops/architecture/BEDROCK_CROSS_REGION_FALLBACK.md
"""
from __future__ import annotations

import os

import structlog

log = structlog.get_logger()


# Map a tenant's home-region prefix → ordered list of cross-region fallbacks.
# Strict ordering: nearest geographies first to minimize latency overhead.
_FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    "apac.anthropic.": ("us.anthropic.", "eu.anthropic."),
    "us.anthropic.":   ("eu.anthropic.", "apac.anthropic."),
    "eu.anthropic.":   ("us.anthropic.", "apac.anthropic."),
}


def fallback_model_ids(home_model_id: str) -> list[str]:
    """Return ordered list of cross-region model_ids that a caller can try
    when the home model_id's breaker is OPEN.

    Example:
        home = 'apac.anthropic.claude-sonnet-4-6-20251022-v1:0'
        →    ['us.anthropic.claude-sonnet-4-6-20251022-v1:0',
              'eu.anthropic.claude-sonnet-4-6-20251022-v1:0']
    """
    for home_prefix, fallbacks in _FALLBACK_CHAINS.items():
        if home_model_id.startswith(home_prefix):
            tail = home_model_id[len(home_prefix):]
            return [f"{fb}{tail}" for fb in fallbacks]
    return []


def is_cross_region_fallback_enabled() -> bool:
    """Feature flag — turn off for cost-sensitive tenants."""
    return os.getenv("BEDROCK_CROSS_REGION_FALLBACK_ENABLED", "true").lower() != "false"


def fallback_chain_snapshot() -> dict[str, list[str]]:
    """Snapshot for /capabilities + /architecture descriptor."""
    return {
        prefix: list(chain)
        for prefix, chain in _FALLBACK_CHAINS.items()
    }
