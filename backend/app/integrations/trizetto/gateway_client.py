"""TriZetto AI Gateway MCP client.

The Gateway is Cognizant's centralized agent-management surface (launched
Aug 6, 2025; built on AWS Bedrock; MCP-native; ships Anthropic Claude Sonnet
4.6 by default). ClinCase submits decisions to the Gateway as MCP tool-call
events; the Gateway then fans them out to Facets / QNXT / appeal-management
modules per the customer's deployment.

Two modes (selected via env / constructor):

  • Mock mode (default for hackathon): the client POSTS to the in-process
    /api/v1/integrations/trizetto/_mock/inbox endpoint. Every demo run
    visibly succeeds; the receiver's inbox can be inspected to prove the
    end-to-end loop is real.

  • Real mode: the client POSTS to TRIZETTO_GATEWAY_URL with bearer auth.
    No further code changes — flip TRIZETTO_GATEWAY_URL and
    TRIZETTO_GATEWAY_TOKEN. The wire shape is identical (mock matches real).

The wire shape is JSON-RPC 2.0 (matching the public MCP spec). Request:

    POST {gateway_url}/mcp
    {
      "jsonrpc": "2.0", "id": "...", "method": "tools/call",
      "params": {
        "name": "submit_clincase_determination",
        "arguments": {
          "case_id": "...", "facets_event": {...}, "qnxt_event": {...}
        }
      }
    }
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.config import settings
from app.integrations.trizetto.facets_pa_event import FacetsPAEvent
from app.integrations.trizetto.qnxt_writeback import QNXTDecisionEvent

log = structlog.get_logger()


# =============================================================================
# Public DTOs
# =============================================================================


@dataclass
class GatewaySubmission:
    """One submission to the Gateway. Carries both Facets + QNXT shapes;
    the Gateway routes by the customer's TriZetto product config."""

    case_id: str
    organization_id: str
    facets_event: FacetsPAEvent | None = None
    qnxt_event: QNXTDecisionEvent | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_jsonrpc_args(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "organization_id": self.organization_id,
            "facets_event": self.facets_event.model_dump() if self.facets_event else None,
            "qnxt_event": self.qnxt_event.model_dump() if self.qnxt_event else None,
            **self.extra,
        }


@dataclass
class GatewayAck:
    """Gateway response. Always returned even on mock-mode submissions."""

    accepted: bool
    gateway_id: str | None
    fanout_targets: list[str]
    received_at: str
    raw: dict[str, Any]


# =============================================================================
# In-process mock (default)
# =============================================================================


# Module-level inbox so /api/v1/integrations/trizetto/_mock/inbox can read it.
# In production the mock is unused — TRIZETTO_GATEWAY_URL points to the real
# Gateway and this stays empty.
_MOCK_INBOX: list[dict[str, Any]] = []
_MOCK_INBOX_MAX = 100


def _record_mock(envelope: dict[str, Any]) -> None:
    _MOCK_INBOX.append(envelope)
    if len(_MOCK_INBOX) > _MOCK_INBOX_MAX:
        del _MOCK_INBOX[: len(_MOCK_INBOX) - _MOCK_INBOX_MAX]


def get_mock_inbox() -> list[dict[str, Any]]:
    """Return the latest N mock-mode envelopes the Gateway client posted."""
    return list(_MOCK_INBOX)


def clear_mock_inbox() -> None:
    _MOCK_INBOX.clear()


# =============================================================================
# Client
# =============================================================================


class TriZettoGatewayClient:
    """Async client for the TriZetto AI Gateway.

    Stateless: one instance can be reused across submissions. HTTP transport
    uses a short-lived `httpx.AsyncClient` per call so connection lifecycle
    matches typical FastAPI per-request semantics.

    Selection: if `gateway_url` is empty (default), the client runs in mock
    mode and records to `_MOCK_INBOX`. Otherwise it POSTs to
    `{gateway_url}/mcp` with a `Bearer {token}` header.
    """

    def __init__(
        self,
        *,
        gateway_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.gateway_url = (gateway_url or getattr(settings, "TRIZETTO_GATEWAY_URL", "") or "").rstrip("/")
        self.token = token or getattr(settings, "TRIZETTO_GATEWAY_TOKEN", "") or ""
        self.timeout = timeout_seconds

    @property
    def is_mock(self) -> bool:
        return not self.gateway_url

    async def submit(self, submission: GatewaySubmission) -> GatewayAck:
        """Send a submission to the Gateway. Returns an ack regardless of mode."""
        envelope = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": "submit_clincase_determination",
                "arguments": submission.to_jsonrpc_args(),
            },
        }

        if self.is_mock:
            return self._mock_submit(envelope)
        return await self._real_submit(envelope)

    # ------------------------------------------------------------------
    # Mock path
    # ------------------------------------------------------------------

    def _mock_submit(self, envelope: dict[str, Any]) -> GatewayAck:
        from datetime import datetime, timezone

        gateway_id = f"trizetto-mock-{uuid.uuid4().hex[:12]}"
        received_at = datetime.now(timezone.utc).isoformat()

        # Echo what a real Gateway would: which downstream products will
        # receive this. Demo-grade — production fan-out is config-driven.
        targets = []
        if envelope["params"]["arguments"].get("facets_event"):
            targets.append("facets-pa-workflow")
        if envelope["params"]["arguments"].get("qnxt_event"):
            targets.append("qnxt-case-events")

        record = {
            "gateway_id": gateway_id,
            "received_at": received_at,
            "envelope": envelope,
            "fanout_targets": targets,
        }
        _record_mock(record)
        log.info(
            "trizetto.gateway.mock_submit",
            gateway_id=gateway_id,
            case_id=envelope["params"]["arguments"].get("case_id"),
            targets=targets,
        )
        return GatewayAck(
            accepted=True,
            gateway_id=gateway_id,
            fanout_targets=targets,
            received_at=received_at,
            raw={"jsonrpc": "2.0", "id": envelope["id"], "result": {"ok": True, "gateway_id": gateway_id}},
        )

    # ------------------------------------------------------------------
    # Real network path
    # ------------------------------------------------------------------

    async def _real_submit(self, envelope: dict[str, Any]) -> GatewayAck:
        from datetime import datetime, timezone

        url = f"{self.gateway_url}/mcp"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                resp = await http.post(url, headers=headers, json=envelope)
        except httpx.RequestError as e:
            log.warning("trizetto.gateway.network_error", error=str(e))
            return GatewayAck(
                accepted=False,
                gateway_id=None,
                fanout_targets=[],
                received_at=datetime.now(timezone.utc).isoformat(),
                raw={"error": str(e)},
            )

        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = {"error": "non-json response", "status": resp.status_code, "text_preview": resp.text[:200]}

        accepted = resp.status_code < 400 and "error" not in body
        result = body.get("result", {}) if isinstance(body, dict) else {}
        return GatewayAck(
            accepted=accepted,
            gateway_id=result.get("gateway_id") if isinstance(result, dict) else None,
            fanout_targets=result.get("fanout_targets", []) if isinstance(result, dict) else [],
            received_at=datetime.now(timezone.utc).isoformat(),
            raw=body if isinstance(body, dict) else {"raw": body},
        )
