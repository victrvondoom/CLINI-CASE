"""Atomic tenant-scoped JSONB records. Memory fallback permits synthetic data ONLY."""

from __future__ import annotations

import threading

from fastapi import HTTPException

from app.db import db
from app.onehealth.models import ExposureRecord

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS onehealth_exposures (
 organization_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id, id)
);
"""
_memory: dict[tuple[str, str], ExposureRecord] = {}
_lock = threading.Lock()


def mode() -> str:
    return "postgresql" if db._pool is not None else "volatile_synthetic_demo_only"


async def ensure_schema() -> None:
    await db.execute(SCHEMA_SQL)


async def list_records(org: str) -> list[ExposureRecord]:
    if mode() == "postgresql":
        rows = await db.fetch(
            "SELECT payload FROM onehealth_exposures WHERE organization_id=$1", org
        )
        return [ExposureRecord.model_validate_json(r["payload"]) for r in rows]
    with _lock:
        return [r.model_copy(deep=True) for (tenant, _), r in _memory.items() if tenant == org]


async def get(org: str, record_id: str) -> ExposureRecord:
    for row in await list_records(org):
        if row.id == record_id:
            return row
    raise HTTPException(404, "Exposure record not found")


async def save(record: ExposureRecord, expected: int | None = None) -> ExposureRecord:
    """CAS update keeps record, reviewer decision, tasks and audit together."""
    updated = record.model_copy(deep=True)
    updated.version = 1 if expected is None else expected + 1
    if mode() == "postgresql":
        if expected is None:
            result = await db.fetchval(
                "INSERT INTO onehealth_exposures VALUES ($1,$2,$3,$4::jsonb) ON CONFLICT DO NOTHING RETURNING version",
                updated.organization_id,
                updated.id,
                updated.version,
                updated.model_dump_json(),
            )
        else:
            result = await db.fetchval(
                "UPDATE onehealth_exposures SET version=$3,payload=$4::jsonb WHERE organization_id=$1 AND id=$2 AND version=$5 RETURNING version",
                updated.organization_id,
                updated.id,
                updated.version,
                updated.model_dump_json(),
                expected,
            )
        if result is None:
            raise HTTPException(409, "Record changed; reload before retrying")
    else:
        if not updated.synthetic:
            raise HTTPException(
                503, "Persistent database required for non-synthetic exposure evidence"
            )
        key = (updated.organization_id, updated.id)
        with _lock:
            previous = _memory.get(key)
            if (expected is None and previous) or (
                expected is not None and (not previous or previous.version != expected)
            ):
                raise HTTPException(409, "Record changed; reload before retrying")
            _memory[key] = updated.model_copy(deep=True)
    return updated
