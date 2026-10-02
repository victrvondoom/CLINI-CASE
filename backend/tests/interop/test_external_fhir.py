"""Third-party FHIR check: synthetic-only, server-config-only, never fatal, never retries the POST."""

import copy
import json

import httpx
import pytest
from fastapi import FastAPI
from test_fhir_api import valid_bundle

from app.api import interop as interop_api
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import external_fhir, repository

BASE = "https://fhir.example.test/baseR4"


class FakeServer:
    """A generic FHIR R4 server: stores any Bundle, assigns an id, returns it unchanged unless told not to."""

    def __init__(self, mutate=None, post_status=201, get_status=200, outage=None):
        self.store, self.calls = {}, []
        self.mutate, self.post_status, self.get_status, self.outage = mutate, post_status, get_status, outage

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if self.outage:
            raise self.outage("simulated outage", request=request)
        if request.method == "POST":
            if self.post_status not in (200, 201):
                return httpx.Response(self.post_status, json={"resourceType": "OperationOutcome"})
            body = json.loads(request.content)
            rid = f"srv-{len(self.store) + 1}"
            self.store[rid] = {**body, "id": rid}
            return httpx.Response(self.post_status, json=self.store[rid])
        rid = request.url.path.rsplit("/", 1)[-1]
        if self.get_status != 200 or rid not in self.store:
            return httpx.Response(self.get_status if self.get_status != 200 else 404)
        data = copy.deepcopy(self.store[rid])
        return httpx.Response(200, json=self.mutate(data) if self.mutate else data)

    def client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


async def run(server, **kw):
    return await external_fhir.exchange(
        valid_bundle(),
        synthetic=kw.pop("synthetic", True),
        base_url=BASE,
        request_timeout_s=5,
        client=server.client(),
        **kw,
    )


def change_value(bundle):
    obs = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation")
    obs["valueQuantity"]["value"] = 999
    return bundle


async def test_round_trip_through_a_generic_server_passes_and_records_the_evidence():
    server = FakeServer()
    result = await run(server)
    assert result["status"] == "passed" and result["endpoint"] == BASE
    assert result["resource_type"] == "Bundle" and result["resource_id"] == "srv-1"
    assert result["request"]["status_code"] == 201 and result["retrieval"]["status_code"] == 200
    assert result["semantic"]["fields_preserved"] == result["semantic"]["fields_total"] == 5
    assert "not an OAH conformance result" in result["scope_note"]


async def test_a_server_that_alters_content_fails_and_names_the_field():
    result = await run(FakeServer(mutate=change_value))
    assert result["status"] == "failed"
    assert [f["field"] for f in result["semantic"]["fields"] if not f["preserved"]] == ["sample"]


@pytest.mark.parametrize(
    ("server", "status"),
    [
        (FakeServer(outage=httpx.ConnectError), "unavailable"),
        (FakeServer(outage=httpx.ReadTimeout), "unavailable"),
        (FakeServer(post_status=422), "rejected"),
        (FakeServer(get_status=500), "failed"),
        (FakeServer(mutate=lambda b: {"resourceType": "Bundle", "type": "collection", "entry": []}), "failed"),
    ],
)
async def test_every_failure_mode_is_a_fixed_category_not_an_exception(server, status, monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(external_fhir.asyncio, "sleep", instant)
    result = await run(server)
    assert result["status"] == status
    assert "Traceback" not in result["detail"] and "httpx" not in result["detail"]


async def test_non_synthetic_data_is_refused_before_any_network_call():
    server = FakeServer()
    with pytest.raises(external_fhir.ExternalFhirRefusedError):
        await run(server, synthetic=False)
    assert server.calls == []


async def test_post_is_never_retried_but_reads_are(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(external_fhir.asyncio, "sleep", instant)
    server = FakeServer(get_status=503)
    await run(server)
    methods = [m for m, _ in server.calls]
    assert methods.count("POST") == 1 and methods.count("GET") == external_fhir.READ_ATTEMPTS


@pytest.fixture
async def api(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "")
    monkeypatch.setattr(settings, "EXTERNAL_FHIR_BASE_URL", BASE)
    repository._memory.clear()
    server = FakeServer()
    monkeypatch.setattr(external_fhir, "make_client", lambda _t, _s: server.client())
    app = FastAPI()
    app.include_router(interop_api.router, prefix="/api/v1")
    user = {"id": "ext-reviewer", "role": "reviewer", "organization_id": "ext-org"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, server
    repository._memory.clear()


async def generated_job(client):
    base = "/api/v1/interop"
    job = (await client.post(base + "/demo?variant=dissolved", json={})).json()

    async def step(path, **extra):
        nonlocal job
        response = await client.post(
            base + path, json={"job_id": job["id"], "expected_version": job["version"], **extra}
        )
        assert response.is_success, response.text
        job = response.json()

    await step("/map")
    for m in [m for m in job["mappings"] if m["decision"] == "pending"]:
        verb = "approve" if m["target"] else "reject"
        await step(f"/mappings/{job['id']}/{verb}", source_field=m["source_field"], target=m["target"])
    return job, step


async def test_endpoint_needs_a_validated_bundle_then_records_the_attempt_as_an_event(api):
    client, server = api
    job, step = await generated_job(client)
    early = await client.post(
        "/api/v1/interop/external-check", json={"job_id": job["id"], "expected_version": job["version"]}
    )
    assert early.status_code == 409 and server.calls == []
    await step("/generate-fhir")
    version = (await client.get(f"/api/v1/interop/jobs/{job['id']}")).json()["version"]
    done = await client.post(
        "/api/v1/interop/external-check", json={"job_id": job["id"], "expected_version": version}
    )
    assert done.status_code == 200 and done.json()["external"]["status"] == "passed"
    assert [e["event_type"] for e in done.json()["job"]["events"]][-1] == "external_fhir_check_passed"


async def test_unavailable_server_does_not_break_the_job(api, monkeypatch):
    client, _ = api
    down = FakeServer(outage=httpx.ConnectError)
    monkeypatch.setattr(external_fhir, "make_client", lambda _t, _s: down.client())
    job, step = await generated_job(client)
    await step("/generate-fhir")
    version = (await client.get(f"/api/v1/interop/jobs/{job['id']}")).json()["version"]
    response = await client.post(
        "/api/v1/interop/external-check", json={"job_id": job["id"], "expected_version": version}
    )
    assert response.status_code == 200 and response.json()["external"]["status"] == "unavailable"
    transfer = await client.post(
        "/api/v1/interop/transfer",
        json={"job_id": job["id"], "expected_version": response.json()["job"]["version"]},
    )
    assert transfer.status_code == 200 and transfer.json()["transfers"][-1]["status"] == "delivered"
