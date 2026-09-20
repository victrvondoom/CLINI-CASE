"""MCP server exposed over HTTP/JSON-RPC 2.0.

ClinCase implements the Model Context Protocol so MCP-compatible clients
(Claude Desktop, Cursor, Cognizant TriZetto AI Gateway) can discover and
invoke ClinCase's reasoning tools without bespoke integration glue.

This is the single feature that makes ClinCase "drop-in compatible with
TriZetto AI Gateway" — Cognizant's own re:Invent 2025 talk (IND210)
described their gateway as MCP-compliant.

Transport: HTTP POST of JSON-RPC 2.0 envelopes.
Methods supported:
  - initialize
  - tools/list
  - tools/call

Reference: https://modelcontextprotocol.io/specification
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp.tools import TOOL_DEFINITIONS, TOOL_IMPLS

router = APIRouter(prefix="/mcp", tags=["mcp"])


# =============================================================================
# JSON-RPC 2.0 request/response envelopes
# =============================================================================


class JSONRPCRequest(BaseModel):
    jsonrpc: str = Field(default="2.0")
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


def _ok(req_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(
    req_id: str | int | None, code: int, message: str, data: Any = None
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# =============================================================================
# JSON-RPC method handlers
# =============================================================================


SERVER_INFO = {
    "name": "clincase-mcp",
    "version": "0.1.0",
    "description": (
        "ClinCase prior-authorisation copilot — MCP-compliant tool surface. "
        "Exposes 5 tools backed by the ClinCase 5-agent LangGraph DAG over "
        "AWS Bedrock Claude Sonnet 4.6."
    ),
}

# Capabilities advertised in the initialize handshake
CAPABILITIES = {
    "tools": {"listChanged": False},
    "logging": {},
    "resources": {"subscribe": False, "listChanged": False},
}


async def _handle_initialize(req_id: str | int | None, params: dict[str, Any]) -> dict[str, Any]:
    """The MCP handshake. Returns server identity + capabilities."""
    return _ok(
        req_id,
        {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": CAPABILITIES,
            "instructions": (
                "ClinCase MCP server. Use tools/list to discover available "
                "tools (policy_lookup, clinical_extract, decision_check, "
                "appeal_draft, audit_query). All tools are read-mostly; "
                "decision_check and appeal_draft return persisted outputs "
                "from the audit trail without re-running the LLM."
            ),
        },
    )


async def _handle_tools_list(req_id: str | int | None) -> dict[str, Any]:
    return _ok(req_id, {"tools": TOOL_DEFINITIONS})


async def _handle_tools_call(
    req_id: str | int | None, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments") or {}
    if not name or name not in TOOL_IMPLS:
        return _err(
            req_id,
            -32602,
            f"Unknown tool: {name!r}. Use tools/list to discover available tools.",
        )
    impl = TOOL_IMPLS[name]
    try:
        result = await impl(**args)
        return _ok(req_id, result)
    except TypeError as e:
        # Bad argument shape
        return _err(req_id, -32602, f"Invalid arguments for {name}: {e}")
    except Exception as e:  # noqa: BLE001
        return _err(req_id, -32603, f"Tool execution failed: {e}", data={"tool": name})


# =============================================================================
# HTTP route
# =============================================================================


def _check_token(authorization: str | None) -> None:
    """Optional shared-secret check.

    If MCP_AUTH_TOKEN is set in the environment, require a matching Bearer
    token. If unset, allow all callers (hackathon / open-demo mode). In
    production this is set via AWS Secrets Manager and rotated regularly.
    """
    expected = getattr(settings, "MCP_AUTH_TOKEN", None) or ""
    if not expected:
        return  # open mode for the demo
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@router.post("", status_code=200)
async def mcp_endpoint(
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """JSON-RPC 2.0 endpoint. Single transport, multiple methods."""
    _check_token(authorization)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _err(None, -32700, "Parse error: invalid JSON")

    if not isinstance(body, dict):
        return _err(None, -32600, "Invalid request: must be a JSON object")

    try:
        rpc = JSONRPCRequest(**body)
    except Exception as e:  # noqa: BLE001
        return _err(body.get("id"), -32600, f"Invalid request envelope: {e}")

    method = rpc.method
    params = rpc.params or {}

    if method == "initialize":
        return await _handle_initialize(rpc.id, params)
    if method == "tools/list":
        return await _handle_tools_list(rpc.id)
    if method == "tools/call":
        return await _handle_tools_call(rpc.id, params)
    if method == "ping":
        return _ok(rpc.id, {})
    return _err(rpc.id, -32601, f"Method not found: {method!r}")


# =============================================================================
# Convenience GET handler — returns the manifest as plain JSON for humans.
# =============================================================================


@router.get("/manifest", status_code=200)
async def mcp_manifest() -> dict[str, Any]:
    """Human-readable manifest of MCP tools.

    Useful for documentation, integration testing, and showing in the demo.
    The authoritative discovery method per the MCP spec is the JSON-RPC
    `tools/list` call against POST /mcp.
    """
    return {
        "server": SERVER_INFO,
        "transport": "http+jsonrpc",
        "endpoint": "/mcp",
        "spec_version": "2024-11-05",
        "tools": TOOL_DEFINITIONS,
        "client_compatibility": [
            "Claude Desktop",
            "Cursor",
            "Cognizant TriZetto AI Gateway (MCP-compliant per re:Invent 2025 IND210)",
            "Any JSON-RPC 2.0 MCP client",
        ],
    }
