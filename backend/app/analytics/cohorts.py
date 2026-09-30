"""Cross-case cohort analytics — computed from the caller's own cases, never from fixtures.

`compute_cohorts` is a pure function over plain rows so every number on the Cohorts page can be unit-tested;
`fetch_cohort_rows` is the only DB access. Insights are derived from the data and are only emitted when there is
enough evidence (minimum sample sizes below) — with no data the page shows an honest empty state instead.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from app.db import db

#: minimum decided cases behind any comparative statement
MIN_DECIDED_PER_GROUP = 3
#: time-to-decision histogram buckets: (label, upper bound in seconds; None = open-ended)
TIME_BUCKETS: tuple[tuple[str, float | None], ...] = (
    ("< 1m", 60),
    ("1-3m", 180),
    ("3-5m", 300),
    ("5-10m", 600),
    ("10-30m", 1800),
    ("> 30m", None),
)
TOP_TREATMENTS = 8


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None


def _quantile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


def compute_cohorts(rows: list[dict[str, Any]], *, days: int) -> dict[str, Any]:
    """rows: one per case — payer_id, treatment, status, verdict (APPROVE/DENY/REFER/None), dur_s (seconds or None)."""
    total = len(rows)
    decided = [r for r in rows if r.get("verdict")]
    verdicts = Counter(r["verdict"] for r in decided)

    # ---- approval rate by payer -------------------------------------------------------------
    by_payer: dict[str, Counter[str]] = defaultdict(Counter)
    for r in decided:
        by_payer[r["payer_id"] or "unknown"][r["verdict"]] += 1
    approval_by_payer = sorted(
        (
            {
                "payer": p,
                "decided": sum(c.values()),
                "approve": c["APPROVE"],
                "deny": c["DENY"],
                "refer": c["REFER"],
                "rate": _pct(c["APPROVE"], sum(c.values())),
            }
            for p, c in by_payer.items()
        ),
        key=lambda x: (-x["decided"], x["payer"]),
    )

    # ---- time-to-decision -------------------------------------------------------------------
    durs = sorted(
        float(r["dur_s"]) for r in decided if r.get("dur_s") is not None and r["dur_s"] >= 0
    )
    buckets = [{"bucket": label, "count": 0} for label, _ in TIME_BUCKETS]
    for d in durs:
        for i, (_, upper) in enumerate(TIME_BUCKETS):
            if upper is None or d < upper:
                buckets[i]["count"] += 1
                break
    median_s, p90_s = _quantile(durs, 0.5), _quantile(durs, 0.9)

    # ---- verdict mix by treatment -----------------------------------------------------------
    by_tx: dict[str, Counter[str]] = defaultdict(Counter)
    for r in decided:
        by_tx[(r["treatment"] or "unspecified").strip().lower()][r["verdict"]] += 1
    verdict_by_treatment = [
        {"treatment": t, "approve": c["APPROVE"], "deny": c["DENY"], "refer": c["REFER"]}
        for t, c in sorted(by_tx.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[
            :TOP_TREATMENTS
        ]
    ]

    # ---- status funnel (incl. appeals) ------------------------------------------------------
    status_counts = Counter(r["status"] for r in rows)
    appealed, overturned = status_counts["appealed"], status_counts["overturned"]

    # ---- data-derived insights (only with enough evidence) ----------------------------------
    insights: list[dict[str, Any]] = []
    eligible = [p for p in approval_by_payer if p["decided"] >= MIN_DECIDED_PER_GROUP]
    if len(eligible) >= 2:
        hi = max(eligible, key=lambda p: (p["rate"] or 0, p["decided"]))
        lo = min(eligible, key=lambda p: (p["rate"] or 0, -p["decided"]))
        if hi["payer"] != lo["payer"] and (hi["rate"] or 0) != (lo["rate"] or 0):
            gap = round((hi["rate"] or 0) - (lo["rate"] or 0), 1)
            insights.append(
                {
                    "id": "payer-approval-gap",
                    "accent": "blue",
                    "metric": f"{gap:g} pp",
                    "metric_label": "approval-rate gap between payers",
                    "title": f"{hi['payer']} approves {hi['rate']:g}% vs {lo['payer']} {lo['rate']:g}%",
                    "detail": (
                        f"Among decided cases: {hi['payer']} {hi['approve']}/{hi['decided']} approved, "
                        f"{lo['payer']} {lo['approve']}/{lo['decided']} approved."
                    ),
                    "link": {"label": "View cases", "to": "/cases"},
                }
            )
    tx_eligible = [
        t
        for t in verdict_by_treatment
        if t["approve"] + t["deny"] + t["refer"] >= MIN_DECIDED_PER_GROUP
    ]
    if tx_eligible:
        worst = max(
            tx_eligible,
            key=lambda t: (t["deny"] + t["refer"]) / (t["approve"] + t["deny"] + t["refer"]),
        )
        n = worst["approve"] + worst["deny"] + worst["refer"]
        not_approved = worst["deny"] + worst["refer"]
        if not_approved:
            insights.append(
                {
                    "id": "treatment-friction",
                    "accent": "amber",
                    "metric": f"{_pct(not_approved, n):g}%",
                    "metric_label": "not approved outright",
                    "title": f"{worst['treatment']}: {not_approved} of {n} decided cases were denied or referred",
                    "detail": f"{worst['deny']} denied, {worst['refer']} referred to human review, {worst['approve']} approved.",
                    "link": {"label": "View cases", "to": "/cases"},
                }
            )
    if len(decided) >= MIN_DECIDED_PER_GROUP:
        refer_pct = _pct(verdicts["REFER"], len(decided))
        insights.append(
            {
                "id": "human-review-load",
                "accent": "violet",
                "metric": f"{refer_pct:g}%",
                "metric_label": "of decided cases needed human review",
                "title": f"{verdicts['REFER']} of {len(decided)} decided cases were referred to a reviewer",
                "detail": "Referral means the evidence was incomplete or ambiguous; these route to the reviewer queue.",
                "link": {"label": "Open reviewer queue", "to": "/reviewer"},
            }
        )
    if len(durs) >= MIN_DECIDED_PER_GROUP:
        under5 = sum(1 for d in durs if d < 300)
        insights.append(
            {
                "id": "decision-speed",
                "accent": "green",
                "metric": _fmt_duration(median_s),
                "metric_label": "median time to decision",
                "title": f"{_pct(under5, len(durs)):g}% of decisions were made in under 5 minutes",
                "detail": f"p90 {_fmt_duration(p90_s)} across {len(durs)} timed decisions.",
                "link": {"label": "View cases", "to": "/cases"},
            }
        )
    if appealed + overturned:
        insights.append(
            {
                "id": "appeal-outcomes",
                "accent": "green",
                "metric": f"{_pct(overturned, appealed + overturned):g}%",
                "metric_label": "of appealed cases overturned",
                "title": f"{overturned} of {appealed + overturned} appealed cases were overturned",
                "detail": "Counts cases currently in status 'appealed' or 'overturned'.",
                "link": {"label": "View cases", "to": "/cases"},
            }
        )

    return {
        "window_days": days,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_cases": total,
        "decided_cases": len(decided),
        "pending_cases": total - len(decided),
        "verdicts": {
            "APPROVE": verdicts["APPROVE"],
            "DENY": verdicts["DENY"],
            "REFER": verdicts["REFER"],
        },
        "approval_by_payer": approval_by_payer,
        "time_to_decision": {
            "buckets": buckets,
            "timed_cases": len(durs),
            "median_seconds": None if median_s is None else round(median_s, 1),
            "p90_seconds": None if p90_s is None else round(p90_s, 1),
        },
        "verdict_by_treatment": verdict_by_treatment,
        "status_counts": dict(status_counts),
        "insights": insights,
        "min_group_size": MIN_DECIDED_PER_GROUP,
    }


async def fetch_cohort_rows(organization_id: str, days: int) -> list[dict[str, Any]]:
    """The caller's cases in the window with their latest decision (one row per case)."""
    rows = await db.fetch(
        """SELECT c.id, c.payer_id, c.requested_treatment_name AS treatment, c.status,
                  d.verdict,
                  EXTRACT(EPOCH FROM (d.created_at - c.created_at))::FLOAT AS dur_s
           FROM cases c
           LEFT JOIN LATERAL (
               SELECT verdict, created_at FROM decisions WHERE case_id = c.id
               ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           WHERE c.organization_id = $1
             AND c.created_at >= NOW() - ($2::INT * INTERVAL '1 day')""",
        organization_id,
        days,
    )
    return [dict(r) for r in rows]
