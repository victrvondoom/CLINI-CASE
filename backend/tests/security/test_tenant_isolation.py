"""ORG A CANNOT READ OR WRITE ORG B DATA — end-to-end against the real app and a real PostgreSQL schema.

Phase-1 security baseline: platform-admin vs organisation-admin semantics, authenticated and tenant-scoped MCP.
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import is_platform_admin
from app.auth.jwt_helpers import create_access_token
from app.config import settings
from app.db import db
from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


async def _org_with_users(tag: str) -> dict[str, str]:
    org = f"iso-{tag}-{uuid.uuid4().hex[:6]}"
    await db.execute("INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1)", org)
    out = {"org": org}
    for role in ("admin", "reviewer", "coordinator"):
        uid, email = f"u-{role}-{org}", f"{role}@{org}.test"
        await db.execute(
            "INSERT INTO users (id,email,password_hash,full_name,organization_id,role) "
            "VALUES ($1,$2,'x',$3,$4,$5)",
            uid,
            email,
            role,
            org,
            role,
        )
        out[role] = create_access_token(
            user_id=uid, organization_id=org, role=role, email=email, full_name=role
        )
        out[f"{role}_email"] = email
    return out


async def _case(org: str, status: str = "approved") -> str:
    cid = f"iso-{uuid.uuid4().hex[:10]}"
    await db.execute(
        """INSERT INTO cases (id, organization_id, payer_id, patient_initials,
                              requested_treatment_name, fhir_bundle, status)
           VALUES ($1,$2,'aetna','T.T.','Trastuzumab','{}'::jsonb,$3)""",
        cid,
        org,
        status,
    )
    await db.execute(
        """INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence)
           VALUES ($1,'APPROVE','secret rationale of ' || $2,'[]'::jsonb,0.9)""",
        cid,
        org,
    )
    return cid


@pytest.fixture
async def world():
    a, b = await _org_with_users("a"), await _org_with_users("b")
    a["case"], b["case"] = await _case(a["org"]), await _case(b["org"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield a, b, c


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---- case data: reads ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/cases/{c}",
        "/api/v1/cases/{c}/audit",
        "/api/v1/cases/{c}/twin",
        "/api/v1/cases/{c}/evidence-pack",
        "/api/v1/cases/{c}/compare",
    ],
)
async def test_org_a_cannot_read_org_b_case(world, path):
    a, b, c = world
    own = await c.get(path.format(c=a["case"]), headers=_h(a["admin"]))
    assert own.status_code == 200, (path, own.text)
    other = await c.get(path.format(c=b["case"]), headers=_h(a["admin"]))
    assert other.status_code == 404, (path, other.status_code)
    assert b["org"] not in other.text


async def test_case_list_contains_only_own_org(world):
    a, b, c = world
    r = await c.get("/api/v1/cases", headers=_h(a["admin"]))
    assert r.status_code == 200
    text = r.text
    assert a["case"] in text and b["case"] not in text and b["org"] not in text


# ---- case data: writes -----------------------------------------------------------------------
async def test_org_a_cannot_write_org_b_case(world):
    a, b, c = world
    await db.execute("UPDATE cases SET status='awaiting_review' WHERE id=$1", b["case"])
    for method, path, body in [
        ("post", f"/api/v1/cases/{b['case']}/resume", {"verdict": "DENY", "reviewer_note": "x"}),
        ("post", f"/api/v1/cases/{b['case']}/review", {"action": "add_note", "note": "x"}),
        ("post", f"/api/v1/cases/{b['case']}/run-async", None),
        ("post", f"/api/v1/cases/{b['case']}/compare/uhc", None),
    ]:
        r = await getattr(c, method)(path, headers=_h(a["reviewer"]), json=body)
        assert r.status_code in (403, 404), (path, r.status_code, r.text)
    row = await db.fetchrow("SELECT status FROM cases WHERE id=$1", b["case"])
    assert row["status"] == "awaiting_review"
    assert (
        await db.fetchval("SELECT count(*) FROM reviewer_actions WHERE case_id=$1", b["case"]) == 0
    )
    assert await db.fetchval("SELECT count(*) FROM case_jobs WHERE case_id=$1", b["case"]) == 0
    assert (
        await db.fetchval(
            "SELECT count(*) FROM decisions WHERE case_id=$1 AND rationale LIKE '%OVERRIDE%'",
            b["case"],
        )
        == 0
    )


# ---- org admin is NOT a platform admin --------------------------------------------------------
PLATFORM_ONLY = [
    ("get", "/api/v1/admin/tenants", None),
    ("get", "/api/v1/admin/tenants/{org}", None),
    (
        "post",
        "/api/v1/admin/tenants",
        {"name": "X Org", "admin_email": "x@x.test", "admin_full_name": "Xx Xx"},
    ),
    ("get", "/api/v1/finops/cells", None),
    ("get", "/api/v1/finops/leaderboard", None),
    ("get", "/api/v1/finops/projection", None),
    ("get", "/api/v1/security/anomalies?same_org_only=false", None),
    ("post", "/api/v1/privacy/_run_hard_delete", None),
    ("get", "/api/v1/jobs/queue/depth", None),
    ("post", "/api/v1/integrations/kiro/export", None),
    ("get", "/api/v1/prompts", None),
    ("post", "/api/v1/prompts", {}),
]


@pytest.mark.parametrize("method,path,body", PLATFORM_ONLY)
async def test_org_admin_cannot_use_platform_routes(world, method, path, body):
    a, b, c = world
    r = (
        await getattr(c, method)(path.format(org=b["org"]), headers=_h(a["admin"]), json=body)
        if method == "post"
        else await c.get(path.format(org=b["org"]), headers=_h(a["admin"]))
    )
    assert r.status_code == 403, (path, r.status_code, r.text[:200])


async def test_org_admin_still_has_own_org_scope(world):
    a, _b, c = world
    r = await c.get("/api/v1/security/anomalies", headers=_h(a["admin"]))
    assert r.status_code == 200 and r.json()["scope"] == "same-org"


async def test_tenant_registry_does_not_leak_to_org_admin(world):
    a, b, c = world
    r = await c.get("/api/v1/admin/tenants", headers=_h(a["admin"]))
    assert b["org"] not in r.text


async def test_platform_admin_is_bound_to_user_id_not_email(world, monkeypatch):
    a, _b, c = world
    uid = f"u-admin-{a['org']}"
    user = {"id": uid, "role": "admin", "email": a["admin_email"]}
    assert not is_platform_admin(user)
    # An e-mail in the allow-list (the retired mechanism) grants nothing.
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_USER_IDS", a["admin_email"])
    assert not is_platform_admin(user)
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_USER_IDS", f" {uid} , user_other")
    assert is_platform_admin(user)
    assert not is_platform_admin({**user, "role": "reviewer"})  # role still required
    assert not is_platform_admin({**user, "id": "user_someone_else"})
    r = await c.get("/api/v1/admin/tenants", headers=_h(a["admin"]))
    assert r.status_code == 200


async def test_registering_an_operator_email_does_not_confer_platform_admin(world):
    """The attack the id binding prevents: sign up with an e-mail that is merely *named* somewhere."""
    _a, _b, c = world
    email = f"ops-{uuid.uuid4().hex[:6]}@example.org"
    r = await c.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "a-long-password-1",
            "full_name": "Mallory",
            "organization_name": "Mallory Org",
        },
    )
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]
    assert (await c.get("/api/v1/admin/tenants", headers=_h(token))).status_code == 403


async def test_platform_routes_fail_closed_without_allow_list(world, monkeypatch):
    a, _b, c = world
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_USER_IDS", "")
    r = await c.get("/api/v1/admin/tenants", headers=_h(a["admin"]))
    assert r.status_code == 403
    assert not is_platform_admin(
        {"role": "admin", "id": "user_demoadmin"}
    )  # dev shortcut is dev-only


async def test_prompt_assignment_may_target_any_existing_org_for_operators(world, monkeypatch):
    a, b, c = world
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_USER_IDS", f"u-admin-{a['org']}")
    r = await c.post(
        "/api/v1/prompts/necessity_reasoner/assign",
        headers=_h(a["admin"]),
        json={"organization_id": "no-such-org", "version": "v1"},
    )
    assert r.status_code == 404  # reaches the operator path (not the old same-org 403)


# ---- MCP -------------------------------------------------------------------------------------
def _rpc(tool: str, args: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }


@pytest.mark.parametrize("method", ["initialize", "tools/list", "ping"])
async def test_mcp_requires_authentication_for_every_method(world, method):
    _a, _b, c = world
    r = await c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method})
    assert r.status_code == 401


async def test_mcp_rejects_shared_secret_even_when_configured(world, monkeypatch):
    _a, _b, c = world
    monkeypatch.setattr(settings, "MCP_AUTH_TOKEN", "x" * 40)
    r = await c.post(
        "/mcp",
        headers={"Authorization": "Bearer " + "x" * 40},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert r.status_code == 401


async def test_mcp_decision_check_is_tenant_scoped(world):
    a, b, c = world
    own = await c.post(
        "/mcp", headers=_h(a["reviewer"]), json=_rpc("decision_check", {"case_id": a["case"]})
    )
    assert "result" in own.json(), own.text
    assert "secret rationale of " + a["org"] in json.dumps(own.json())
    other = await c.post(
        "/mcp", headers=_h(a["reviewer"]), json=_rpc("decision_check", {"case_id": b["case"]})
    )
    body = other.json()
    assert body["error"]["message"] == "Case not found"
    assert b["org"] not in json.dumps(body)


@pytest.mark.parametrize(
    "tool", ["clinical_extract", "decision_check", "appeal_draft", "audit_query"]
)
async def test_every_mcp_case_tool_denies_cross_tenant(world, tool):
    a, b, c = world
    r = await c.post("/mcp", headers=_h(a["admin"]), json=_rpc(tool, {"case_id": b["case"]}))
    assert r.json()["error"]["message"] == "Case not found", (tool, r.text)


async def test_mcp_tenant_cannot_be_chosen_by_the_caller(world):
    a, b, c = world
    r = await c.post(
        "/mcp",
        headers=_h(a["admin"]),
        json=_rpc("decision_check", {"case_id": b["case"], "organization_id": b["org"]}),
    )
    assert "error" in r.json() and b["org"] not in json.dumps(r.json()["error"].get("data", {}))
    assert "secret rationale" not in r.text


async def test_mcp_tool_errors_do_not_echo_internals(world):
    a, _b, c = world
    r = await c.post(
        "/mcp", headers=_h(a["admin"]), json=_rpc("audit_query", {"case_id": a["case"]})
    )
    err = r.json().get("error")
    assert err is None or "relation" not in err["message"].lower()  # no raw database error text


@pytest.mark.parametrize("bad", [5, ["organization_id"], "x", True])
async def test_mcp_non_object_arguments_are_a_jsonrpc_error_not_a_500(world, bad):
    a, _b, c = world
    r = await c.post("/mcp", headers=_h(a["admin"]), json=_rpc("decision_check", bad))
    assert r.status_code == 200 and r.json()["error"]["code"] == -32602


async def test_mcp_internal_type_errors_are_not_reported_as_client_errors(world, monkeypatch):
    from app.mcp import server

    async def boom(organization_id, case_id):
        raise TypeError("'NoneType' object is not subscriptable: internal detail")

    a, _b, c = world
    monkeypatch.setitem(server.TOOL_IMPLS, "decision_check", boom)
    r = await c.post(
        "/mcp", headers=_h(a["admin"]), json=_rpc("decision_check", {"case_id": a["case"]})
    )
    err = r.json()["error"]
    assert err["code"] == -32603 and "internal detail" not in r.text


async def test_mcp_wrong_argument_shape_is_reported_without_internals(world):
    a, _b, c = world
    r = await c.post("/mcp", headers=_h(a["admin"]), json=_rpc("decision_check", {"nope": 1}))
    assert r.json()["error"]["code"] == -32602
