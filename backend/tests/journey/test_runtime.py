"""Runtime topology must report only real configuration and live probes, never secrets."""

import httpx
import pytest
from fastapi import FastAPI

from app.api import journey as journey_api
from app.api import runtime as runtime_api
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import receiver

K8S_ENV = ("KUBERNETES_SERVICE_HOST", "POD_NAME", "POD_NAMESPACE", "NODE_NAME", "POD_IP")
RUNTIME_ENV = ("RUNTIME_PLATFORM", "RUNTIME_FRONTEND_URL", "RUNTIME_FRONTEND_IMAGE", "RUNTIME_RECEIVER_IMAGE", "CLINICASE_IMAGE")


@pytest.fixture
def app(monkeypatch):
    for name in K8S_ENV + RUNTIME_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "")
    monkeypatch.setattr(settings, "REDIS_URL", "")
    application = FastAPI()
    application.include_router(runtime_api.router, prefix="/api/v1")
    application.include_router(journey_api.router, prefix="/api/v1")
    application.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "role": "reviewer",
        "organization_id": "o1",
    }
    return application


async def _get(application):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as session:
        return await session.get("/api/v1/runtime")


def _service(body, service_id):
    return next(s for s in body["services"] if s["id"] == service_id)


async def test_runtime_requires_authentication(app):
    app.dependency_overrides.clear()
    assert (await _get(app)).status_code == 401


async def test_runtime_topology_is_reviewer_or_admin_only(app):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u2",
        "role": "coordinator",
        "organization_id": "o1",
    }
    assert (await _get(app)).status_code == 403


async def test_local_process_is_labelled_deployment_topology_without_secrets(app, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://clincase:s3cr3t-pass@db.internal:5432/clincase")
    response = await _get(app)
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "Deployment topology" and body["live"] is False
    assert body["platform"]["pod"] is None
    assert _service(body, "api")["status"] == "up"
    assert _service(body, "receiver")["status"] == "embedded"
    assert _service(body, "frontend")["status"] == "not_probed"
    assert _service(body, "database")["status"] == "up"  # in-memory synthetic store
    assert "s3cr3t-pass" not in response.text
    prefixes = {group["prefix"] for group in body["routes"]}
    assert {"/api/v1/runtime", "/api/v1/journey"} <= prefixes
    assert body["route_count"] == sum(group["routes"] for group in body["routes"])


async def test_kubernetes_identity_and_live_probes_of_configured_services(app, monkeypatch):
    for name, value in {
        "KUBERNETES_SERVICE_HOST": "10.96.0.1",
        "POD_NAME": "api-7c9d",
        "POD_NAMESPACE": "clinicase",
        "NODE_NAME": "clinicase-control-plane",
        "RUNTIME_PLATFORM": "kind",
        "CLINICASE_IMAGE": "clinicase-api:local",
        "RUNTIME_RECEIVER_IMAGE": "clinicase-api:local",
        "RUNTIME_FRONTEND_URL": "http://frontend:5173",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "http://receiver:8091")

    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(
        runtime_api,
        "_client",
        lambda: httpx.AsyncClient(
            mounts={
                "http://receiver:8091": httpx.ASGITransport(app=receiver.app),  # the real System B
                "http://frontend:5173": httpx.MockTransport(refuse),
            }
        ),
    )
    body = (await _get(app)).json()
    assert body["label"] == "Live cluster topology" and body["live"] is True
    assert body["platform"].items() >= {
        "kind": "kubernetes",
        "provider": "kind",
        "pod": "api-7c9d",
        "namespace": "clinicase",
        "node": "clinicase-control-plane",
    }.items()
    system_b = _service(body, "receiver")
    assert system_b["status"] == "up" and system_b["endpoint"] == "receiver:8091"
    assert system_b["workload"] == "Deployment" and system_b["probe_ms"] is not None
    frontend = _service(body, "frontend")
    assert frontend["status"] == "down" and frontend["detail"] == "Unreachable"
    assert _service(body, "api")["image"] == "clinicase-api:local"
    assert {"from": "api", "to": "receiver", "protocol": "HTTP FHIR · service token"} in body["edges"]


async def test_probe_timeouts_are_reported_as_a_fixed_category(app, monkeypatch):
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "http://receiver:8091")

    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(
        runtime_api, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(slow))
    )
    receiver_status = _service((await _get(app)).json(), "receiver")
    assert receiver_status["status"] == "down" and receiver_status["detail"] == "Health probe timed out"


async def test_non_http_configuration_is_never_fetched(app, monkeypatch):
    monkeypatch.setenv("RUNTIME_FRONTEND_URL", "file:///etc/passwd")
    calls = []
    monkeypatch.setattr(runtime_api, "_client", lambda: calls.append(1))
    frontend = _service((await _get(app)).json(), "frontend")
    assert frontend["status"] == "misconfigured" and calls == []
