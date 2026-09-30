"""SQL behaviour of the cohort query against a real PostgreSQL schema (CI job: integration + postgres)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.cohorts import compute_cohorts, fetch_cohort_rows
from app.db import db

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


async def _org(org: str) -> None:
    await db.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $1, $1) ON CONFLICT (id) DO NOTHING",
        org,
    )


async def _case(org, payer, tx, status, verdict, secs, age_days=0):
    cid = f"cohort-{uuid.uuid4().hex[:10]}"
    created = datetime.now(UTC) - timedelta(days=age_days)
    await db.execute(
        """INSERT INTO cases (id, created_at, organization_id, payer_id, patient_initials,
                              requested_treatment_name, fhir_bundle, status)
           VALUES ($1,$2,$3,$4,'T.T.',$5,'{}'::jsonb,$6)""",
        cid,
        created,
        org,
        payer,
        tx,
        status,
    )
    if verdict:
        await db.execute(
            """INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence, created_at)
               VALUES ($1,$2,'r','[]'::jsonb,0.9,$3)""",
            cid,
            verdict,
            created + timedelta(seconds=secs),
        )
    return cid


async def test_query_is_org_scoped_windowed_and_uses_latest_decision():
    a, b = f"org_a_{uuid.uuid4().hex[:6]}", f"org_b_{uuid.uuid4().hex[:6]}"
    await _org(a)
    await _org(b)
    await _case(a, "aetna", "trastuzumab", "approved", "APPROVE", 90)
    await _case(a, "aetna", "trastuzumab", "denied", "DENY", 200)
    pending = await _case(a, "uhc", "olaparib", "pending", None, 0)
    await _case(
        a, "uhc", "olaparib", "approved", "APPROVE", 30, age_days=200
    )  # outside a 90-day window
    await _case(b, "bcbs", "osimertinib", "approved", "APPROVE", 45)  # other tenant

    # a second, later decision on the same case must supersede the first
    await db.execute(
        "INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence) VALUES ($1,'REFER','r','[]'::jsonb,0.5)",
        pending,
    )
    rows = await fetch_cohort_rows(a, 90)
    assert len(rows) == 3  # own org, inside the window
    assert {r["payer_id"] for r in rows} == {"aetna", "uhc"}
    rep = compute_cohorts(rows, days=90)
    assert rep["verdicts"] == {"APPROVE": 1, "DENY": 1, "REFER": 1}
    assert len(await fetch_cohort_rows(a, 365)) == 4
    assert [r["payer_id"] for r in await fetch_cohort_rows(b, 90)] == ["bcbs"]
