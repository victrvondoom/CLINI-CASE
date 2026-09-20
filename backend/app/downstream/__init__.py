"""Downstream circuit breakers + adapters for non-Bedrock external services.

Round-9 shipped a per-Bedrock-model breaker. Bedrock is one of MANY downstream
dependencies. Round-12 generalizes the pattern across:

  • TriZetto AI Gateway (POST /facets/prior_auth_event)
  • TriZetto QNXT Gateway (POST /qnxt/case_event)
  • Amazon Q Business (POST /amazonq/retrieve)
  • Da Vinci PAS endpoint (POST /Claim/$submit)
  • Anthropic API (when LLM_PROVIDER=anthropic)
  • Bedrock KB (POST /bedrock-kb/retrieve)

Each downstream gets a per-(host, route) breaker. Failures don't spread.

Pairs with: ops/architecture/DOWNSTREAM_BREAKERS.md
"""
from app.downstream.breaker import (
    DownstreamBreaker,
    DownstreamBreakerOpen,
    breaker_snapshot,
    get_breaker,
)

__all__ = [
    "DownstreamBreaker",
    "DownstreamBreakerOpen",
    "get_breaker",
    "breaker_snapshot",
]
