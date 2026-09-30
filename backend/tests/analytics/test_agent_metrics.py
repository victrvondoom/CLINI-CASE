"""Agent metrics come from agent_runs; the runs endpoint no longer hides the DB behind a broken import."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.analytics.agent_metrics import price_for, summarize_agent
from app.auth import get_current_user
from app.main import app


def base(**over):
    r = {
        "invocations": 10,
        "ok": 9,
        "errors": 1,
        "running": 0,
        "p50_ms": 1000.4,
        "p95_ms": 2500.6,
        "mean_in": 2000.2,
        "mean_out": 500.5,
        "last_run_at": datetime(2026, 1, 1, tzinfo=UTC),
        "model_id": "claude-sonnet",
        "last_failed": False,
    }
    return {**r, **over}


def test_price_table_by_model_family():
    haiku, sonnet = price_for("us.anthropic.claude-haiku-4-5"), price_for("claude-sonnet-4-6")
    assert haiku[0] < sonnet[0] and price_for(None) == sonnet


def test_summary_math_and_cost():
    s = summarize_agent(
        base(), [{"model_id": "claude-sonnet", "in_tokens": 1_000_000, "out_tokens": 100_000}]
    )
    assert s["success_pct"] == 90.0 and s["p50_ms"] == 1000 and s["p95_ms"] == 2501
    assert s["cost_usd"] == pytest.approx(
        3.0 + 1.5
    )  # $3/M in + $15/M out under the framework price table
    assert s["state"] == "healthy"


def test_state_machine():
    assert summarize_agent(base(running=1), [])["state"] == "running"
    assert summarize_agent(base(last_failed=True), [])["state"] == "error"
    assert (
        summarize_agent(base(ok=2, errors=2), [])["state"] == "error"
    )  # 50% success over >= 3 finished runs
    assert (
        summarize_agent(base(ok=1, errors=1), [])["state"] == "healthy"
    )  # too few runs to call it an error
    assert (
        summarize_agent(
            base(ok=0, errors=0, p50_ms=None, p95_ms=None, mean_in=None, mean_out=None), []
        )["success_pct"]
        is None
    )


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u",
        "email": "a@b.c",
        "organization_id": "org_am",
        "role": "admin",
        "full_name": "x",
    }
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_metrics_endpoint_scopes_and_validates(client, monkeypatch):
    seen = {}

    async def fake(org, hours):
        seen.update(org=org, hours=hours)
        return {"window_hours": hours, "agents": {}, "totals": {"invocations": 0, "cost_usd": 0}}

    monkeypatch.setattr("app.api.agents_manifest.fetch_agent_metrics", fake)
    assert client.get("/api/v1/agents/metrics?hours=6").status_code == 200 and seen == {
        "org": "org_am",
        "hours": 6,
    }
    assert client.get("/api/v1/agents/metrics?hours=0").status_code == 422


def test_metrics_endpoint_503_without_db(client, monkeypatch):
    async def boom(org, hours):
        raise RuntimeError("down")

    monkeypatch.setattr("app.api.agents_manifest.fetch_agent_metrics", boom)
    assert client.get("/api/v1/agents/metrics").status_code == 503


def test_metrics_route_is_not_shadowed_by_agent_name_routes(client, monkeypatch):
    async def fake(org, hours):
        return {"window_hours": hours, "agents": {}, "totals": {"invocations": 0, "cost_usd": 0}}

    monkeypatch.setattr("app.api.agents_manifest.fetch_agent_metrics", fake)
    assert "agents" in client.get("/api/v1/agents/metrics").json()


def test_manifest_exposes_the_real_pipeline_topology(client):
    body = client.get("/api/v1/agents/manifest").json()
    g = body["graph"]
    assert g["order"][:7] == [
        "clinical_extractor",
        "policy_retriever",
        "necessity_reasoner",
        "decision_composer",
        "denial_forecaster",
        "appeals_drafter",
        "patient_communicator",
    ]
    cond = {(e["source"], e["target"]) for e in g["edges"] if e["conditional"]}
    assert ("necessity_reasoner", "review_gate") in cond and (
        "denial_forecaster",
        "appeals_drafter",
    ) in cond
    idx = {a["name"]: a["pipeline_index"] for a in body["agents"]}
    assert idx["clinical_extractor"] == 1 and idx["patient_communicator"] == 7
    from app.agents.manifest import total_sub_agents

    assert body["n_agents"] == 7 and body["n_sub_agents"] == total_sub_agents()
