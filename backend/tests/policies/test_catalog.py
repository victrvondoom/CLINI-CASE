"""Policy catalog: counts are computed from the corpus, diffs match whole drugs only, open cases come from the DB."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import policy_catalog as pc
from app.auth import get_current_user
from app.db import db
from app.main import app

CORPUS = json.loads((Path(pc._DATA) / "policies.json").read_text())["policies"]


def test_catalog_counts_are_computed_from_the_corpus():
    c = pc.catalog()
    assert c["n"] == len(CORPUS) == len(c["policies"])
    assert c["payers"] == sorted({p["payer_id"] for p in CORPUS})
    first = c["policies"][0]
    src = CORPUS[0]
    assert first["section_count"] == len(src["sections"])
    assert first["word_count"] == sum(
        len(__import__("re").findall(r"\w+", s["text"])) for s in src["sections"]
    )
    assert c["n_with_recent_change"] == sum(1 for p in c["policies"] if p["has_recent_change"])


def test_payer_name_mapping():
    assert [
        pc.payer_id_from_name(n)
        for n in ("Aetna", "UnitedHealthcare", "BCBS", "Blue Cross Blue Shield", "Anthem", "Cigna")
    ] == ["aetna", "uhc", "bcbs", "bcbs", "anthem", "cigna"]


def test_diffs_match_whole_drug_names_only():
    aetna_olaparib = next(
        p for p in CORPUS if p["payer_id"] == "aetna" and "olaparib" in p["treatment_keywords"]
    )
    anthem_trastuzumab = next(
        p for p in CORPUS if p["payer_id"] == "anthem" and "trastuzumab" in p["treatment_keywords"]
    )
    assert any(d["treatment"] == "olaparib" for d in pc._diffs_for(aetna_olaparib))
    # Anthem's change is for trastuzumab DERUXTECAN — it must not be attributed to plain trastuzumab
    assert pc._diffs_for(anthem_trastuzumab) == []
    assert pc._drug_names("trastuzumab deruxtecan (T-DXd)") == {"trastuzumab deruxtecan", "t-dxd"}


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u",
        "email": "a@b.c",
        "organization_id": "org_pc",
        "role": "admin",
        "full_name": "x",
    }
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_list_endpoint(client):
    body = client.get("/api/v1/policy-catalog").json()
    assert body["n"] == len(CORPUS) and "snapshot" in body


def test_detail_endpoint_with_and_without_database(client, monkeypatch):
    async def fake(org, policy, limit=50):
        return [
            {
                "case_id": "x1",
                "patient": "A.B.",
                "treatment": "olaparib",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr(pc, "open_cases_for", fake)
    d = client.get("/api/v1/policy-catalog/0421").json()
    assert (
        d["policy_id"] == "0421"
        and d["diffs"]
        and d["sections"]
        and d["open_cases"][0]["case_id"] == "x1"
    )
    assert d["snapshot"]["taken_at"] and d["related"]

    async def boom(org, policy, limit=50):
        raise RuntimeError("down")

    monkeypatch.setattr(pc, "open_cases_for", boom)
    d2 = client.get("/api/v1/policy-catalog/0421").json()
    assert (
        d2["open_cases"] == [] and d2["open_cases_available"] is False
    )  # policy still served, honestly flagged
    assert client.get("/api/v1/policy-catalog/does-not-exist").status_code == 404


def test_case_insensitive_id_and_auth(client):
    assert client.get("/api/v1/policy-catalog/onCG-2025-d098").status_code == 200
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/api/v1/policy-catalog").status_code in (401, 403)


@pytest.mark.integration
@pytest.mark.postgres
async def test_open_cases_query_is_scoped_by_org_payer_status_and_drug():
    org, other = f"org_pc_{uuid.uuid4().hex[:5]}", f"org_pc_o_{uuid.uuid4().hex[:5]}"
    for o in (org, other):
        await db.execute(
            "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
            o,
        )

    async def case(o, payer, tx, status):
        cid = f"pc-{uuid.uuid4().hex[:8]}"
        await db.execute(
            "INSERT INTO cases (id, organization_id, payer_id, patient_initials, requested_treatment_name, fhir_bundle, status) VALUES ($1,$2,$3,'T.T.',$4,'{}'::jsonb,$5)",
            cid,
            o,
            payer,
            tx,
            status,
        )
        return cid

    policy = pc.find_policy("0421")  # aetna olaparib
    hit = await case(org, "aetna", "Olaparib 300mg", "pending")
    await case(org, "aetna", "olaparib", "approved")  # closed
    await case(org, "uhc", "olaparib", "pending")  # other payer
    await case(org, "aetna", "trastuzumab", "pending")  # other drug
    await case(other, "aetna", "olaparib", "pending")  # other tenant
    got = await pc.open_cases_for(org, policy)
    assert [g["case_id"] for g in got] == [hit]
