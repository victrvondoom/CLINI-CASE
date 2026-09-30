"""Cohort analytics: every number is derived from case rows (pure logic), scoped per org (SQL), never fixtures."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.analytics.cohorts import MIN_DECIDED_PER_GROUP, compute_cohorts
from app.auth import get_current_user
from app.main import app


def row(payer="aetna", tx="trastuzumab", verdict="APPROVE", dur=120.0, status="approved"):
    return {
        "id": uuid.uuid4().hex,
        "payer_id": payer,
        "treatment": tx,
        "status": status,
        "verdict": verdict,
        "dur_s": dur,
    }


def test_empty_input_is_an_honest_empty_report():
    r = compute_cohorts([], days=90)
    assert r["total_cases"] == 0 and r["decided_cases"] == 0
    assert r["approval_by_payer"] == [] and r["verdict_by_treatment"] == [] and r["insights"] == []
    assert [b["count"] for b in r["time_to_decision"]["buckets"]] == [0] * 6
    assert r["time_to_decision"]["median_seconds"] is None


def test_counts_and_verdicts_come_from_rows():
    rows = (
        [row(verdict="APPROVE")] * 5
        + [row(verdict="DENY")] * 2
        + [row(verdict="REFER")]
        + [row(verdict=None, dur=None, status="pending")] * 3
    )
    r = compute_cohorts(rows, days=30)
    assert (r["total_cases"], r["decided_cases"], r["pending_cases"]) == (11, 8, 3)
    assert r["verdicts"] == {"APPROVE": 5, "DENY": 2, "REFER": 1}
    assert r["window_days"] == 30


def test_approval_rate_by_payer():
    rows = (
        [row("aetna")] * 3
        + [row("aetna", verdict="DENY")]
        + [row("uhc")] * 2
        + [row("uhc", verdict="REFER")] * 2
    )
    by = {p["payer"]: p for p in compute_cohorts(rows, days=90)["approval_by_payer"]}
    assert by["aetna"]["rate"] == 75.0 and by["aetna"]["decided"] == 4
    assert by["uhc"]["rate"] == 50.0 and by["uhc"]["refer"] == 2


def test_time_buckets_and_quantiles():
    rows = [row(dur=d) for d in (30, 90, 200, 400, 900, 4000)]
    t = compute_cohorts(rows, days=90)["time_to_decision"]
    assert [b["count"] for b in t["buckets"]] == [1, 1, 1, 1, 1, 1]
    assert t["timed_cases"] == 6 and t["median_seconds"] == pytest.approx(300.0)
    assert t["p90_seconds"] is not None and t["p90_seconds"] > 900


def test_undecided_and_negative_durations_are_excluded_from_timing():
    rows = [row(dur=-5.0), row(verdict=None, dur=None, status="running"), row(dur=60.0)]
    t = compute_cohorts(rows, days=90)["time_to_decision"]
    assert t["timed_cases"] == 1


def test_verdict_by_treatment_is_normalised_and_capped():
    rows = [row(tx="Trastuzumab"), row(tx="trastuzumab "), row(tx="olaparib", verdict="DENY")]
    v = {x["treatment"]: x for x in compute_cohorts(rows, days=90)["verdict_by_treatment"]}
    assert v["trastuzumab"]["approve"] == 2 and v["olaparib"]["deny"] == 1
    many = [row(tx=f"drug{i}") for i in range(20)]
    assert len(compute_cohorts(many, days=90)["verdict_by_treatment"]) == 8


def test_insights_require_enough_evidence():
    few = [row("aetna"), row("uhc", verdict="DENY")]
    assert (
        compute_cohorts(few, days=90)["insights"] == []
    )  # below MIN_DECIDED_PER_GROUP: nothing is invented


def test_insights_are_derived_from_the_data():
    rows = (
        [row("aetna")] * 5
        + [row("uhc")] * 2
        + [row("uhc", verdict="DENY")] * 3
        + [row("uhc", tx="olaparib", verdict="REFER")] * 0
    )
    ins = {i["id"]: i for i in compute_cohorts(rows, days=90)["insights"]}
    gap = ins["payer-approval-gap"]
    assert "aetna approves 100% vs uhc 40%" in gap["title"] and gap["metric"] == "60 pp"
    assert "human-review-load" in ins and "decision-speed" in ins
    assert MIN_DECIDED_PER_GROUP == 3


def test_appeal_insight_uses_case_status():
    rows = [row(status="overturned")] * 3 + [row(status="appealed")]
    ins = {i["id"]: i for i in compute_cohorts(rows, days=90)["insights"]}
    assert ins["appeal-outcomes"]["metric"] == "75%"


def _user(org="org_cohort_api"):
    return {"id": "u1", "email": "a@b.c", "full_name": "x", "organization_id": org, "role": "admin"}


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: _user()
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_returns_computed_report_for_callers_org(client, monkeypatch):
    seen = {}

    async def fake_rows(org, days):
        seen.update(org=org, days=days)
        return [row("aetna")] * 4

    monkeypatch.setattr("app.api.cohorts.fetch_cohort_rows", fake_rows)
    r = client.get("/api/v1/cohorts?days=30")
    assert r.status_code == 200
    body = r.json()
    assert seen == {"org": "org_cohort_api", "days": 30}
    assert body["total_cases"] == 4 and body["approval_by_payer"][0]["payer"] == "aetna"


def test_endpoint_validates_window_and_degrades_to_503(client, monkeypatch):
    assert client.get("/api/v1/cohorts?days=0").status_code == 422
    assert client.get("/api/v1/cohorts?days=9999").status_code == 422

    async def boom(org, days):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.api.cohorts.fetch_cohort_rows", boom)
    r = client.get("/api/v1/cohorts")
    assert r.status_code == 503 and "database" in r.json()["detail"]


def test_endpoint_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/api/v1/cohorts").status_code in (401, 403)
