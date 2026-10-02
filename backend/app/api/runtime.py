"""Runtime topology: what this deployment actually is, from its own configuration and probes.

Every value comes from the process environment (incl. the Kubernetes Downward API), server
configuration, the live route table, or a probe of a server-configured URL — never a
client-supplied one, so this endpoint cannot be steered at arbitrary hosts. Credentials are
never returned, and probe failures are reported as fixed categories, not exception text.
"""

from __future__ import annotations

import asyncio
import os
import platform
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute

from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.onehealth.repository import mode

router = APIRouter(prefix="/runtime", tags=["runtime"])
PROBE_TIMEOUT_S = 1.5


def _client() -> httpx.AsyncClient:
    """HTTP probe client (tests swap in an ASGI or mock transport)."""
    return httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, follow_redirects=False)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _endpoint(url: str) -> str | None:
    """host:port only — userinfo (credentials) is dropped."""
    parts = urlsplit(url)
    if not parts.hostname:
        return None
    return f"{parts.hostname}:{parts.port}" if parts.port else parts.hostname


def _result(status: str, detail: str, started: float | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "detail": detail,
        "probe_ms": round((time.perf_counter() - started) * 1000, 1) if started else None,
        "checked_at": _now(),
    }


def _platform() -> dict[str, Any]:
    env = os.environ
    in_k8s = bool(env.get("KUBERNETES_SERVICE_HOST"))
    dockerenv = Path("/.dockerenv").exists()
    detected = [
        name
        for name, present in (
            ("KUBERNETES_SERVICE_HOST", in_k8s),
            ("Downward API", bool(env.get("POD_NAME"))),
            ("/.dockerenv", dockerenv),
        )
        if present
    ]
    return {
        "kind": "kubernetes" if in_k8s else "container" if dockerenv else "process",
        "provider": env.get("RUNTIME_PLATFORM") or None,
        "namespace": env.get("POD_NAMESPACE") or None,
        "pod": env.get("POD_NAME") or None,
        "node": env.get("NODE_NAME") or None,
        "pod_ip": env.get("POD_IP") or None,
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "detected_from": detected,
    }


async def _probe_http(base_url: str) -> dict[str, Any]:
    if urlsplit(base_url).scheme not in ("http", "https"):
        return _result("misconfigured", "Configured URL is not http(s)")
    started = time.perf_counter()
    try:
        async with _client() as client:
            response = await client.get(base_url.rstrip("/") + "/healthz")
    except httpx.TimeoutException:
        return _result("down", "Health probe timed out", started)
    except httpx.HTTPError:
        return _result("down", "Unreachable", started)
    if response.status_code == 200:
        return _result("up", "GET /healthz returned 200", started)
    return _result("down", f"GET /healthz returned {response.status_code}", started)


async def _probe_database(persistence: str) -> dict[str, Any]:
    if persistence == "sqlite_synthetic_demo_only":
        return _result("up", "SQLite synthetic demo store (local file)")
    if persistence != "postgresql":
        return _result("up", "In-memory synthetic store; no database configured")
    started = time.perf_counter()
    try:
        await asyncio.wait_for(db.fetchval("SELECT 1"), PROBE_TIMEOUT_S)
    except TimeoutError:
        return _result("down", "SELECT 1 timed out", started)
    except Exception:  # noqa: BLE001 - reachability only; never echo driver errors
        return _result("down", "SELECT 1 failed", started)
    return _result("up", "SELECT 1 succeeded", started)


async def _probe_redis(url: str) -> dict[str, Any]:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return _result("not_probed", "Redis client library not installed")
    started = time.perf_counter()
    client = aioredis.from_url(  # type: ignore[no-untyped-call]
        url, socket_timeout=PROBE_TIMEOUT_S, socket_connect_timeout=PROBE_TIMEOUT_S
    )
    try:
        await asyncio.wait_for(client.ping(), PROBE_TIMEOUT_S)
    except Exception:  # noqa: BLE001 - reachability only
        return _result("down", "PING failed", started)
    finally:
        await client.aclose()
    return _result("up", "PING succeeded", started)


async def _static(result: dict[str, Any]) -> dict[str, Any]:
    return result


def _routes(request: Request) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    methods: dict[str, set[str]] = {}
    for route in request.app.routes:
        if not isinstance(route, APIRoute):
            continue
        parts = route.path.split("/")
        prefix = "/".join(parts[:4]) if route.path.startswith("/api/v1/") else "/".join(parts[:2]) or "/"
        counts[prefix] = counts.get(prefix, 0) + 1
        methods.setdefault(prefix, set()).update(route.methods or ())
    return [
        {"prefix": prefix, "routes": counts[prefix], "methods": sorted(methods[prefix] - {"HEAD"})}
        for prefix in sorted(counts)
    ]


@router.get("")
async def runtime_topology(
    request: Request, _user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    env = os.environ
    host = _platform()
    in_k8s = host["kind"] == "kubernetes"
    workload = "Deployment" if in_k8s else None
    persistence = mode()
    frontend_url = env.get("RUNTIME_FRONTEND_URL", "")
    receiver_url = settings.INTEROP_RECEIVER_URL
    frontend, receiver, database, redis = await asyncio.gather(
        _probe_http(frontend_url)
        if frontend_url
        else _static(_result("not_probed", "No RUNTIME_FRONTEND_URL configured; your browser loaded the UI directly")),
        _probe_http(receiver_url)
        if receiver_url
        else _static(_result("embedded", "Independent ASGI app called in-process with separate SQLite storage")),
        _probe_database(persistence),
        _probe_redis(settings.REDIS_URL) if settings.REDIS_URL else _static({}),
    )
    server = request.scope.get("server")
    services: list[dict[str, Any]] = [
        {
            "id": "frontend",
            "name": "Web frontend",
            "role": "Unified CLINI-CASE interface; proxies /api and /fhir to the API",
            "image": env.get("RUNTIME_FRONTEND_IMAGE") or None,
            "endpoint": _endpoint(frontend_url) if frontend_url else None,
            "health_path": "/healthz",
            "workload": workload,
            **frontend,
        },
        {
            "id": "api",
            "name": "API",
            "role": "One application API: journey, interop, One Health, oncology, twins, FHIR",
            "image": env.get("CLINICASE_IMAGE") or None,
            "endpoint": f"{server[0]}:{server[1]}" if server else None,
            "health_path": "/api/v1/healthz",
            "workload": workload,
            **_result("up", "Answered this request"),
        },
        {
            "id": "receiver",
            "name": "System B receiver",
            "role": "Independent FHIR receiver: validates, reassigns IDs, returns bundles",
            "image": env.get("RUNTIME_RECEIVER_IMAGE") or None,
            "endpoint": _endpoint(receiver_url) if receiver_url else None,
            "health_path": "/healthz",
            "workload": workload if receiver_url else None,
            **receiver,
        },
        {
            "id": "database",
            "name": "Evidence store",
            "role": "Cases, jobs, evidence records and passports",
            "engine": persistence,
            "image": None,
            "endpoint": _endpoint(settings.DATABASE_URL) if persistence == "postgresql" else None,
            "health_path": None,
            "workload": "StatefulSet" if in_k8s and persistence == "postgresql" else None,
            **database,
        },
    ]
    if settings.REDIS_URL:
        services.append(
            {
                "id": "redis",
                "name": "Live trace fan-out",
                "role": "Redis pub/sub for multi-replica live traces",
                "image": None,
                "endpoint": _endpoint(settings.REDIS_URL),
                "health_path": None,
                "workload": workload,
                **redis,
            }
        )
    edges = [
        {"from": "frontend", "to": "api", "protocol": "HTTP · /api, /fhir"},
        {
            "from": "api",
            "to": "receiver",
            "protocol": "HTTP FHIR · service token" if receiver_url else "In-process ASGI",
        },
        {"from": "api", "to": "database", "protocol": "PostgreSQL" if persistence == "postgresql" else "Local store"},
    ]
    if settings.REDIS_URL:
        edges.append({"from": "api", "to": "redis", "protocol": "Redis pub/sub"})
    routes = _routes(request)
    return {
        "label": "Live cluster topology" if in_k8s else "Deployment topology",
        "live": in_k8s,
        "platform": host,
        "services": services,
        "edges": edges,
        "routes": routes,
        "route_count": sum(group["routes"] for group in routes),
        "generated_at": _now(),
        "notice": "Statuses are live probes of server-configured endpoints taken for this request. "
        "No CPU, memory, replica or cloud metrics are collected.",
    }
