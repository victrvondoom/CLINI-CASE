"""Asyncpg connection pools — write (primary) + read (Aurora reader endpoint).

Round-9 had a single pool against the primary. At 50+ pods × 20 connections
each, we'd blow past Aurora's `max_connections` budget. Round-12 splits:

  • Writer pool  → Aurora primary (DATABASE_URL)
  • Reader pool  → Aurora reader endpoint (DATABASE_READ_URL); falls back
                   to writer when not configured

Reads from `db.fetch_ro(...)` use the reader pool. Hot-path queries that
don't need write-after-read consistency (audit, dashboards, analytics)
should use the read API. Writes + write-after-read still go to the
writer pool via `db.execute / fetchrow / fetch / fetchval`.

In production both pools are fronted by **PgBouncer** in transaction-pooling
mode (see `ops/k8s/pgbouncer/`). This multiplexes per-pod connections
onto a small backend connection pool — turning 50 pods × 20 conns into
50 pods × 20 client conns × 1 backend conn per active txn. Without
PgBouncer, Aurora's max_connections becomes the cluster-wide ceiling.

Use:
    await db.fetchrow("SELECT 1")             # reads + writes against primary
    await db.fetch_ro("SELECT 1")             # reader endpoint
    await db.execute("INSERT ...", val)
"""
from __future__ import annotations

import os
from typing import Any

import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger()

# Pool size tuning — these MUST be set per-replica in K8s manifest:
#   _DB_POOL_MAX_SIZE = floor(aurora_max_connections / max_pods / 2)
# Default of 10 is safe for a 100-conn Aurora primary at 5 pods. Override
# via env in production.
_DB_POOL_MIN = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
_DB_POOL_MAX = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
_DB_RO_POOL_MAX = int(os.getenv("DB_RO_POOL_MAX_SIZE", str(_DB_POOL_MAX)))


class Database:
    """Asyncpg writer + reader pools with lazy connect/disconnect."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._ro_pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=_DB_POOL_MIN,
                max_size=_DB_POOL_MAX,
                command_timeout=30,
            )
            logger.info(
                "db.connected",
                role="writer",
                max_size=_DB_POOL_MAX,
                dsn_host=settings.DATABASE_URL.split("@")[-1],
            )
        # Optional reader pool — Aurora reader endpoint
        ro_url = os.getenv("DATABASE_READ_URL", "").strip()
        if ro_url and self._ro_pool is None:
            try:
                self._ro_pool = await asyncpg.create_pool(
                    dsn=ro_url,
                    min_size=_DB_POOL_MIN,
                    max_size=_DB_RO_POOL_MAX,
                    command_timeout=30,
                )
                logger.info(
                    "db.connected",
                    role="reader",
                    max_size=_DB_RO_POOL_MAX,
                    dsn_host=ro_url.split("@")[-1],
                )
            except Exception as e:  # noqa: BLE001
                # Don't fail the whole bootstrap — fall back to writer pool.
                logger.warning("db.reader_pool.failed", error=str(e))

    async def disconnect(self) -> None:
        for attr in ("_ro_pool", "_pool"):
            p = getattr(self, attr)
            if p is not None:
                await p.close()
                setattr(self, attr, None)
        logger.info("db.disconnected")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    @property
    def ro_pool(self) -> asyncpg.Pool:
        """Reader pool. Falls back to writer if not configured."""
        return self._ro_pool or self.pool

    # -------------------------------------------------------------------------
    # Writer-side primitives (everything mutating + read-after-write)
    # -------------------------------------------------------------------------

    async def execute(self, query: str, *args: Any) -> str:
        return await self.pool.execute(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        return await self.pool.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        return await self.pool.fetch(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self.pool.fetchval(query, *args)

    # -------------------------------------------------------------------------
    # Reader-side primitives (analytics, audit, dashboards — anything tolerant
    # of a few hundred ms of replica lag).
    # -------------------------------------------------------------------------

    async def fetchrow_ro(self, query: str, *args: Any) -> asyncpg.Record | None:
        return await self.ro_pool.fetchrow(query, *args)

    async def fetch_ro(self, query: str, *args: Any) -> list[asyncpg.Record]:
        return await self.ro_pool.fetch(query, *args)

    async def fetchval_ro(self, query: str, *args: Any) -> Any:
        return await self.ro_pool.fetchval(query, *args)

    # -------------------------------------------------------------------------
    # Snapshot — for /healthz/deep + /architecture descriptor
    # -------------------------------------------------------------------------

    def pool_snapshot(self) -> dict[str, Any]:
        snap: dict[str, Any] = {
            "writer_pool": {
                "configured": self._pool is not None,
                "max_size": _DB_POOL_MAX,
            },
            "reader_pool": {
                "configured": self._ro_pool is not None,
                "max_size": _DB_RO_POOL_MAX,
                "fallback_to_writer": self._ro_pool is None,
            },
            "pgbouncer_recommended": "ops/k8s/pgbouncer/ — transaction pooling at scale",
        }
        return snap


db = Database()
