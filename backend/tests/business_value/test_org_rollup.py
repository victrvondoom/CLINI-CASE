"""Org rollup: the dashboard's sparkline, month-over-month change and baselines are real, org-scoped values."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.business_value.roi import MANUAL_PA_COST_USD, MANUAL_PA_MINUTES, org_value_rollup
from app.db import db
from app.main import app


def test_fallback_payload_carries_the_baselines_and_an_empty_series(monkeypatch):
    async def boom(org):
        raise RuntimeError("no db")

    monkeypatch.setattr("app.api.business_value.org_value_rollup", boom)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u",
        "email": "a@b.c",
        "organization_id": "o",
        "role": "admin",
        "full_name": "x",
    }
    try:
        body = TestClient(app).get("/api/v1/business-value/org").json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert body["db_unavailable"] is True and body["daily_cases_7d"] == [0] * 7
    assert body["assumptions"] == {
        "manual_pa_cost_usd": MANUAL_PA_COST_USD,
        "manual_pa_minutes": MANUAL_PA_MINUTES,
    }
    assert body["avg_decision_change_pct"] is None


@pytest.mark.integration
@pytest.mark.postgres
async def test_daily_series_and_month_over_month_change_come_from_the_orgs_cases():
    org, other = f"org_bv_{uuid.uuid4().hex[:5]}", f"org_bv_o_{uuid.uuid4().hex[:5]}"
    for o in (org, other):
        await db.execute(
            "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
            o,
        )

    async def case(o, created, secs=None):
        cid = f"bv-{uuid.uuid4().hex[:8]}"
        await db.execute(
            "INSERT INTO cases (id, created_at, organization_id, payer_id, patient_initials, requested_treatment_name, fhir_bundle, status) VALUES ($1,$2,$3,'aetna','T.T.','x','{}'::jsonb,'approved')",
            cid,
            created,
            o,
        )
        if secs is not None:
            await db.execute(
                "INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence, created_at) VALUES ($1,'APPROVE','r','[]'::jsonb,0.9,$2)",
                cid,
                created + timedelta(seconds=secs),
            )

    now = datetime.now(UTC)
    for _ in range(3):
        await case(org, now, 100)  # today (may also be this month)
    await case(org, now - timedelta(days=2), 100)
    await case(org, now - timedelta(days=6), 100)
    await case(org, now - timedelta(days=30), 100)  # outside the 7-day series
    await case(other, now, 100)  # other tenant
    r = await org_value_rollup(org)
    assert r.daily_cases_7d[-1] == 3 and r.daily_cases_7d[-3] == 1 and r.daily_cases_7d[0] == 1
    assert sum(r.daily_cases_7d) == 5 and len(r.daily_cases_7d) == 7

    # previous calendar month at 400 s vs this month's ~100 s → about -75 %
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev = first_of_this_month - timedelta(days=5)
    org2 = f"org_bv2_{uuid.uuid4().hex[:5]}"
    await db.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
        org2,
    )
    await case(org2, prev, 400)
    await case(org2, first_of_this_month + timedelta(minutes=1), 100)
    r2 = await org_value_rollup(org2)
    assert r2.avg_decision_change_pct == pytest.approx(-75.0, abs=0.5)
    assert (
        await org_value_rollup(f"org_none_{uuid.uuid4().hex[:4]}")
    ).avg_decision_change_pct is None


def test_case_roi_serves_baseline_minutes_and_token_pricing():
    from app.business_value.roi import CaseROI, token_pricing

    r = CaseROI("c", "o", "APPROVE", 1500.0, 0.25, 1499.75, 17.0, 60.0, 18.0, None, [])
    assert r.manual_minutes == MANUAL_PA_MINUTES and r.token_pricing_usd_per_m == token_pricing()
    assert token_pricing()["haiku"]["in"] < token_pricing()["sonnet"]["in"]


def test_capabilities_counts_are_computed_from_the_running_code():
    from app.agents.manifest import total_sub_agents
    from app.compliance.cms_0057f import CLAUSES

    body = TestClient(app).get("/api/v1/capabilities").json()
    assert body["system"]["sub_agents"] == total_sub_agents() and body["system"]["agents"] == 7
    assert body["system"]["policies_indexed"] == 22 and body["system"]["payers"] == 4
    assert body["compliance"]["cms_0057f_clauses_tracked"] == len(CLAUSES)
