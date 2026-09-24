"""Deterministic response cache for LLM sub-agents (SCALE-9).

Why this is a *real* cost lever:

  • Retry storms — a network blip during the demo, a worker timeout, an
    operator re-running a case for the audit panel — every retry of the
    same case re-runs every sub-agent. Without a cache, that's 21 LLM calls
    × $0.005 avg = $0.10 wasted per replay.

  • Sibling-agent symmetry — two sub-agents under the same parent often
    receive byte-identical inputs (e.g. evidence_matcher × N criteria all
    see the same ClinicalSnapshot+Excerpt context). Within-case dedup is
    real money over a 10K-case/day workload.

  • Idempotency-Key reruns — the API tier already dedups *case-level*
    submissions. The cache dedups at the *sub-agent* level, which catches
    the case where a duplicate submission slipped through (e.g. browser
    re-fired a POST after a 504 timeout).

What this is NOT (and why it isn't shipped yet):

  • A *semantic* cache (similar-but-not-identical inputs) — that needs an
    embedding model and a similarity threshold. Real value at scale (~12%
    case dedup) but it's a much bigger surface area: cache poisoning, false
    positives, embedding model versioning. Deferred to post-pilot once the
    Bedrock Titan Embeddings call is part of the regular cost basis.

Key design properties:

  • Exact-match only — the cache key is sha256(qualified_name + input JSON).
    Two different agents with the same input produce different keys.
  • Schema-version pinned — if an agent's output schema changes, all old
    cache entries are invalidated immediately (key includes schema hash).
  • Per-row TTL with lazy eviction — `expires_at` column; lookups filter
    `expires_at > NOW()`. A daily janitor query reaps expired rows.
  • Postgres-backed not Redis — same reason as the job queue: one fewer
    dependency, transactional consistency with case writes if we ever need it.
  • PHI-aware — we reuse the input that's already passed PHI guardrails.
    The cache stores no PHI that the agent didn't already legitimately receive.
  • Per-org scoped — cache key includes organization_id, so org A's cached
    output is *not* visible to org B even with identical input. (Two payers
    might submit identical synthetic patient data for testing.)

Lifecycle integration (`framework/agent.py`):

  After validate-input, before guardrails:
      hit = await response_cache.lookup(...)
      if hit:
          emit cache_hit event; return cached output as AgentResult
      ... else continue lifecycle, store on success at end ...
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()


# =============================================================================
# Schema
# =============================================================================


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_response_cache (
    cache_key       TEXT        PRIMARY KEY,
    agent_name      TEXT        NOT NULL,
    organization_id TEXT        NOT NULL,
    output_json     JSONB       NOT NULL,
    model_id        TEXT,
    input_tokens    INTEGER     NOT NULL DEFAULT 0,
    output_tokens   INTEGER     NOT NULL DEFAULT 0,
    schema_version  TEXT        NOT NULL,
    hits            INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arc_agent       ON agent_response_cache (agent_name);
CREATE INDEX IF NOT EXISTS idx_arc_expires     ON agent_response_cache (expires_at);
CREATE INDEX IF NOT EXISTS idx_arc_org         ON agent_response_cache (organization_id);
"""


# Default per-row TTL — short by design. A cached entry's value is bounded:
# • Within the same case-execution tree (sibling sub-agents): seconds.
# • Idempotent retry of a case: minutes.
# • A clinical snapshot the same morning: hours.
# Bigger TTL → bigger blast radius if a policy update lands. 1 hour is the
# sweet spot for the 90-second-DAG / hour-scale-policy-update profile.
_DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour


async def ensure_schema() -> None:
    """Idempotent schema bootstrap. Called from app lifespan + worker boot."""
    await db.execute(_SCHEMA)


# =============================================================================
# Public types
# =============================================================================


@dataclass(frozen=True)
class CacheKey:
    """A composite key for one cached agent output.

    The string form is `sha256(agent_name | org_id | schema_version | input_json)`.
    All four components are needed for correctness:
      • agent_name      — distinct agents, same input → distinct outputs
      • organization_id — tenant isolation
      • schema_version  — schema drift invalidates cache
      • input_json      — the actual content
    """

    digest: str

    @staticmethod
    def derive(
        *,
        agent_qualified_name: str,
        organization_id: str,
        schema_version: str,
        input_json: str,
    ) -> CacheKey:
        material = (
            f"{agent_qualified_name}\x1f"
            f"{organization_id}\x1f"
            f"{schema_version}\x1f"
            f"{input_json}"
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return CacheKey(digest=digest)


@dataclass(frozen=True)
class CacheHit:
    """A cache hit. The framework reconstructs `output_schema.model_validate`."""

    output_json: dict[str, Any]
    model_id: str | None
    input_tokens: int
    output_tokens: int
    age_seconds: float
    hits_pre: int
    """Hit count BEFORE this lookup. Used to bound bursty staleness."""


# =============================================================================
# Lookup + store
# =============================================================================


async def lookup(key: CacheKey) -> CacheHit | None:
    """Return a cache hit if one exists and is not expired.

    Atomically increments `hits` + bumps `last_used_at` so the cache stays
    warm against an LRU-ish eviction strategy. Misses return None.
    """
    row = await db.fetchrow(
        """UPDATE agent_response_cache
           SET hits = hits + 1, last_used_at = NOW()
           WHERE cache_key = $1
             AND expires_at > NOW()
           RETURNING output_json, model_id, input_tokens, output_tokens,
                     EXTRACT(EPOCH FROM (NOW() - created_at))::FLOAT AS age_s,
                     hits""",
        key.digest,
    )
    if row is None:
        return None
    raw = row["output_json"]
    output = json.loads(raw) if isinstance(raw, str) else raw
    return CacheHit(
        output_json=output,
        model_id=row["model_id"],
        input_tokens=row["input_tokens"] or 0,
        output_tokens=row["output_tokens"] or 0,
        age_seconds=float(row["age_s"]),
        hits_pre=int(row["hits"]) - 1,
    )


async def store(
    key: CacheKey,
    *,
    agent_qualified_name: str,
    organization_id: str,
    output_json: dict[str, Any],
    schema_version: str,
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    """Store a successful agent output in the cache.

    UPSERT semantics — if the key already exists (e.g. concurrent miss-then-store
    by sibling agents), we keep the older row's `created_at` and `hits` to
    preserve cache warmth.
    """
    await db.execute(
        """
        INSERT INTO agent_response_cache (
            cache_key, agent_name, organization_id, output_json,
            model_id, input_tokens, output_tokens, schema_version,
            expires_at
        )
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8,
                NOW() + ($9 || ' seconds')::interval)
        ON CONFLICT (cache_key) DO UPDATE
        SET expires_at    = EXCLUDED.expires_at,
            last_used_at  = NOW()
        """,
        key.digest,
        agent_qualified_name,
        organization_id,
        json.dumps(output_json),
        model_id,
        input_tokens,
        output_tokens,
        schema_version,
        str(ttl_seconds),
    )


async def reap_expired(*, batch_size: int = 1000) -> int:
    """Operator helper / janitor: delete expired rows. Returns count.

    Run from a cron Lambda or the worker's janitor loop. Lazy eviction
    via the `expires_at > NOW()` filter on lookup is enough for correctness;
    this is purely a storage-bound housekeeping concern.
    """
    rows = await db.fetch(
        """DELETE FROM agent_response_cache
           WHERE cache_key IN (
               SELECT cache_key FROM agent_response_cache
               WHERE expires_at <= NOW()
               LIMIT $1
           )
           RETURNING cache_key""",
        batch_size,
    )
    return len(rows)


async def cache_stats() -> dict[str, Any]:
    """Cache utilization stats for /metrics + admin UI."""
    row = await db.fetchrow(
        """SELECT
              COUNT(*)::INT                      AS rows_total,
              COUNT(*) FILTER (WHERE expires_at > NOW())::INT AS rows_live,
              COALESCE(SUM(hits), 0)::INT        AS total_hits,
              COALESCE(MAX(hits), 0)::INT        AS top_hit_count
           FROM agent_response_cache"""
    )
    return dict(row) if row else {}


# =============================================================================
# Convenience: schema_version derivation
# =============================================================================


def schema_version_for(output_schema: type) -> str:
    """Stable hash of an agent's output schema. Drift invalidates cache.

    Pydantic's model_json_schema is deterministic for a given Python object
    graph, so hashing it gives a 16-hex-char fingerprint we can embed in the
    cache key.
    """
    try:
        # `output_schema` is a Pydantic v2 model class
        schema_json = output_schema.model_json_schema()
        digest = hashlib.sha256(
            json.dumps(schema_json, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest[:16]
    except Exception:  # noqa: BLE001
        # Fallback — class qualname. Won't catch field changes but won't crash.
        return getattr(output_schema, "__qualname__", "unknown")
