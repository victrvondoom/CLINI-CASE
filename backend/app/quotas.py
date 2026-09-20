"""Per-organization daily case quota enforcement (SCALE-8).

Why this matters at production scale:
  • Cost control — a single org submitting 100K cases/day at $0.45/case = $45K/day.
    Without a quota, a misconfigured client can drain a payer contract overnight.
  • Per-tenant fairness — one org's burst can't starve another's queue.
  • Compliance — payer contracts cap concurrent volume; we enforce contractually.

Design (single source of truth: this file):
  • One row per organization in `org_quotas`.
  • Daily counter + reset timestamp. Atomically incremented on each case submit.
  • Race-free via a single conditional UPDATE — the WHERE clause IS the gate;
    when the limit is reached the row is unmatched and `RETURNING` returns
    nothing → the caller sees QuotaExceeded. Two concurrent submitters block
    on the row lock; the one that arrives second re-evaluates the WHERE and
    correctly fails if the first one consumed the last slot.
  • Day boundary uses CURRENT_DATE (UTC by Postgres convention) so the reset
    is operator-meaningful and matches our log/metrics grain.

Wired in at:
  • `app/api/cases.py:run_full`        — synchronous run path
  • `app/api/jobs.py:enqueue_async`    — async run path
The async path checks BEFORE enqueueing so a denial returns 429 immediately
rather than after the worker picks the job up.

Why a separate file (not in `app/db.py`):
  • Quota policy belongs to the API tier's domain logic, not the DB connection layer.
  • Keeps `db.py` to ~60 LOC pool ops only.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()


# =============================================================================
# Schema
# =============================================================================


_SCHEMA = """
CREATE TABLE IF NOT EXISTS org_quotas (
    organization_id        TEXT        PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    daily_case_limit       INTEGER     NOT NULL DEFAULT 1000  CHECK (daily_case_limit >= 0),
    monthly_case_limit     INTEGER     NOT NULL DEFAULT 30000 CHECK (monthly_case_limit >= 0),
    current_day            DATE        NOT NULL DEFAULT CURRENT_DATE,
    current_day_count      INTEGER     NOT NULL DEFAULT 0     CHECK (current_day_count >= 0),
    current_month          DATE        NOT NULL DEFAULT date_trunc('month', CURRENT_DATE)::date,
    current_month_count    INTEGER     NOT NULL DEFAULT 0     CHECK (current_month_count >= 0),
    -- Per-tenant data residency — drives RDS cluster + S3 bucket region selection.
    -- Defaults to ap-south-1; flip per customer's regulatory requirement
    -- (HDS for FR healthcare, DPDP for IN, HIPAA region preference for US payers).
    data_region            TEXT        NOT NULL DEFAULT 'ap-south-1',
    -- Pricing / SLA tier — Bronze / Silver / Gold drives WAF rate-limit + Bedrock
    -- model allowlist + on-call escalation tier.
    tier                   TEXT        NOT NULL DEFAULT 'silver' CHECK (tier IN ('bronze','silver','gold')),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_org_quotas_day    ON org_quotas (current_day);
CREATE INDEX IF NOT EXISTS idx_org_quotas_region ON org_quotas (data_region);
CREATE INDEX IF NOT EXISTS idx_org_quotas_tier   ON org_quotas (tier);

-- Idempotent ALTER (existing DBs predating data_region/tier columns)
ALTER TABLE org_quotas ADD COLUMN IF NOT EXISTS data_region TEXT NOT NULL DEFAULT 'ap-south-1';
ALTER TABLE org_quotas ADD COLUMN IF NOT EXISTS tier        TEXT NOT NULL DEFAULT 'silver';
"""


_DEFAULT_DAILY_LIMIT = 1000
_DEFAULT_MONTHLY_LIMIT = 30000


async def ensure_schema() -> None:
    """Idempotent schema bootstrap. Called from app lifespan + worker boot."""
    await db.execute(_SCHEMA)


# =============================================================================
# Public types
# =============================================================================


class QuotaExceeded(Exception):
    """Raised when an org has consumed its daily / monthly case quota.

    `kind` is the dimension that tripped — 'daily' or 'monthly'. Carries
    enough context that the API layer can return a proper 429 response with
    Retry-After hints for the client.
    """

    def __init__(
        self,
        *,
        organization_id: str,
        kind: str,
        limit: int,
        used: int,
        resets_at_iso: str,
    ) -> None:
        self.organization_id = organization_id
        self.kind = kind
        self.limit = limit
        self.used = used
        self.resets_at_iso = resets_at_iso
        super().__init__(
            f"QuotaExceeded[{kind}] org={organization_id} used={used}/{limit} "
            f"resets_at={resets_at_iso}"
        )


# =============================================================================
# Public API
# =============================================================================


async def get_quota(organization_id: str) -> dict[str, Any]:
    """Read current quota state for an org. Used by /metrics + admin UI."""
    row = await db.fetchrow(
        "SELECT * FROM org_quotas WHERE organization_id = $1", organization_id
    )
    if row is None:
        return {
            "organization_id": organization_id,
            "daily_case_limit": _DEFAULT_DAILY_LIMIT,
            "monthly_case_limit": _DEFAULT_MONTHLY_LIMIT,
            "current_day_count": 0,
            "current_month_count": 0,
            "exists": False,
        }
    return {**dict(row), "exists": True}


async def _ensure_quota_row(organization_id: str) -> None:
    """Create the org_quotas row on first encounter. Idempotent."""
    await db.execute(
        """INSERT INTO org_quotas (organization_id, daily_case_limit, monthly_case_limit)
           VALUES ($1, $2, $3)
           ON CONFLICT (organization_id) DO NOTHING""",
        organization_id, _DEFAULT_DAILY_LIMIT, _DEFAULT_MONTHLY_LIMIT,
    )


async def consume_case_quota(organization_id: str) -> dict[str, int]:
    """Atomically consume one slot of the org's daily + monthly quota.

    Returns the post-increment counters on success. Raises `QuotaExceeded`
    when either dimension is at its cap. Rolls over the counters when the
    day / month boundary has passed since the last increment.

    The atomicity guarantee comes from a single UPDATE statement whose WHERE
    clause IS the eligibility check — when concurrent callers race, Postgres
    serializes them via the row lock and the second caller re-evaluates the
    WHERE clause correctly. No SELECT-then-UPDATE race window.
    """
    await _ensure_quota_row(organization_id)

    row = await db.fetchrow(
        """
        UPDATE org_quotas
        SET
            current_day = CASE WHEN current_day < CURRENT_DATE
                               THEN CURRENT_DATE
                               ELSE current_day END,
            current_day_count = CASE WHEN current_day < CURRENT_DATE
                                     THEN 1
                                     ELSE current_day_count + 1 END,
            current_month = CASE WHEN current_month < date_trunc('month', CURRENT_DATE)::date
                                 THEN date_trunc('month', CURRENT_DATE)::date
                                 ELSE current_month END,
            current_month_count = CASE WHEN current_month < date_trunc('month', CURRENT_DATE)::date
                                       THEN 1
                                       ELSE current_month_count + 1 END,
            updated_at = NOW()
        WHERE organization_id = $1
          AND (
              current_day < CURRENT_DATE
              OR current_day_count < daily_case_limit
          )
          AND (
              current_month < date_trunc('month', CURRENT_DATE)::date
              OR current_month_count < monthly_case_limit
          )
        RETURNING current_day_count, current_month_count,
                  daily_case_limit, monthly_case_limit
        """,
        organization_id,
    )

    if row is None:
        # Either daily or monthly cap was hit. Re-read to determine which.
        state = await db.fetchrow(
            """SELECT current_day_count, daily_case_limit,
                      current_month_count, monthly_case_limit,
                      (CURRENT_DATE + INTERVAL '1 day')::timestamptz AS day_resets_at,
                      (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::timestamptz AS month_resets_at
               FROM org_quotas WHERE organization_id = $1""",
            organization_id,
        )
        if state is None:
            # Pathological — row vanished after _ensure_quota_row. Fail safe.
            raise QuotaExceeded(
                organization_id=organization_id,
                kind="unknown",
                limit=0,
                used=0,
                resets_at_iso="",
            )
        # Determine which dimension was the binding constraint.
        if state["current_day_count"] >= state["daily_case_limit"]:
            raise QuotaExceeded(
                organization_id=organization_id,
                kind="daily",
                limit=state["daily_case_limit"],
                used=state["current_day_count"],
                resets_at_iso=state["day_resets_at"].isoformat(),
            )
        raise QuotaExceeded(
            organization_id=organization_id,
            kind="monthly",
            limit=state["monthly_case_limit"],
            used=state["current_month_count"],
            resets_at_iso=state["month_resets_at"].isoformat(),
        )

    return {
        "current_day_count": row["current_day_count"],
        "current_month_count": row["current_month_count"],
        "daily_case_limit": row["daily_case_limit"],
        "monthly_case_limit": row["monthly_case_limit"],
    }


async def set_org_limits(
    organization_id: str,
    *,
    daily_case_limit: int | None = None,
    monthly_case_limit: int | None = None,
) -> dict[str, Any]:
    """Operator-facing knob: update an org's quota caps. Idempotent."""
    await _ensure_quota_row(organization_id)
    sets: list[str] = []
    args: list[Any] = []
    if daily_case_limit is not None:
        args.append(daily_case_limit)
        sets.append(f"daily_case_limit = ${len(args)}")
    if monthly_case_limit is not None:
        args.append(monthly_case_limit)
        sets.append(f"monthly_case_limit = ${len(args)}")
    if not sets:
        return await get_quota(organization_id)
    args.append(organization_id)
    await db.execute(
        f"UPDATE org_quotas SET {', '.join(sets)}, updated_at = NOW() "
        f"WHERE organization_id = ${len(args)}",
        *args,
    )
    return await get_quota(organization_id)


# =============================================================================
# FastAPI helper — drop-in dependency for case-creating endpoints
# =============================================================================


def quota_exceeded_to_http(exc: QuotaExceeded) -> dict[str, Any]:
    """Render a QuotaExceeded as a 429 response body. Caller raises HTTPException."""
    return {
        "error": "quota_exceeded",
        "kind": exc.kind,
        "organization_id": exc.organization_id,
        "limit": exc.limit,
        "used": exc.used,
        "resets_at": exc.resets_at_iso,
        "message": (
            f"Daily" if exc.kind == "daily" else f"Monthly"
        ) + f" case quota of {exc.limit} reached for organization "
        + f"{exc.organization_id}. Resets at {exc.resets_at_iso} UTC.",
    }
