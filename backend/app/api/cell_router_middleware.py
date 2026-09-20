"""ASGI middleware — stamps `X-ClinCase-Cell-Id` on every response.

When a customer files a support ticket, their first piece of evidence is
their own X-Request-Id (round-8 already shipped). Their second piece is
the cell their request was served by — so SRE knows which cell's logs +
DB + workers to look at.

The middleware:
  1. Reads the JWT (decodes the unsigned payload — same shape as
     rate_limit_middleware) to get organization_id + data_region
  2. Resolves the cell via app.cells.cell_for_organization()
  3. Stamps `X-ClinCase-Cell-Id` on the response

This is also where future cells-aware routing can plug in: today a single
deployment serves all cells, but at scale the middleware would 307-redirect
mis-cell traffic to the cell's own ALB.
"""
from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.cells import cell_for_organization


def _decode_jwt_unsafe(token: str) -> dict | None:
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _bearer(headers) -> str | None:
    for name, value in headers:
        if name.lower() == b"authorization":
            v = value.decode("latin-1", errors="replace")
            if v.startswith("Bearer "):
                return v[7:]
    return None


class CellRouterMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cell_id_bytes: bytes | None = None
        token = _bearer(scope.get("headers", []))
        if token:
            payload = _decode_jwt_unsafe(token)
            if payload:
                org_id = (
                    payload.get("org")
                    or payload.get("organization_id")
                    or payload.get("org_id")
                )
                data_region = payload.get("data_region")
                if org_id:
                    cell = cell_for_organization(
                        organization_id=str(org_id),
                        data_region=str(data_region) if data_region else None,
                    )
                    cell_id_bytes = cell.cell_id.encode("ascii")

        async def _send_with_cell_header(message: dict) -> None:
            if message["type"] == "http.response.start" and cell_id_bytes:
                headers = list(message.get("headers", []))
                headers.append((b"x-clincase-cell-id", cell_id_bytes))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send_with_cell_header)
