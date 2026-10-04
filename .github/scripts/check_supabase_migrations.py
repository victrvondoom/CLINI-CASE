"""Replay Supabase migrations against an empty, loopback-only CI database."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg

ROOT = Path(__file__).resolve().parents[2]


async def check() -> None:
    dsn = os.environ["MIGRATION_TEST_DATABASE_URL"]
    parsed = urlsplit(dsn)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.endswith("_ci"):
        raise RuntimeError("Migration replay requires an isolated loopback database ending in _ci")
    migrations = sorted((ROOT / "supabase/migrations").glob("*.sql"))
    versions = [path.name.split("_", 1)[0] for path in migrations]
    if not migrations or len(set(versions)) != len(versions):
        raise RuntimeError("Migration history must have unique versions")
    if not all(re.fullmatch(r"\d{14}_[a-z0-9_]+\.sql", path.name) for path in migrations):
        raise RuntimeError("Migration filenames must use timestamp_name.sql")
    conn = await asyncpg.connect(dsn, ssl=False, timeout=15)
    try:
        if await conn.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname='public'"):
            raise RuntimeError("Migration replay requires an empty public schema")
        # Supabase provisions this schema before user migrations.
        await conn.execute("CREATE SCHEMA extensions; SET search_path = public, extensions")
        for attempt in range(2):
            for path in migrations:
                async with conn.transaction():
                    await conn.execute(path.read_text(encoding="utf-8"))
            rows = await conn.fetch(
                "SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n "
                "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r'"
            )
            if len(rows) != 34 or any(not row["relrowsecurity"] for row in rows):
                raise RuntimeError("All 34 backend-owned tables must exist with RLS enabled")
            if await conn.fetchval("SELECT count(*) FROM pg_policies WHERE schemaname='public'"):
                raise RuntimeError("Backend-owned tables must have no public Data API policies")
            print(f"Migration replay {attempt + 1}: {len(migrations)} migrations, 34 RLS tables")
        # A synthetic seed proves owner access works and public-style access is denied.
        if await conn.fetchval("SELECT count(*) FROM organizations WHERE id='org_demo'") != 1:
            raise RuntimeError("Backend owner lost access to the synthetic seed")
        transaction = conn.transaction()
        await transaction.start()
        try:
            await conn.execute(
                "CREATE ROLE migration_anon_ci NOLOGIN NOSUPERUSER NOBYPASSRLS; "
                "GRANT USAGE ON SCHEMA public TO migration_anon_ci; "
                "GRANT SELECT ON ALL TABLES IN SCHEMA public TO migration_anon_ci; "
                "SET LOCAL ROLE migration_anon_ci"
            )
            if await conn.fetchval("SELECT count(*) FROM organizations") != 0:
                raise RuntimeError("RLS permitted a public-style role to read backend data")
        finally:
            await transaction.rollback()
        print("RLS access proof: backend owner can read; public-style role reads zero rows")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
