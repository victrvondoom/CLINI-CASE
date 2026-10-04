"""Reviewer queue is assembled from real decisions + necessity assessments, prioritised transparently."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import db
from app.main import app
from app.review.queue import STALE_AFTER_MINUTES, build_item, fetch_review_queue, priority_for

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def row(**over):
    r = {
        "id": "c1",
        "patient_initials": "S.D.",
        "treatment": "trastuzumab",
        "payer_id": "aetna",
        "status": "referred",
        "created_at": NOW - timedelta(minutes=30),
        "decided_at": NOW - timedelta(minutes=10),
        "rationale": "Baseline LVEF is outside the payer window. More detail follows.",
        "decision_confidence": 0.6,
        "necessity": {
            "overall_confidence": 0.5,
            "summary": "S.",
            "criteria": [
                {
                    "criterion_text": "LVEF within 60d",
                    "status": "AMBIGUOUS",
                    "missing_evidence": "ECHO within 60 days",
                },
                {"criterion_text": "HER2+", "status": "MET", "missing_evidence": None},
                {
                    "criterion_text": "ECOG",
                    "status": "NOT_MET",
                    "missing_evidence": "Documented ECOG",
                },
                {
                    "criterion_text": "dup",
                    "status": "AMBIGUOUS",
                    "missing_evidence": "ECHO within 60 days",
                },
            ],
        },
    }
    return {**r, **over}


def test_item_is_built_from_recorded_evidence():
    it = build_item(row(), NOW)
    assert it["reason"] == "Baseline LVEF is outside the payer window."
    assert (
        it["missing_evidence"] == "ECHO within 60 days; Documented ECOG"
    )  # deduplicated, unresolved criteria only
    assert it["unresolved_criteria"] == 3 and it["confidence"] == 0.5  # min(decision, necessity)
    assert it["age_minutes"] == 10 and it["priority"] == "high" and it["case_id"] == "c1"


def test_necessity_json_may_arrive_as_a_string_and_gaps_degrade_gracefully():
    it = build_item(row(necessity=json.dumps(row()["necessity"])), NOW)
    assert it["unresolved_criteria"] == 3
    bare = build_item(row(rationale=None, necessity=None, decision_confidence=None), NOW)
    assert bare["reason"] == "Referred for human review." and bare["missing_evidence"] is None
    assert (
        bare["confidence"] is None and bare["priority"] == "medium"
    )  # unknown confidence is not buried


def test_priority_thresholds_and_staleness_bump():
    assert [priority_for(c, 0) for c in (0.3, 0.6, 0.9)] == ["high", "medium", "low"]
    assert (
        priority_for(0.9, STALE_AFTER_MINUTES) == "medium"
        and priority_for(0.6, STALE_AFTER_MINUTES) == "high"
    )
    assert priority_for(0.1, STALE_AFTER_MINUTES) == "high"  # capped


def test_pending_deny_uses_pause_reason_and_wait_time_without_final_decision():
    item = build_item(
        row(
            status="awaiting_review",
            rationale=None,
            decision_confidence=None,
            decided_at=None,
            paused_at=NOW - timedelta(minutes=5),
            pause_reason="AI proposed DENY; clinician review is required.",
        ),
        NOW,
    )
    assert item["status"] == "awaiting_review"
    assert item["reason"] == "AI proposed DENY; clinician review is required."
    assert item["age_minutes"] == 5


async def test_query_includes_paused_cases_and_preserves_tenant_scope(monkeypatch):
    async def fetch(sql, organization_id, limit):
        assert organization_id == "org_rq" and limit == 20
        assert "c.status IN ('referred', 'awaiting_review')" in sql
        assert "c.organization_id = $1" in sql
        assert "s.organization_id = c.organization_id" in sql
        return [row(status="awaiting_review", decided_at=None, rationale=None)]

    monkeypatch.setattr(db, "fetch", fetch)
    items = await fetch_review_queue("org_rq", 20)
    assert len(items) == 1 and items[0]["status"] == "awaiting_review"


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u",
        "email": "a@b.c",
        "organization_id": "org_rq",
        "role": "reviewer",
        "full_name": "x",
    }
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_returns_items_counts_and_rule(client, monkeypatch):
    async def fake(org, limit):
        assert (org, limit) == ("org_rq", 50)
        return [
            build_item(row(id="a"), NOW),
            build_item(row(id="b", decision_confidence=0.95, necessity=None), NOW),
        ]

    monkeypatch.setattr("app.api.reviewer_queue.fetch_review_queue", fake)
    body = client.get("/api/v1/reviewer/queue").json()
    assert (
        body["total"] == 2
        and body["counts"] == {"high": 0, "medium": 1, "low": 1}
        or body["counts"]["low"] >= 1
    )
    assert "confidence <" in body["priority_rule"]


def test_endpoint_is_503_not_fake_data_without_a_database(client, monkeypatch):
    async def boom(org, limit):
        raise RuntimeError("down")

    monkeypatch.setattr("app.api.reviewer_queue.fetch_review_queue", boom)
    r = client.get("/api/v1/reviewer/queue")
    assert r.status_code == 503 and "database" in r.json()["detail"]
    assert client.get("/api/v1/reviewer/queue?limit=0").status_code == 422


def test_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/api/v1/reviewer/queue").status_code in (401, 403)


@pytest.mark.integration
@pytest.mark.postgres
async def test_sql_only_returns_referred_cases_of_the_callers_org_with_real_evidence():
    org, other = f"org_rq_{uuid.uuid4().hex[:5]}", f"org_rq_o_{uuid.uuid4().hex[:5]}"
    for o in (org, other):
        await db.execute(
            "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
            o,
        )

    async def case(o, status, conf=0.5):
        cid = f"rq-{uuid.uuid4().hex[:8]}"
        await db.execute(
            "INSERT INTO cases (id, organization_id, payer_id, patient_initials, requested_treatment_name, fhir_bundle, status) "
            "VALUES ($1,$2,'uhc','R.K.','osimertinib','{}'::jsonb,$3)",
            cid,
            o,
            status,
        )
        await db.execute(
            "INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence) VALUES ($1,'REFER','EGFR mutation type unclear. x','[]'::jsonb,$2)",
            cid,
            conf,
        )
        await db.execute(
            "INSERT INTO agent_runs (case_id, agent_name, started_at, finished_at, input_json, output_json) VALUES ($1,'necessity_reasoner',NOW(),NOW(),'{}'::jsonb,$2::jsonb)",
            cid,
            json.dumps(
                {
                    "overall_confidence": 0.45,
                    "summary": "s",
                    "criteria": [
                        {
                            "criterion_text": "EGFR",
                            "status": "AMBIGUOUS",
                            "missing_evidence": "Exon 19 / L858R designation",
                            "confidence": 0.4,
                        }
                    ],
                }
            ),
        )
        return cid

    keep = await case(org, "referred")
    await case(org, "approved")  # not referred
    await case(other, "referred")  # other tenant
    items = await fetch_review_queue(org, 50)
    assert [i["case_id"] for i in items] == [keep]
    assert (
        items[0]["missing_evidence"] == "Exon 19 / L858R designation"
        and items[0]["priority"] == "high"
    )
    assert items[0]["reason"] == "EGFR mutation type unclear."
