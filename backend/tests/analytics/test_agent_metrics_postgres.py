"""Agent metrics SQL + the runs endpoint against real PostgreSQL (CI: integration + postgres)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.analytics.agent_metrics import fetch_agent_metrics
from app.auth.dependencies import get_current_user
from app.db import db
from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


async def _case(org):
    await db.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
        org,
    )
    cid = f"am-{uuid.uuid4().hex[:8]}"
    await db.execute(
        "INSERT INTO cases (id, organization_id, payer_id, patient_initials, requested_treatment_name, fhir_bundle) "
        "VALUES ($1,$2,'aetna','T.T.','x','{}'::jsonb)",
        cid,
        org,
    )
    return cid


async def _run(
    cid,
    agent,
    *,
    latency=None,
    err=None,
    finished=True,
    tin=None,
    tout=None,
    model="claude-sonnet",
    age_min=1,
):
    started = datetime.now(UTC) - timedelta(minutes=age_min)
    await db.execute(
        """INSERT INTO agent_runs (case_id, agent_name, started_at, finished_at, input_json, latency_ms,
                                   model_id, input_tokens, output_tokens, error_text)
           VALUES ($1,$2,$3,$4,'{}'::jsonb,$5,$6,$7,$8,$9)""",
        cid,
        agent,
        started,
        started + timedelta(seconds=1) if finished else None,
        latency,
        model,
        tin,
        tout,
        err,
    )


async def test_metrics_are_computed_from_real_rows_and_org_scoped():
    a, b = f"org_am_a_{uuid.uuid4().hex[:5]}", f"org_am_b_{uuid.uuid4().hex[:5]}"
    ca, cb = await _case(a), await _case(b)
    for lat in (1000, 2000, 3000):
        await _run(ca, "clinical_extractor", latency=lat, tin=1000, tout=200)
    await _run(ca, "clinical_extractor", err="boom", latency=500)
    await _run(ca, "policy_retriever", finished=False)
    await _run(
        cb, "clinical_extractor", latency=99999, tin=10**6, tout=10**6
    )  # other tenant: must not leak in
    await _run(
        ca, "denial_forecaster", latency=10, tin=1, tout=1, age_min=60 * 30
    )  # outside a 24h window

    m = await fetch_agent_metrics(a, 24)
    ce = m["agents"]["clinical_extractor"]
    assert ce["invocations"] == 4 and ce["errors"] == 1 and ce["success_pct"] == 75.0
    assert (
        ce["p50_ms"] == 1500 and ce["state"] == "error"
    )  # most recent-first array: last run failed? see below
    assert ce["cost_usd"] == pytest.approx(3 * (1000 * 3 + 200 * 15) / 1e6)
    assert m["agents"]["policy_retriever"]["state"] == "running"
    assert "denial_forecaster" not in m["agents"]
    assert m["totals"]["invocations"] == 5
    assert (await fetch_agent_metrics(b, 24))["agents"]["clinical_extractor"]["invocations"] == 1


async def test_runs_endpoint_returns_real_rows_now_that_the_db_import_is_fixed():
    org = f"org_runs_{uuid.uuid4().hex[:5]}"
    cid = await _case(org)
    await _run(cid, "clinical_extractor", latency=1234, tin=5, tout=6)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u",
        "email": "a@b.c",
        "organization_id": org,
        "role": "admin",
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            body = (await c.get("/api/v1/agents/clinical_extractor/runs")).json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert "db_unavailable" not in body
    assert len(body["runs"]) == 1 and body["runs"][0]["latency_ms"] == 1234
