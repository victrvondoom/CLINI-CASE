"""OAH-Bridge HTTP routes, on a standalone app (no middleware), with auth overridden."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.api import oah_bridge
from app.auth import get_current_user
from app.oahbridge import weather

BASE = "/api/v1/oah-bridge"


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(oah_bridge.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": "coordinator", "organization_id": "org"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as session:
        yield session


async def test_routes_require_a_signed_in_user():
    app = FastAPI()
    app.include_router(oah_bridge.router, prefix="/api/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as session:
        assert (await session.get(f"{BASE}/scenarios")).status_code == 401


async def test_scenarios_and_demo_run(client):
    scenarios = (await client.get(f"{BASE}/scenarios")).json()
    assert {s["id"] for s in scenarios} == {"coimbra-cyanobacteria", "toulouse-diptera", "mondego-storm-surge"}

    run = (await client.get(f"{BASE}/demo/run", params={"scenario": "mondego-storm-surge"})).json()
    assert run["scenario"]["epistemic_status"] == "confirmed"
    assert run["validation_report"]["all_passed"] is True
    assert run["bundle"]["entry"][0]["fullUrl"].startswith(f"http://test{BASE}/fhir/")
    assert set(run["run"]["timings_ms"]) == {"ingest", "corroborate", "compose", "validate"}

    posted = await client.post(f"{BASE}/demo/run", json={"scenario": "toulouse-diptera"})
    assert posted.json()["scenario"]["id"] == "toulouse-diptera"


async def test_unknown_or_malformed_scenario_is_rejected(client):
    assert (await client.get(f"{BASE}/demo/run", params={"scenario": "atlantis"})).status_code == 404
    assert (await client.get(f"{BASE}/demo/run", params={"scenario": "<script>"})).status_code == 422


async def test_fhir_metadata_and_search(client):
    meta = await client.get(f"{BASE}/fhir/metadata")
    assert meta.headers["content-type"].startswith("application/fhir+json")
    assert meta.json()["implementation"]["url"] == f"http://test{BASE}/fhir"

    hits = (
        await client.get(
            f"{BASE}/fhir/Observation",
            params={"scenario": "coimbra-cyanobacteria", "oah-hazard": "cyanobacteria-proliferation"},
        )
    ).json()
    assert hits["type"] == "searchset" and hits["total"] == 1
    assert (await client.get(f"{BASE}/fhir/not-a-type")).status_code == 422


async def test_cds_hooks_discovery_and_advisory(client):
    discovery = (await client.get(f"{BASE}/cds-services")).json()
    assert discovery["services"][0]["hook"] == "patient-view"

    inside = await client.post(
        f"{BASE}/cds-services/oah-exposure-advisory",
        json={
            "hook": "patient-view",
            "hookInstance": "abc",
            "scenario": "coimbra-cyanobacteria",
            "context": {"patientId": "p1", "coordinates": [-8.4285, 40.2035]},
        },
    )
    assert inside.status_code == 200
    assert len(inside.json()["cards"]) == 1

    outside = await client.post(
        f"{BASE}/cds-services/oah-exposure-advisory",
        json={"scenario": "coimbra-cyanobacteria", "context": {"coordinates": [-8.6, 40.35]}},
    )
    assert outside.json()["cards"] == []

    wrong_hook = await client.post(f"{BASE}/cds-services/oah-exposure-advisory", json={"hook": "order-sign"})
    assert wrong_hook.status_code == 422
    bad_coords = await client.post(
        f"{BASE}/cds-services/oah-exposure-advisory", json={"context": {"coordinates": [500, 0]}}
    )
    assert bad_coords.status_code == 422


async def test_conformance_terminology_monitor(client):
    assert (await client.get(f"{BASE}/conformance")).json()["total"] >= 12
    assert (await client.get(f"{BASE}/terminology")).json()["concepts"]
    monitor = (await client.get(f"{BASE}/monitor")).json()
    assert monitor["status"] in {"operational", "degraded"}
    assert {c["id"] for c in monitor["components"]} >= {"engine", "validator", "weather"}


async def test_weather_takes_coordinates_in_the_body(client, monkeypatch):
    weather.reset_for_tests()
    seen: list[tuple[float, float]] = []

    async def fake(lat, lon):
        seen.append((lat, lon))
        raise httpx.ConnectError("offline in tests")

    monkeypatch.setattr(weather, "_fetch_upstream", fake)
    res = await client.post(f"{BASE}/weather", json={"latitude": 40.20351, "longitude": -8.42849})
    assert res.status_code == 200
    assert res.json()["mode"] == "unavailable"
    assert seen == [(40.2, -8.43)]
    assert (await client.post(f"{BASE}/weather", json={"latitude": 95, "longitude": 0})).status_code == 422
    weather.reset_for_tests()


def test_router_is_registered_before_the_spa_fallback():
    source = (Path(__file__).resolve().parents[2] / "app" / "main.py").read_text(encoding="utf-8")
    assert source.index("oah_bridge.router") < source.index("\n_mount_frontend()")
