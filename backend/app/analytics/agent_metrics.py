"""Per-agent operational metrics from the caller's own `agent_runs` — invocations, success rate, latency
percentiles, token means, estimated cost and a health state. No fixtures: an agent that has not run in the
window simply has no entry (the UI shows it as idle)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db import db
from app.llm import pricing

#: a span with no finish time younger than this counts as "running"
RUNNING_WINDOW_MINUTES = 10
#: below this success rate (with >= MIN_RUNS_FOR_ERROR finished runs) an agent is flagged "error"
ERROR_SUCCESS_PCT = 90.0
MIN_RUNS_FOR_ERROR = 3


def price_for(model_id: str | None) -> tuple[float, float]:
    """(USD per 1M input tokens, USD per 1M output tokens) by model family (single source: app.llm.pricing)."""
    return pricing.price_per_mtok(model_id)


def summarize_agent(row: dict[str, Any], cost_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn one aggregated SQL row (+ its per-model token sums) into the public metrics record."""
    ok, errors, running = int(row["ok"] or 0), int(row["errors"] or 0), int(row["running"] or 0)
    finished = ok + errors
    success_pct = round(100.0 * ok / finished, 1) if finished else None
    cost = 0.0
    for c in cost_rows:
        pin, pout = price_for(c.get("model_id"))
        cost += int(c["in_tokens"] or 0) * pin / 1e6 + int(c["out_tokens"] or 0) * pout / 1e6
    if row.get("last_failed") or (
        finished >= MIN_RUNS_FOR_ERROR
        and success_pct is not None
        and success_pct < ERROR_SUCCESS_PCT
    ):
        state = "error"
    elif running:
        state = "running"
    else:
        state = "healthy"
    last = row.get("last_run_at")
    return {
        "invocations": int(row["invocations"] or 0),
        "success_pct": success_pct,
        "errors": errors,
        "running": running,
        "p50_ms": None if row.get("p50_ms") is None else round(float(row["p50_ms"])),
        "p95_ms": None if row.get("p95_ms") is None else round(float(row["p95_ms"])),
        "mean_input_tokens": None if row.get("mean_in") is None else round(float(row["mean_in"])),
        "mean_output_tokens": None
        if row.get("mean_out") is None
        else round(float(row["mean_out"])),
        "cost_usd": round(cost, 4),
        "model_id": row.get("model_id"),
        "last_run_at": last.isoformat() if isinstance(last, datetime) else last,
        "state": state,
    }


async def fetch_agent_metrics(organization_id: str, hours: int) -> dict[str, Any]:
    rows = await db.fetch(
        """SELECT ar.agent_name,
                  COUNT(*)::INT AS invocations,
                  COUNT(*) FILTER (WHERE ar.finished_at IS NOT NULL AND ar.error_text IS NULL)::INT AS ok,
                  COUNT(*) FILTER (WHERE ar.error_text IS NOT NULL)::INT AS errors,
                  COUNT(*) FILTER (WHERE ar.finished_at IS NULL AND ar.error_text IS NULL
                                     AND ar.started_at > NOW() - ($3::INT * INTERVAL '1 minute'))::INT AS running,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY ar.latency_ms)
                      FILTER (WHERE ar.latency_ms IS NOT NULL) AS p50_ms,
                  percentile_cont(0.95) WITHIN GROUP (ORDER BY ar.latency_ms)
                      FILTER (WHERE ar.latency_ms IS NOT NULL) AS p95_ms,
                  AVG(ar.input_tokens)::FLOAT AS mean_in,
                  AVG(ar.output_tokens)::FLOAT AS mean_out,
                  MAX(ar.started_at) AS last_run_at,
                  (array_agg(ar.model_id ORDER BY ar.started_at DESC)
                      FILTER (WHERE ar.model_id IS NOT NULL))[1] AS model_id,
                  (array_agg(ar.error_text IS NOT NULL ORDER BY ar.started_at DESC))[1] AS last_failed
           FROM agent_runs ar
           JOIN cases c ON c.id = ar.case_id
           WHERE c.organization_id = $1
             AND ar.started_at >= NOW() - ($2::INT * INTERVAL '1 hour')
           GROUP BY ar.agent_name""",
        organization_id,
        hours,
        RUNNING_WINDOW_MINUTES,
    )
    cost_rows = await db.fetch(
        """SELECT ar.agent_name, ar.model_id,
                  COALESCE(SUM(ar.input_tokens), 0)::BIGINT AS in_tokens,
                  COALESCE(SUM(ar.output_tokens), 0)::BIGINT AS out_tokens
           FROM agent_runs ar
           JOIN cases c ON c.id = ar.case_id
           WHERE c.organization_id = $1
             AND ar.started_at >= NOW() - ($2::INT * INTERVAL '1 hour')
           GROUP BY ar.agent_name, ar.model_id""",
        organization_id,
        hours,
    )
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for c in cost_rows:
        by_agent.setdefault(c["agent_name"], []).append(dict(c))
    agents = {
        r["agent_name"]: summarize_agent(dict(r), by_agent.get(r["agent_name"], [])) for r in rows
    }
    return {
        "window_hours": hours,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "agents": agents,
        "totals": {
            "invocations": sum(a["invocations"] for a in agents.values()),
            "cost_usd": round(sum(a["cost_usd"] for a in agents.values()), 4),
        },
    }
