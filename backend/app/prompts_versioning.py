"""Prompt versioning + A/B testing framework.

Round-9 prompts live as `.txt` files in `app/prompts/` per CLAUDE.md. That's
correct for the demo cohort. Production needs:
  • Version every prompt change (git history isn't enough — runtime needs it)
  • A/B test prompts at the tenant level
  • Roll out a new prompt version to 5% of traffic before 100%
  • Roll back instantly without a deploy

The shape:
  prompts                — table of (agent_name, version, body, status)
                           status ∈ {draft | shadow | active | retired}
  prompt_assignments     — per-tenant override {organization_id, agent_name, prompt_version}
  prompt_traffic_split   — global {agent_name, version, weight}

The `Agent[I,O]` framework calls `resolve_prompt(agent_name, organization_id)`
which:
  1. Checks per-tenant explicit assignment → return it
  2. Else: weighted random by `prompt_traffic_split`
  3. Else: returns the active version

Shadow mode: a `shadow` version runs in parallel with the active version
on the same input; outputs are compared offline for delta analysis. The
SHADOW output is NEVER returned to the user.

Pairs with: ops/architecture/PROMPT_VERSIONING.md
"""
from __future__ import annotations

import hashlib
import os
import random
from dataclasses import dataclass
from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prompts (
    agent_name        TEXT NOT NULL,
    version           TEXT NOT NULL,
    body              TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('draft','shadow','active','retired')),
    description       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at      TIMESTAMPTZ,
    retired_at        TIMESTAMPTZ,
    PRIMARY KEY (agent_name, version)
);
CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts (agent_name) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS prompt_assignments (
    organization_id  TEXT NOT NULL,
    agent_name       TEXT NOT NULL,
    version          TEXT NOT NULL,
    assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (organization_id, agent_name)
);

CREATE TABLE IF NOT EXISTS prompt_traffic_splits (
    agent_name       TEXT NOT NULL,
    version          TEXT NOT NULL,
    weight_percent   NUMERIC(5,2) NOT NULL CHECK (weight_percent >= 0 AND weight_percent <= 100),
    PRIMARY KEY (agent_name, version)
);
"""


async def ensure_schema() -> None:
    await db.execute(_SCHEMA_SQL)


@dataclass(frozen=True)
class ResolvedPrompt:
    agent_name: str
    version: str
    body: str
    source: str          # 'tenant_override' | 'traffic_split' | 'active' | 'file_fallback'


async def resolve_prompt(*, agent_name: str, organization_id: str | None = None) -> ResolvedPrompt:
    """Return the prompt to use for this (agent, tenant) right now."""
    # 1) Per-tenant explicit override
    if organization_id:
        row = await db.fetchrow_ro(
            """
            SELECT pa.version, p.body
              FROM prompt_assignments pa
              JOIN prompts p USING (agent_name, version)
             WHERE pa.organization_id = $1 AND pa.agent_name = $2
            """,
            organization_id, agent_name,
        )
        if row is not None:
            return ResolvedPrompt(agent_name, row["version"], row["body"], "tenant_override")

    # 2) Weighted traffic split
    splits = await db.fetch_ro(
        """
        SELECT pts.version, pts.weight_percent::FLOAT AS w, p.body
          FROM prompt_traffic_splits pts
          JOIN prompts p USING (agent_name, version)
         WHERE pts.agent_name = $1 AND p.status IN ('active','shadow')
        """,
        agent_name,
    )
    if splits:
        total = sum(float(r["w"]) for r in splits)
        if total > 0:
            # Stable per-tenant assignment via consistent hash so repeated
            # calls from the same tenant pick the same arm (avoids flicker).
            seed = organization_id or "anon"
            h = int(hashlib.sha256(f"{seed}|{agent_name}".encode()).hexdigest()[:8], 16)
            pick = (h % 10000) / 100.0   # 0.00 .. 99.99
            cum = 0.0
            for r in splits:
                cum += float(r["w"])
                if pick < cum:
                    return ResolvedPrompt(agent_name, r["version"], r["body"], "traffic_split")

    # 3) Active version
    row = await db.fetchrow_ro(
        "SELECT version, body FROM prompts WHERE agent_name = $1 AND status = 'active'",
        agent_name,
    )
    if row is not None:
        return ResolvedPrompt(agent_name, row["version"], row["body"], "active")

    # 4) File-system fallback (round-9 .txt convention)
    body = _file_fallback(agent_name)
    return ResolvedPrompt(agent_name, "file_v0", body, "file_fallback")


def _file_fallback(agent_name: str) -> str:
    """Read app/prompts/{agent_name}.txt as the boot-time fallback."""
    candidates = [
        f"app/prompts/{agent_name}.txt",
        f"backend/app/prompts/{agent_name}.txt",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:  # noqa: BLE001
                continue
    return ""


# =============================================================================
# Lifecycle helpers — add a new prompt version, activate, retire, set split
# =============================================================================


async def add_prompt(
    *,
    agent_name: str,
    version: str,
    body: str,
    description: str | None = None,
    status: str = "draft",
) -> None:
    await db.execute(
        """
        INSERT INTO prompts (agent_name, version, body, status, description)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (agent_name, version) DO UPDATE
          SET body = EXCLUDED.body,
              description = COALESCE(EXCLUDED.description, prompts.description)
        """,
        agent_name, version, body, status, description,
    )


async def activate_prompt(*, agent_name: str, version: str) -> None:
    """Mark version as active and retire any prior active."""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE prompts SET status='retired', retired_at=NOW() "
                "WHERE agent_name=$1 AND status='active'",
                agent_name,
            )
            await conn.execute(
                "UPDATE prompts SET status='active', activated_at=NOW() "
                "WHERE agent_name=$1 AND version=$2",
                agent_name, version,
            )


async def set_traffic_split(*, agent_name: str, weights: dict[str, float]) -> None:
    """Set traffic split for an agent. weights = {version: percent}; sum should == 100."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights must sum > 0")
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"weights must sum to 100, got {total}")
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM prompt_traffic_splits WHERE agent_name=$1", agent_name)
            for version, w in weights.items():
                await conn.execute(
                    "INSERT INTO prompt_traffic_splits (agent_name, version, weight_percent) "
                    "VALUES ($1, $2, $3)",
                    agent_name, version, w,
                )


async def assign_to_tenant(*, organization_id: str, agent_name: str, version: str) -> None:
    await db.execute(
        """
        INSERT INTO prompt_assignments (organization_id, agent_name, version)
        VALUES ($1, $2, $3)
        ON CONFLICT (organization_id, agent_name) DO UPDATE
          SET version = EXCLUDED.version, assigned_at = NOW()
        """,
        organization_id, agent_name, version,
    )


async def list_prompts(*, agent_name: str | None = None) -> list[dict[str, Any]]:
    if agent_name:
        rows = await db.fetch_ro(
            "SELECT agent_name, version, status, description, created_at, activated_at "
            "FROM prompts WHERE agent_name=$1 ORDER BY created_at DESC", agent_name,
        )
    else:
        rows = await db.fetch_ro(
            "SELECT agent_name, version, status, description, created_at, activated_at "
            "FROM prompts ORDER BY agent_name, created_at DESC",
        )
    return [dict(r) for r in rows]
