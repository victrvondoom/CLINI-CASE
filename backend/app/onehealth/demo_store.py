"""Opt-in durable SQLite demo storage: synthetic only, never a clinical database."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.onehealth.passport import seal


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = Path(settings.TRACK7_DEMO_DB).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS evidence (namespace TEXT, tenant TEXT, id TEXT, version INTEGER, payload TEXT, PRIMARY KEY(namespace,tenant,id))"
        )
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(namespace: str, org: str) -> list[dict[str, Any]]:
    with connection() as conn:
        return [
            json.loads(r[0])
            for r in conn.execute(
                "SELECT payload FROM evidence WHERE namespace=? AND tenant=?", (namespace, org)
            )
        ]


def write(
    conn: sqlite3.Connection, namespace: str, data: dict[str, Any], expected: int | None
) -> dict[str, Any]:
    synthetic = data.get("synthetic", data.get("source", {}).get("synthetic", False))
    if not synthetic or settings.ENVIRONMENT != "dev":
        raise HTTPException(503, "SQLite demo storage accepts synthetic data in development only")
    key = (namespace, data["organization_id"], data["id"])
    row = conn.execute(
        "SELECT version,payload FROM evidence WHERE namespace=? AND tenant=? AND id=?", key
    ).fetchone()
    if (expected is None and row) or (expected is not None and (not row or row[0] != expected)):
        raise HTTPException(409, "Record changed; reload before retrying")
    result = seal(data, json.loads(row[1]) if row else None)
    conn.execute(
        "INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?)",
        (*key, result["version"], json.dumps(result)),
    )
    return result


def save(namespace: str, data: dict[str, Any], expected: int | None) -> dict[str, Any]:
    with connection() as conn:
        return write(conn, namespace, data, expected)
