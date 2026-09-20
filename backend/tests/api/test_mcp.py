"""Contract test for the MCP / JSON-RPC 2.0 server.

Verifies that:
  - GET /mcp/manifest returns a tool list with all 5 tools.
  - POST /mcp with method=initialize returns a serverInfo + capabilities envelope.
  - POST /mcp with method=tools/list returns the same 5 tools.
  - POST /mcp with method=tools/call invokes policy_lookup and returns content.
  - Unknown methods return JSON-RPC error code -32601.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_manifest_lists_all_five_tools(client: AsyncClient) -> None:
    r = await client.get("/mcp/manifest")
    assert r.status_code == 200
    body = r.json()
    tool_names = sorted(t["name"] for t in body["tools"])
    assert tool_names == sorted([
        "policy_lookup",
        "clinical_extract",
        "decision_check",
        "appeal_draft",
        "audit_query",
    ])
    # Must advertise TriZetto compatibility
    compat = " ".join(body.get("client_compatibility", []))
    assert "TriZetto" in compat


@pytest.mark.asyncio
async def test_initialize_handshake(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert "result" in body
    assert body["result"]["serverInfo"]["name"] == "clincase-mcp"
    assert body["result"]["protocolVersion"] == "2024-11-05"
    assert "capabilities" in body["result"]


@pytest.mark.asyncio
async def test_tools_list_returns_five_tools(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "abc", "method": "tools/list"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "abc"
    assert len(body["result"]["tools"]) == 5
    # Each tool has the MCP-required shape
    for tool in body["result"]["tools"]:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


@pytest.mark.asyncio
async def test_tools_call_policy_lookup(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "policy_lookup",
                "arguments": {"payer_id": "aetna", "treatment": "trastuzumab"},
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 42
    assert "result" in body
    assert body["result"]["isError"] is False
    text = "\n".join(c["text"] for c in body["result"]["content"] if c["type"] == "text")
    assert "trastuzumab" in text.lower()
    assert "aetna" in text.lower() or "Aetna" in text


@pytest.mark.asyncio
async def test_tools_call_unknown_tool(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_unknown_method(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
    )
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_ping(client: AsyncClient) -> None:
    r = await client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": "ping1", "method": "ping"}
    )
    body = r.json()
    assert body["result"] == {}
    assert body["id"] == "ping1"
