"""Contract test for the Da Vinci PAS / CMS-0057-F § IV.A endpoint.

Verifies that POST /fhir/Claim/$submit:
  - Accepts a Da Vinci PAS-shaped Claim Bundle.
  - Returns a Bundle whose first entry is a ClaimResponse with use="preauthorization".
  - Rejects Bundles missing a Claim resource.
  - Rejects Claims with use != "preauthorization".
  - Advertises Da Vinci PAS conformance via /fhir/metadata.

These tests use FastAPI's TestClient with the auth dependency overridden so
we don't need a live DB session per test.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.db import db
from app.main import app

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _fake_user() -> dict[str, Any]:
    # Use a real seeded user so the cases.created_by_user_id FK is satisfied.
    # The startup lifespan in app.main seeds these three demo users.
    return {
        "id": "user_demoadmin",
        "email": "admin@aerofyta.health",
        "organization_id": "org_demo",
        "role": "admin",
    }


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """ASGI client with auth bypass + minimal DB."""
    app.dependency_overrides[get_current_user] = _fake_user
    await db.connect()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c
    await db.disconnect()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pas_submit_trastuzumab_returns_claimresponse(client: AsyncClient) -> None:
    bundle = json.loads((FIXTURES / "pas_submit_trastuzumab.json").read_text())
    response = await client.post("/fhir/Claim/$submit", json=bundle)
    assert response.status_code == 200, response.text
    body = response.json()

    # Top-level must be a Bundle with PAS profile tagged
    assert body["resourceType"] == "Bundle"
    profiles = body.get("meta", {}).get("profile", [])
    assert any("davinci-pas" in p for p in profiles), "Response Bundle must declare PAS profile"

    # Must include a CMS-0057-F regulatory tag
    tags = body.get("meta", {}).get("tag", [])
    assert any(
        t.get("code", "").startswith("CMS-0057-F") for t in tags
    ), "Response must carry the CMS-0057-F regulatory tag"

    # First entry: ClaimResponse with use=preauthorization
    entries = body.get("entry", [])
    assert len(entries) >= 2, "Expected ClaimResponse + Provenance entries"
    cr = entries[0]["resource"]
    assert cr["resourceType"] == "ClaimResponse"
    assert cr["use"] == "preauthorization"
    assert cr["outcome"] in {"queued", "complete", "partial", "error"}, (
        f"outcome must be a PAS-conformant value, got: {cr.get('outcome')!r}"
    )
    assert cr.get("preAuthRef"), "preAuthRef must be set so payer can poll"
    assert cr.get("preAuthPeriod", {}).get("end"), (
        "preAuthPeriod.end must be set per CMS-0057-F § IV.B"
    )

    # Second entry: Provenance pointing back at the ClaimResponse
    prov = entries[1]["resource"]
    assert prov["resourceType"] == "Provenance"
    assert prov["target"][0]["reference"].startswith("ClaimResponse/")
    assert "ClinCase" in prov["agent"][0]["who"]["display"]


@pytest.mark.asyncio
async def test_pas_submit_rejects_missing_claim(client: AsyncClient) -> None:
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
    response = await client.post("/fhir/Claim/$submit", json=bundle)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "missing_claim"
    assert "PAS" in detail["spec"]


@pytest.mark.asyncio
async def test_pas_submit_rejects_wrong_use(client: AsyncClient) -> None:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Claim",
                    "use": "claim",  # not preauthorization
                    "patient": {"reference": "Patient/x"},
                }
            }
        ],
    }
    response = await client.post("/fhir/Claim/$submit", json=bundle)
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "wrong_use"


@pytest.mark.asyncio
async def test_capability_statement_advertises_pas(client: AsyncClient) -> None:
    response = await client.get("/fhir/metadata")
    assert response.status_code == 200
    cs = response.json()
    assert cs["resourceType"] == "CapabilityStatement"
    igs = cs.get("implementationGuide", [])
    assert any("davinci-pas" in ig for ig in igs), (
        "CapabilityStatement must declare Da Vinci PAS IG"
    )
    # $submit operation declared
    rest_ops = (
        cs.get("rest", [{}])[0].get("resource", [{}])[0].get("operation", [])
    )
    assert any(op.get("name") == "submit" for op in rest_ops), (
        "Claim/$submit operation must be advertised"
    )
