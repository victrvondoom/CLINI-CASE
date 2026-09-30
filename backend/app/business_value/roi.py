"""Per-case + per-org ROI computation.

Two industry baselines anchor the math:

  • CAQH 2024 Index: Manual PA cost = ~$11.50 per claim for the payer side
    + $14.24 for the provider side; AMA's loaded cost (clinician + staff
    + appeals) puts a single oncology PA at $1,400-$1,800 across both
    sides. We use **$1,500 per PA** as the conservative manual baseline
    (matches AMA Council on Medical Service 2024 testimony).

  • ClinCase per-case Bedrock cost (from ops/SCALING.md):
      Clean APPROVE: ~$0.25
      DENY+appeal:   ~$0.45

The math is intentionally conservative — anyone asking "where do these
numbers come from?" can point to AMA / CAQH / KFF directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC

from app.db import db

# =============================================================================
# Constants — sourced from public industry data
# =============================================================================


# AMA Council on Medical Service: oncology PA fully-loaded cost $1,400-$1,800
# Conservative midpoint:
MANUAL_PA_COST_USD = 1_500.0

# Time burden — AMA 2024 + 2025 surveys: 39-43 PAs/week consume 12-13 hours.
# Per PA: 12 hours / 41 PAs ≈ 17.5 minutes. We round to 18 min.
MANUAL_PA_MINUTES = 18.0

# Provider hourly cost (oncologist fully loaded, US): ~$320/hour
# (MGMA 2024 oncologist comp $441K / 2080h plus 50% loading).
PROVIDER_HOURLY_LOADED_USD = 320.0

# Bedrock per-case ranges
CLINCASE_COST_CLEAN_APPROVE = 0.25
CLINCASE_COST_DENY_PATH = 0.45
CLINCASE_COST_REFER_PATH = 0.32  # halfway — refer typically requires fewer agents than DENY

# ClinCase p99 case latency (from SCALING.md): 90s SLA. We use 60s as
# the observed p50 for the cost-savings comparison.
CLINCASE_P50_SECONDS = 60.0


# =============================================================================
# Per-case ROI
# =============================================================================


def token_pricing() -> dict[str, dict[str, float]]:
    from app.agents.framework.models import HAIKU_LITE, SONNET_REASONING

    return {
        "sonnet": {
            "in": SONNET_REASONING.cost_per_million_input_tokens,
            "out": SONNET_REASONING.cost_per_million_output_tokens,
        },
        "haiku": {
            "in": HAIKU_LITE.cost_per_million_input_tokens,
            "out": HAIKU_LITE.cost_per_million_output_tokens,
        },
    }


@dataclass
class CaseROI:
    case_id: str
    organization_id: str
    verdict: str | None
    manual_cost_usd: float
    clincase_cost_usd: float
    savings_usd: float
    minutes_saved: float
    decision_seconds: float | None
    speedup_factor: float | None
    annual_extrapolation_usd: float | None  # if this org runs N similar cases / year
    citations: list[str]
    #: the manual-PA baseline (minutes) the savings / speed-up numbers are measured against
    manual_minutes: float = MANUAL_PA_MINUTES
    #: USD per 1M tokens by model family — the same table the agent framework bills against
    token_pricing_usd_per_m: dict[str, dict[str, float]] = field(
        default_factory=lambda: token_pricing()
    )


def _verdict_to_clincase_cost(verdict: str | None) -> float:
    if verdict == "APPROVE":
        return CLINCASE_COST_CLEAN_APPROVE
    if verdict == "DENY":
        return CLINCASE_COST_DENY_PATH
    if verdict == "REFER":
        return CLINCASE_COST_REFER_PATH
    return CLINCASE_COST_CLEAN_APPROVE  # default optimistic


async def case_roi(case_id: str, organization_id: str | None = None) -> CaseROI:
    """Compute per-case ROI vs manual baseline."""
    case = await db.fetchrow(
        """SELECT id, organization_id, created_at FROM cases WHERE id = $1""",
        case_id,
    )
    if case is None:
        raise ValueError(f"Case {case_id} not found")
    if organization_id is not None and case["organization_id"] != organization_id:
        raise PermissionError("Cross-org access forbidden.")

    decision = await db.fetchrow(
        """SELECT verdict, created_at FROM decisions WHERE case_id = $1
           ORDER BY id DESC LIMIT 1""",
        case_id,
    )

    decision_seconds: float | None = None
    if decision and case["created_at"] and decision["created_at"]:
        decision_seconds = (decision["created_at"] - case["created_at"]).total_seconds()

    verdict = decision["verdict"] if decision else None
    clincase_cost = _verdict_to_clincase_cost(verdict)
    savings = MANUAL_PA_COST_USD - clincase_cost

    minutes_saved = MANUAL_PA_MINUTES
    if decision_seconds is not None:
        # Adjust by what we actually used (some seconds shaving)
        minutes_saved = max(0.0, MANUAL_PA_MINUTES - decision_seconds / 60.0)

    speedup = None
    if decision_seconds and decision_seconds > 0:
        # Compare against the AMA 18-minute median per PA in seconds
        speedup = (MANUAL_PA_MINUTES * 60.0) / decision_seconds

    # Annual extrapolation — count this org's last-30-days volume × 12.
    last_30d_count = (
        await db.fetchval(
            """SELECT COUNT(*)::INT FROM cases
           WHERE organization_id = $1 AND created_at >= NOW() - INTERVAL '30 days'""",
            case["organization_id"],
        )
        or 0
    )
    annual = float(last_30d_count) * 12.0 * savings

    return CaseROI(
        case_id=case_id,
        organization_id=case["organization_id"],
        verdict=verdict,
        manual_cost_usd=MANUAL_PA_COST_USD,
        clincase_cost_usd=clincase_cost,
        savings_usd=round(savings, 2),
        minutes_saved=round(minutes_saved, 1),
        decision_seconds=round(decision_seconds, 2) if decision_seconds is not None else None,
        speedup_factor=round(speedup, 1) if speedup else None,
        annual_extrapolation_usd=round(annual, 2),
        citations=[
            "AMA 2025 Prior Authorization Physician Survey",
            "CAQH 2024 Index — PA admin cost",
            "MGMA 2024 oncologist compensation",
            "ClinCase ops/SCALING.md per-case cost model",
        ],
    )


# =============================================================================
# Org rollup
# =============================================================================


@dataclass
class OrgValueRollup:
    organization_id: str
    asof_iso: str
    cases_total: int
    cases_decided: int
    verdict_breakdown: dict[str, int]
    direct_savings_mtd_usd: float
    direct_savings_annual_projection_usd: float
    avg_decision_seconds: float | None
    avg_speedup_factor: float | None
    citations: list[str]
    #: cases created per UTC day for the last 7 days, oldest first (last item = today)
    daily_cases_7d: list[int] = field(default_factory=lambda: [0] * 7)
    #: change in mean time-to-decision vs the previous calendar month, in % (negative = faster); None if either is unknown
    avg_decision_change_pct: float | None = None
    #: the baselines the savings / speed-up maths are measured against — served so the UI never hard-codes them
    assumptions: dict[str, float] = field(
        default_factory=lambda: {
            "manual_pa_cost_usd": MANUAL_PA_COST_USD,
            "manual_pa_minutes": MANUAL_PA_MINUTES,
        }
    )


async def org_value_rollup(organization_id: str) -> OrgValueRollup:
    """Org-level direct-savings rollup. Star Ratings + abrasion are in
    sibling modules `star_ratings.py` and `provider_abrasion.py`."""
    from datetime import datetime, timedelta

    # Cases this month
    rows = await db.fetch(
        """SELECT c.id, d.verdict,
                  EXTRACT(EPOCH FROM (d.created_at - c.created_at)) AS dur_s
           FROM cases c
           LEFT JOIN LATERAL (
               SELECT verdict, created_at FROM decisions WHERE case_id = c.id
               ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           WHERE c.organization_id = $1
             AND c.created_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')""",
        organization_id,
    )
    n_cases = len(rows)
    n_decided = sum(1 for r in rows if r["verdict"])
    verdicts: dict[str, int] = {"APPROVE": 0, "DENY": 0, "REFER": 0, "PENDING": 0}
    for r in rows:
        v = r["verdict"] or "PENDING"
        verdicts[v] = verdicts.get(v, 0) + 1

    durations = [float(r["dur_s"]) for r in rows if r["dur_s"]]
    avg_dur = (sum(durations) / len(durations)) if durations else None
    avg_speedup = ((MANUAL_PA_MINUTES * 60.0) / avg_dur) if avg_dur else None

    # MTD savings
    direct_savings_mtd = (
        verdicts["APPROVE"] * (MANUAL_PA_COST_USD - CLINCASE_COST_CLEAN_APPROVE)
        + verdicts["DENY"] * (MANUAL_PA_COST_USD - CLINCASE_COST_DENY_PATH)
        + verdicts["REFER"] * (MANUAL_PA_COST_USD - CLINCASE_COST_REFER_PATH)
    )

    # Last-30d volume × 12 → projected annual
    last_30d_row = await db.fetchrow(
        """SELECT COUNT(*)::INT AS n,
                  AVG(EXTRACT(EPOCH FROM (d.created_at - c.created_at)))::FLOAT AS avg_dur
           FROM cases c
           LEFT JOIN LATERAL (
               SELECT verdict, created_at FROM decisions WHERE case_id = c.id
               ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           WHERE c.organization_id = $1
             AND c.created_at >= NOW() - INTERVAL '30 days'""",
        organization_id,
    )
    n_30 = (last_30d_row["n"] if last_30d_row else 0) or 0

    # Use actual mix from MTD (or assume 70/20/10 if no MTD data)
    if n_cases > 0:
        approve_frac = verdicts["APPROVE"] / max(1, n_cases)
        deny_frac = verdicts["DENY"] / max(1, n_cases)
        refer_frac = verdicts["REFER"] / max(1, n_cases)
    else:
        approve_frac, deny_frac, refer_frac = 0.70, 0.20, 0.10
    blended_savings = (
        approve_frac * (MANUAL_PA_COST_USD - CLINCASE_COST_CLEAN_APPROVE)
        + deny_frac * (MANUAL_PA_COST_USD - CLINCASE_COST_DENY_PATH)
        + refer_frac * (MANUAL_PA_COST_USD - CLINCASE_COST_REFER_PATH)
    )
    annual_projection = n_30 * 12.0 * blended_savings

    # Real activity series + month-over-month speed change (both derived from this org's own cases)
    daily_rows = await db.fetch(
        """SELECT (c.created_at AT TIME ZONE 'UTC')::date AS d, COUNT(*)::INT AS n
           FROM cases c
           WHERE c.organization_id = $1
             AND c.created_at >= (date_trunc('day', NOW() AT TIME ZONE 'UTC') - INTERVAL '6 days')
           GROUP BY 1""",
        organization_id,
    )
    today = datetime.now(UTC).date()
    by_day = {r["d"]: r["n"] for r in daily_rows}
    daily = [int(by_day.get(today - timedelta(days=6 - i), 0)) for i in range(7)]

    prev_row = await db.fetchrow(
        """SELECT AVG(EXTRACT(EPOCH FROM (d.created_at - c.created_at)))::FLOAT AS avg_dur
           FROM cases c
           JOIN LATERAL (
               SELECT created_at FROM decisions WHERE case_id = c.id ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           WHERE c.organization_id = $1
             AND c.created_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC') - INTERVAL '1 month'
             AND c.created_at <  date_trunc('month', NOW() AT TIME ZONE 'UTC')""",
        organization_id,
    )
    prev_avg = prev_row["avg_dur"] if prev_row else None
    change_pct = round(100.0 * (avg_dur - prev_avg) / prev_avg, 1) if avg_dur and prev_avg else None

    return OrgValueRollup(
        organization_id=organization_id,
        asof_iso=datetime.now(UTC).isoformat(),
        cases_total=n_cases,
        cases_decided=n_decided,
        verdict_breakdown=verdicts,
        direct_savings_mtd_usd=round(direct_savings_mtd, 2),
        direct_savings_annual_projection_usd=round(annual_projection, 2),
        avg_decision_seconds=round(avg_dur, 2) if avg_dur else None,
        avg_speedup_factor=round(avg_speedup, 1) if avg_speedup else None,
        citations=[
            "AMA 2025 Prior Authorization Physician Survey",
            "CAQH 2024 Index — PA admin cost",
            "ClinCase ops/SCALING.md per-case cost model",
        ],
        daily_cases_7d=daily,
        avg_decision_change_pct=change_pct,
    )
