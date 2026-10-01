"""Independent simulator: only HTTP FHIR input, separate SQLite storage.
Run: python -m uvicorn app.interop.receiver:app --port 8091
Set INTEROP_RECEIVER_TOKEN and INTEROP_RECEIVER_DB for a network deployment.
"""

import json
import secrets
import sqlite3
import threading
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
    result = validate(payload.bundle)
    if not result["valid"]:
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
    with _lock:
        old = _connection.execute(
            "SELECT digest FROM receipts WHERE tenant=? AND correlation=?",
            (x_tenant, payload.correlation_id),
        ).fetchone()
        if old and old[0] != result["sha256"]:
            raise HTTPException(409, "Correlation ID already bound to a different content hash")
        _connection.execute(
            "INSERT OR IGNORE INTO receipts VALUES (?,?,?,?,?)",
            (
                x_tenant,
                payload.correlation_id,
                result["sha256"],
                json.dumps(payload.bundle),
                json.dumps(representation),
            ),
        )
        _connection.commit()
    return {
        "status": "delivered",
        "correlation_id": payload.correlation_id,
        "sha256": result["sha256"],
        "resources_acknowledged": len(payload.bundle["entry"]),
        "representation": representation,
    }


@app.get("/exchanges/{correlation_id}")
async def returned(
    correlation_id: str, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    authorize(x_tenant, x_receiver_token)
    with _lock:
        row = _connection.execute(
            "SELECT bundle,representation FROM receipts WHERE tenant=? AND correlation=?",
            (x_tenant, correlation_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Receiver exchange not found")
    return {
        "bundle": json.loads(row[0]),
        "representation": json.loads(row[1]),
        "direction": "clinical-to-lab",
    }


@app.post("/lab/fhir")
async def lab_receive(
    payload: Receive, x_tenant: str = Header(), x_receiver_token: str = Header()
) -> dict[str, Any]:
    # A separate receiver namespace stores only the returned common FHIR representation.
    copy = payload.model_copy(update={"correlation_id": "lab-" + payload.correlation_id})
    return await receive(copy, x_tenant, x_receiver_token)
