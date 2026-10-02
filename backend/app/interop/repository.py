"""Separate tenant-scoped artifacts and CAS metadata, synthetic-only memory fallback."""

import json
import threading

from fastapi import HTTPException

from app.db import db
from app.interop.models import Job
from app.onehealth import demo_store, passport
from app.onehealth.repository import mode

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS interop_jobs (
 organization_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id,id));
CREATE TABLE IF NOT EXISTS interop_artifacts (
 organization_id TEXT NOT NULL, job_id TEXT NOT NULL, kind TEXT NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id,job_id,kind));
"""
_memory: dict[tuple[str, str], Job] = {}
_lock = threading.Lock()
ARTIFACTS = (
    "source",
    "fields",
    "mappings",
    "normalized",
    "bundle",
    "validation",
    "transfers",
    "events",
    "passport",
)


async def ensure_schema() -> None:
    await db.execute(SCHEMA_SQL)


async def get(org: str, jid: str) -> Job:
    if mode() == "postgresql":
        assert db._pool is not None
        async with (
            db._pool.acquire() as conn,
            conn.transaction(isolation="repeatable_read", readonly=True),
        ):
            row = await conn.fetchrow(
                "SELECT payload FROM interop_jobs WHERE organization_id=$1 AND id=$2", org, jid
            )
            if row:
                data = json.loads(row["payload"])
                parts = await conn.fetch(
                    "SELECT kind,payload FROM interop_artifacts WHERE organization_id=$1 AND job_id=$2",
                    org,
                    jid,
                )
                data.update({r["kind"]: json.loads(r["payload"]) for r in parts})
                return Job.model_validate(data)
    elif mode() == "sqlite_synthetic_demo_only":
        for data in demo_store.rows("job", org):
            if data["id"] == jid:
                return Job.model_validate(data)
    else:
        with _lock:
            if (org, jid) in _memory:
                return _memory[org, jid].model_copy(deep=True)
    raise HTTPException(404, "Mapping job not found in this organisation")


async def bound_jobs(org: str, exposure_id: str) -> list[Job]:
    if mode() == "postgresql":
        rows = await db.fetch(
            "SELECT id FROM interop_jobs WHERE organization_id=$1 AND payload->>'exposure_id'=$2",
            org,
            exposure_id,
        )
        return [await get(org, row["id"]) for row in rows]
    if mode() == "sqlite_synthetic_demo_only":
        return [
            Job.model_validate(data)
            for data in demo_store.rows("job", org)
            if data.get("exposure_id") == exposure_id
        ]
    with _lock:
        return [
            job.model_copy(deep=True)
            for (tenant, _), job in _memory.items()
            if tenant == org and job.exposure_id == exposure_id
        ]


def _last_activity(job: Job) -> str:
    return job.events[-1].timestamp if job.events else ""


async def recent(org: str, limit: int = 12) -> list[Job]:
    """Read-only: the tenant's most recently active jobs, newest first."""
    if mode() == "postgresql":
        rows = await db.fetch(
            "SELECT j.id FROM interop_jobs j LEFT JOIN interop_artifacts a"
            " ON a.organization_id=j.organization_id AND a.job_id=j.id AND a.kind='events'"
            " WHERE j.organization_id=$1"
            " ORDER BY a.payload->-1->>'timestamp' DESC NULLS LAST, j.id LIMIT $2",
            org,
            limit,
        )
        return [await get(org, row["id"]) for row in rows]
    if mode() == "sqlite_synthetic_demo_only":
        jobs = [Job.model_validate(data) for data in demo_store.rows("job", org)]
    else:
        with _lock:
            jobs = [job.model_copy(deep=True) for (tenant, _), job in _memory.items() if tenant == org]
    return sorted(jobs, key=_last_activity, reverse=True)[:limit]


async def save(job: Job, expected: int | None = None) -> Job:
    j = job.model_copy(deep=True)
    j.version = 1 if expected is None else expected + 1
    if mode() == "postgresql":
        assert db._pool is not None
        async with db._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT payload FROM interop_jobs WHERE organization_id=$1 AND id=$2 FOR UPDATE",
                j.organization_id,
                j.id,
            )
            previous = json.loads(row["payload"]) if row else None
            if previous:
                previous_parts = await conn.fetch(
                    "SELECT kind,payload FROM interop_artifacts WHERE organization_id=$1 AND job_id=$2",
                    j.organization_id,
                    j.id,
                )
                previous.update({r["kind"]: json.loads(r["payload"]) for r in previous_parts})
            if (expected is None and previous) or (
                expected is not None and (not previous or previous["version"] != expected)
            ):
                raise HTTPException(409, "Job changed; reload before retrying")
            j = Job.model_validate(passport.seal(j.model_dump(mode="json"), previous))
            data = j.model_dump(mode="json")
            parts = {k: data.pop(k) for k in ARTIFACTS}
            if expected is None:
                result = await conn.fetchval(
                    "INSERT INTO interop_jobs VALUES ($1,$2,$3,$4::jsonb) ON CONFLICT DO NOTHING RETURNING version",
                    j.organization_id,
                    j.id,
                    j.version,
                    json.dumps(data),
                )
            else:
                result = await conn.fetchval(
                    "UPDATE interop_jobs SET version=$3,payload=$4::jsonb WHERE organization_id=$1 AND id=$2 AND version=$5 RETURNING version",
                    j.organization_id,
                    j.id,
                    j.version,
                    json.dumps(data),
                    expected,
                )
            if result is None:
                raise HTTPException(409, "Job changed; reload before retrying")
            for kind, part in parts.items():
                await conn.execute(
                    "INSERT INTO interop_artifacts VALUES ($1,$2,$3,$4::jsonb) ON CONFLICT (organization_id,job_id,kind) DO UPDATE SET payload=EXCLUDED.payload",
                    j.organization_id,
                    j.id,
                    kind,
                    json.dumps(part),
                )
    elif mode() == "sqlite_synthetic_demo_only":
        j = Job.model_validate(demo_store.save("job", j.model_dump(mode="json"), expected))
    else:
        if not j.source.synthetic:
            raise HTTPException(503, "Persistent database required for non-synthetic data")
        with _lock:
            previous = _memory.get((j.organization_id, j.id))
            if (expected is None and previous) or (
                expected is not None and (not previous or previous.version != expected)
            ):
                raise HTTPException(409, "Job changed; reload before retrying")
            j = Job.model_validate(
                passport.seal(
                    j.model_dump(mode="json"),
                    previous.model_dump(mode="json") if previous else None,
                )
            )
            _memory[j.organization_id, j.id] = j.model_copy(deep=True)
    return j
