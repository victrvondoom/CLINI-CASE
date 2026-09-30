"""fetch_twin against a real PostgreSQL schema (CI job: integration + postgres)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.db import db
from app.twin import case_intelligence_id, fetch_twin

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


async def _org(org: str) -> None:
    await db.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $1, $1) ON CONFLICT (id) DO NOTHING",
        org,
    )


async def test_fetch_twin_end_to_end_and_tenant_scoped():
    org, other = f"twin-{uuid.uuid4().hex[:8]}", f"twin-{uuid.uuid4().hex[:8]}"
    await _org(org)
    await _org(other)
    cid = f"twin-{uuid.uuid4().hex[:10]}"
    bundle = {"entry": [{"resource": {"resourceType": "Observation", "id": "obs-her2"}}]}
    await db.execute(
        """INSERT INTO cases (id, organization_id, payer_id, patient_initials,
                              requested_treatment_name, fhir_bundle, status)
           VALUES ($1,$2,'aetna','T.T.','Trastuzumab',$3::jsonb,'approved')""",
        cid,
        org,
        json.dumps(bundle),
    )
    await db.execute(
        """INSERT INTO agent_runs (case_id, agent_name, started_at, finished_at, input_json,
                                   output_json, latency_ms, model_id, input_tokens, output_tokens)
           VALUES ($1,'necessity_reasoner',NOW(),NOW(),'{}'::jsonb,
                   $2::jsonb,1200,'anthropic.claude-sonnet',900,150)""",
        cid,
        json.dumps({"criteria": [{"criterion_text": "HER2+", "status": "MET", "confidence": 0.9}]}),
    )
    await db.execute(
        """INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence)
           VALUES ($1,'APPROVE','r',$2::jsonb,0.88)""",
        cid,
        json.dumps([{"kind": "clinical", "text": "HER2 3+", "pointer": "obs-her2"}]),
    )

    twin = await fetch_twin(org, cid)
    assert twin is not None
    assert twin["case_intelligence_id"] == case_intelligence_id(org, cid)
    assert twin["evidence"][0]["resolved"] is True
    assert twin["policy"]["criteria_met"] == 1
    assert twin["agent_history"][0]["latency_ms"] == 1200
    assert twin["outcome"]["final"] is True

    assert await fetch_twin(other, cid) is None  # another tenant cannot see it
