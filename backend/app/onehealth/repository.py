"""Atomic tenant-scoped JSONB records. Memory fallback permits synthetic data ONLY."""

from __future__ import annotations

import threading

from fastapi import HTTPException

from app.db import db
from app.onehealth import demo_store, passport
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
    from app.config import settings

    if db._pool is not None:
        return "postgresql"
    return (
        "sqlite_synthetic_demo_only" if settings.TRACK7_DEMO_DB else "volatile_synthetic_demo_only"
    )


async def ensure_schema() -> None:
    await db.execute(SCHEMA_SQL)


async def list_records(org: str) -> list[ExposureRecord]:
    if mode() == "postgresql":
        rows = await db.fetch(
            "SELECT payload FROM onehealth_exposures WHERE organization_id=$1", org
        )
        return [ExposureRecord.model_validate_json(r["payload"]) for r in rows]
    if mode() == "sqlite_synthetic_demo_only":
        return [ExposureRecord.model_validate(r) for r in demo_store.rows("exposure", org)]
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
        assert db._pool is not None
        async with db._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT payload FROM onehealth_exposures WHERE organization_id=$1 AND id=$2 FOR UPDATE",
                updated.organization_id,
                updated.id,
            )
            import json

            previous = json.loads(row["payload"]) if row else None
            if (expected is None and previous) or (
                expected is not None and (not previous or previous["version"] != expected)
            ):
                raise HTTPException(409, "Record changed; reload before retrying")
            updated = ExposureRecord.model_validate(
                passport.seal(updated.model_dump(mode="json"), previous)
            )
            if expected is None:
                result = await conn.fetchval(
                    "INSERT INTO onehealth_exposures VALUES ($1,$2,$3,$4::jsonb) ON CONFLICT DO NOTHING RETURNING version",
                    updated.organization_id,
                    updated.id,
                    updated.version,
                    updated.model_dump_json(),
                )
            else:
                result = await conn.fetchval(
                    "UPDATE onehealth_exposures SET version=$3,payload=$4::jsonb WHERE organization_id=$1 AND id=$2 AND version=$5 RETURNING version",
                    updated.organization_id,
                    updated.id,
                    updated.version,
                    updated.model_dump_json(),
                    expected,
                )
            if result is None:
                raise HTTPException(409, "Record changed; reload before retrying")
        return updated
    if mode() == "sqlite_synthetic_demo_only":
        return ExposureRecord.model_validate(
            demo_store.save("exposure", updated.model_dump(mode="json"), expected)
        )
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
            updated = ExposureRecord.model_validate(
                passport.seal(
                    updated.model_dump(mode="json"),
                    previous.model_dump(mode="json") if previous else None,
                )
            )
            _memory[key] = updated.model_copy(deep=True)
    return updated


async def save_retest(
    original: ExposureRecord, successor: ExposureRecord, expected: int
) -> tuple[ExposureRecord, ExposureRecord]:
    """Two related records commit together; a stale request creates neither."""
    original = original.model_copy(deep=True)
    successor = successor.model_copy(deep=True)
    original.version = expected + 1
    successor.version = 1
    if mode() == "postgresql":
        import json

        assert db._pool is not None
        async with db._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT payload FROM onehealth_exposures WHERE organization_id=$1 AND id=$2 FOR UPDATE",
                original.organization_id,
                original.id,
            )
            previous = json.loads(row["payload"]) if row else None
            if not previous or previous["version"] != expected:
                raise HTTPException(409, "Record changed; reload before retrying")
            original = ExposureRecord.model_validate(
                passport.seal(original.model_dump(mode="json"), previous)
            )
            successor = ExposureRecord.model_validate(
                passport.seal(successor.model_dump(mode="json"), None)
            )
            await conn.execute(
                "INSERT INTO onehealth_exposures VALUES ($1,$2,$3,$4::jsonb)",
                successor.organization_id,
                successor.id,
                1,
                successor.model_dump_json(),
            )
            await conn.execute(
                "UPDATE onehealth_exposures SET version=$3,payload=$4::jsonb WHERE organization_id=$1 AND id=$2",
                original.organization_id,
                original.id,
                original.version,
                original.model_dump_json(),
            )
    elif mode() == "sqlite_synthetic_demo_only":
        with demo_store.connection() as conn:
            original = ExposureRecord.model_validate(
                demo_store.write(conn, "exposure", original.model_dump(mode="json"), expected)
            )
            successor = ExposureRecord.model_validate(
                demo_store.write(conn, "exposure", successor.model_dump(mode="json"), None)
            )
    else:
        if not original.synthetic or not successor.synthetic:
            raise HTTPException(503, "Persistent database required for non-synthetic evidence")
        with _lock:
            previous_record = _memory.get((original.organization_id, original.id))
            if (
                not previous_record
                or previous_record.version != expected
                or (successor.organization_id, successor.id) in _memory
            ):
                raise HTTPException(409, "Record changed; reload before retrying")
            original = ExposureRecord.model_validate(
                passport.seal(
                    original.model_dump(mode="json"), previous_record.model_dump(mode="json")
                )
            )
            successor = ExposureRecord.model_validate(
                passport.seal(successor.model_dump(mode="json"), None)
            )
            _memory[(original.organization_id, original.id)] = original.model_copy(deep=True)
            _memory[(successor.organization_id, successor.id)] = successor.model_copy(deep=True)
    return original, successor
