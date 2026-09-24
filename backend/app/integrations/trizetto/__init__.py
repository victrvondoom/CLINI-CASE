"""TriZetto AI Gateway + Facets + QNXT integration adapter.

This package makes ClinCase deployable as a TriZetto AI Gateway-native
specialty agent bundle.

Why this matters:

  • Aug 6, 2025 — TriZetto AI Gateway launched: built on AWS Bedrock,
    MCP-native, ships with Anthropic Claude Sonnet 4.6.
  • ClinCase already speaks the same stack: Bedrock + Claude Sonnet 4.6 + MCP.
    This adapter makes that alignment EXPLICIT and DEMONSTRABLE.

What ships here:

  gateway_client.py      — MCP-over-HTTP client that speaks the Gateway's
                           documented JSON-RPC envelope. Default: calls the
                           local in-process mock at /trizetto/_mock so the
                           demo always works. Real Gateway URL is one env var.
  facets_pa_event.py     — Facets-PA-task DTO. Maps ClinCase Decision ->
                           Facets `prior_auth_event` schema (the production
                           interface a TriZetto reviewer reads).
  qnxt_writeback.py      — QNXT decision writeback. After ClinCase APPROVES,
                           we POST the determination to QNXT's case-event
                           webhook so claims downstream sees the auth.
  router.py              — FastAPI router exposing
                           POST /api/v1/integrations/trizetto/submit
                           GET  /api/v1/integrations/trizetto/_mock/inbox
                              (so the demo can show what the Gateway received)
"""
from app.integrations.trizetto.facets_pa_event import FacetsPAEvent, build_facets_event
from app.integrations.trizetto.gateway_client import (
    GatewayAck,
    GatewaySubmission,
    TriZettoGatewayClient,
)
from app.integrations.trizetto.qnxt_writeback import QNXTDecisionEvent, build_qnxt_event

__all__ = [
    "TriZettoGatewayClient",
    "GatewaySubmission",
    "GatewayAck",
    "FacetsPAEvent",
    "build_facets_event",
    "QNXTDecisionEvent",
    "build_qnxt_event",
]
