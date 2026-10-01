"""Independent simulator: only HTTP FHIR input, separate SQLite storage.
Run: python -m uvicorn app.interop.receiver:app --port 8091
Set INTEROP_RECEIVER_TOKEN and INTEROP_RECEIVER_DB for a network deployment.
"""

import copy
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from app.config import settings
from app.interop.models import Receive
from app.interop.service import assessment, validate
from app.onehealth import fhir

LOCAL_TOKEN = secrets.token_urlsafe(32)

app = FastAPI(title="Synthetic Independent Clinical Receiver")
_connection = sqlite3.connect(settings.INTEROP_RECEIVER_DB, check_same_thread=False)
_lock = threading.Lock()
_connection.execute(
    "CREATE TABLE IF NOT EXISTS receipts (tenant TEXT, correlation TEXT, digest TEXT, bundle TEXT, representation TEXT, PRIMARY KEY(tenant,correlation))"
)
if "withdrawn" not in {row[1] for row in _connection.execute("PRAGMA table_info(receipts)")}:
    _connection.execute("ALTER TABLE receipts ADD COLUMN withdrawn INTEGER NOT NULL DEFAULT 0")
_connection.execute(
    "CREATE TABLE IF NOT EXISTS rejection_log (tenant TEXT, correlation TEXT, digest TEXT, timestamp TEXT, outcome TEXT)"
)
_connection.commit()


def _reidentify(bundle: dict[str, Any], correlation_id: str, source_digest: str) -> dict[str, Any]:
    """Simulate System B assigning new resource IDs and rewriting every internal reference."""
    returned = copy.deepcopy(bundle)
    identities: dict[str, str] = {}
    full_urls: dict[str, str] = {}
    for entry in returned["entry"]:
        resource = entry["resource"]
        old_id = resource["id"]
        kind = resource["resourceType"]
        material = f"{correlation_id}\0{source_digest}\0{kind}\0{old_id}".encode()
        new_id = "b-" + hashlib.sha256(material).hexdigest()[:20]
        identities[f"{kind}/{old_id}"] = f"{kind}/{new_id}"
        if entry.get("fullUrl"):
            full_urls[entry["fullUrl"]] = f"https://system-b.invalid/fhir/{kind}/{new_id}"
        resource["id"] = new_id
    remap = {**identities, **full_urls}

    def references(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("reference"), str):
                node["reference"] = remap.get(node["reference"], node["reference"])
            for value in node.values():
                references(value)
        elif isinstance(node, list):
            for value in node:
                references(value)

    for entry in returned["entry"]:
        if entry.get("fullUrl"):
            entry["fullUrl"] = full_urls[entry["fullUrl"]]
        references(entry["resource"])
    returned["id"] = "b-" + hashlib.sha256(
        f"{correlation_id}\0{source_digest}\0Bundle".encode()
    ).hexdigest()[:20]
    references(returned)
    return returned


def authorize(tenant: str, token: str) -> None:
    import secrets

    expected = settings.INTEROP_RECEIVER_TOKEN or LOCAL_TOKEN
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(401, "Receiver service token required")
    if not tenant:
        raise HTTPException(403, "Tenant scope required")


@app.post("/fhir")
async def receive(
    payload: Receive, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    authorize(x_tenant, x_receiver_token)
    started = time.perf_counter()
    result = validate(payload.bundle)
    if not result["valid"]:
        from app.onehealth.models import now

        with _lock:
            _connection.execute(
                "INSERT INTO rejection_log VALUES (?,?,?,?,?)",
                (
                    x_tenant,
                    payload.correlation_id,
                    result["sha256"],
                    now().isoformat(),
                    json.dumps(result),
                ),
            )
            _connection.commit()
        raise HTTPException(422, result)
    if {"system": fhir.SYSTEM, "code": "synthetic"} not in payload.bundle["meta"]["tag"]:
        raise HTTPException(422, "This simulator accepts synthetic packages only")
    decoded = fhir.read_evidence(payload.bundle)
    representation = {
        "lab_result": decoded["sample"],
        "source_history": decoded["history"],
        "provenance": decoded["provenance"],
        "local_review": "pending",
        "local_lab_verified": False,
        "local_consent_confirmed": False,
        "evidence": assessment(payload.bundle),
    }
    returned_bundle = _reidentify(payload.bundle, payload.correlation_id, result["sha256"])
    returned_validation = validate(returned_bundle)
    if not returned_validation["valid"]:
        raise HTTPException(500, "Receiver ID reassignment broke the FHIR exchange")
    with _lock:
        old = _connection.execute(
            "SELECT digest,withdrawn FROM receipts WHERE tenant=? AND correlation=?",
            (x_tenant, payload.correlation_id),
        ).fetchone()
        if old and old[1]:
            raise HTTPException(409, "Exchange sharing withdrawn")
        if old and old[0] != result["sha256"]:
            raise HTTPException(409, "Correlation ID already bound to a different content hash")
        _connection.execute(
            "INSERT OR IGNORE INTO receipts (tenant,correlation,digest,bundle,representation) VALUES (?,?,?,?,?)",
            (
                x_tenant,
                payload.correlation_id,
                result["sha256"],
                json.dumps(returned_bundle),
                json.dumps(representation),
            ),
        )
        _connection.commit()
    return {
        "status": "delivered",
        "correlation_id": payload.correlation_id,
        "sha256": result["sha256"],
        "resources_acknowledged": len(payload.bundle["entry"]),
        "resource_ids_reassigned": True,
        "returned_sha256": returned_validation["sha256"],
        "processing_ms": round((time.perf_counter() - started) * 1000, 2),
        "representation": representation,
    }


@app.get("/exchanges/{correlation_id}")
async def returned(
    correlation_id: str, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    authorize(x_tenant, x_receiver_token)
    with _lock:
        row = _connection.execute(
            "SELECT bundle,representation,withdrawn FROM receipts WHERE tenant=? AND correlation=?",
            (x_tenant, correlation_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Receiver exchange not found")
    if row[2]:
        raise HTTPException(403, "Sharing withdrawn; historical receipt retained but not exposed")
    return {
        "bundle": json.loads(row[0]),
        "sha256": fhir.digest(json.loads(row[0])),
        "representation": json.loads(row[1]),
        "resource_ids_reassigned": True,
        "direction": "clinical-to-lab",
    }


@app.post("/lab/fhir")
async def lab_receive(
    payload: Receive, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    # A separate receiver namespace stores only the returned common FHIR representation.
    copy = payload.model_copy(update={"correlation_id": "lab-" + payload.correlation_id})
    result = await receive(copy, x_tenant, x_receiver_token)
    result["correlation_id"] = payload.correlation_id
    return result


@app.post("/exchanges/{correlation_id}/withdraw")
async def withdraw(
    correlation_id: str, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    authorize(x_tenant, x_receiver_token)
    with _lock:
        _connection.execute(
            "UPDATE receipts SET withdrawn=1 WHERE tenant=? AND correlation IN (?,?)",
            (x_tenant, correlation_id, "lab-" + correlation_id),
        )
        _connection.commit()
    return {
        "status": "withdrawn",
        "correlation_id": correlation_id,
        "notice": "Previously downloaded copies cannot be recalled; historical receipt retained.",
    }
