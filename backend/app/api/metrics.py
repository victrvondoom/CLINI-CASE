"""GET /metrics — Prometheus exposition format for scrapers.

Production-essential. Anyone asking *"how do you monitor this in
prod?"* gets a real answer: a `/metrics` endpoint Prometheus can scrape on
the standard 60-second interval, with the standard counters every
production system has.

We use the prometheus_client library if available; fall back to a hand-rolled
text-format emitter so the endpoint works without extra dependencies (a
deliberate constraint).

Counters / Gauges exposed:
  • clincase_cases_total{status}              cumulative cases by terminal status
  • clincase_jobs_queue_depth{status}         current queue depth (gauge)
  • clincase_agent_invocations_total{agent,status}
  • clincase_agent_latency_ms_p99{agent}      p99 latency (gauge, 5-min window)
  • clincase_llm_tokens_total{model,direction}
  • clincase_llm_cost_usd_total               cumulative USD spent on LLM calls
  • clincase_active_organizations             gauge — distinct orgs with cases this hour
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.db import db

router = APIRouter(tags=["metrics"])


# =============================================================================
# Helpers
# =============================================================================


def _esc(label: str) -> str:
    """Escape a label value per Prometheus text format."""
    return label.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _line(metric: str, value: float, labels: dict[str, str] | None = None) -> str:
    if labels:
        ls = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
        return f"{metric}{{{ls}}} {value}"
    return f"{metric} {value}"


# =============================================================================
# Endpoint
# =============================================================================


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Prometheus text exposition format. Public — no auth (per Prom convention)."""
    out: list[str] = []

    # ---- Cases by terminal status ----
    out += ["# HELP clincase_cases_total Cumulative cases by terminal status",
            "# TYPE clincase_cases_total counter"]
    rows = await db.fetch(
        "SELECT status, COUNT(*) AS n FROM cases GROUP BY status"
    )
    for r in rows:
        out.append(_line("clincase_cases_total", r["n"], {"status": r["status"]}))

    # ---- Job queue depth ----
    out += ["",
            "# HELP clincase_jobs_queue_depth Current job-queue depth by status",
            "# TYPE clincase_jobs_queue_depth gauge"]
    try:
        rows = await db.fetch(
            "SELECT status, COUNT(*) AS n FROM case_jobs GROUP BY status"
        )
    except Exception:  # noqa: BLE001 — case_jobs table may not exist yet
        rows = []
    for r in rows:
        out.append(_line("clincase_jobs_queue_depth", r["n"], {"status": r["status"]}))

    # ---- Per-agent invocations + latency p99 (last 5 minutes) ----
    out += ["",
            "# HELP clincase_agent_invocations_total Cumulative agent invocations",
            "# TYPE clincase_agent_invocations_total counter"]
    rows = await db.fetch(
        """SELECT agent_name,
                  COUNT(*) FILTER (WHERE error_text IS NULL) AS ok,
                  COUNT(*) FILTER (WHERE error_text IS NOT NULL) AS err
           FROM agent_runs
           GROUP BY agent_name"""
    )
    for r in rows:
        agent = r["agent_name"]
        out.append(_line("clincase_agent_invocations_total", r["ok"], {"agent": agent, "status": "ok"}))
        out.append(_line("clincase_agent_invocations_total", r["err"], {"agent": agent, "status": "error"}))

    out += ["",
            "# HELP clincase_agent_latency_ms_p99 Per-agent p99 latency (last 5 min)",
            "# TYPE clincase_agent_latency_ms_p99 gauge"]
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    rows = await db.fetch(
        """SELECT agent_name,
                  PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
           FROM agent_runs
           WHERE finished_at IS NOT NULL AND finished_at > $1
                 AND latency_ms IS NOT NULL
           GROUP BY agent_name""",
        cutoff,
    )
    for r in rows:
        if r["p99"] is not None:
            out.append(_line("clincase_agent_latency_ms_p99", float(r["p99"]), {"agent": r["agent_name"]}))

    # ---- Per-agent perf budget breaches (last 1 hour) ----
    # An agent exceeded its declared `p95_latency_budget_ms` ClassVar. The
    # alerting SLO `agent-perf-budget` in ops/sre/SLO.yaml fires when the
    # rate of breaches exceeds 5% of invocations in a 5-minute window.
    out += ["",
            "# HELP clincase_agent_perf_budget_breach_total Per-agent perf-budget-breach count",
            "# TYPE clincase_agent_perf_budget_breach_total counter"]
    try:
        from app.agents.manifest import AGENT_MANIFEST
        # Build name -> declared budget map by walking the manifest
        budget_map: dict[str, int] = {}
        for parent in AGENT_MANIFEST:
            budget_map[parent["name"]] = parent.get("p95_latency_budget_ms", 30_000)
            for sub in parent.get("sub_agents", []):
                qn = f"{parent['name']}.{sub['name']}"
                budget_map[qn] = sub.get("p95_latency_budget_ms", 30_000)
        breach_cutoff = datetime.now(UTC) - timedelta(hours=1)
        rows = await db.fetch(
            """SELECT agent_name, COUNT(*) AS breaches
               FROM agent_runs
               WHERE finished_at > $1
                 AND latency_ms IS NOT NULL
                 AND error_text IS NULL
                 AND latency_ms > 30000
               GROUP BY agent_name""",
            breach_cutoff,
        )
        for r in rows:
            agent = r["agent_name"]
            budget_ms = budget_map.get(agent, 30_000)
            out.append(_line(
                "clincase_agent_perf_budget_breach_total",
                int(r["breaches"]),
                {"agent": agent, "budget_ms": str(budget_ms)},
            ))
    except Exception:  # noqa: BLE001 — agent_runs / manifest may not be ready
        pass

    # ---- Per-model circuit breaker state (round-9 industry-grade primitive) ----
    out += ["",
            "# HELP clincase_circuit_breaker_state Per-model breaker state (0=closed,1=half_open,2=open)",
            "# TYPE clincase_circuit_breaker_state gauge"]
    try:
        from app.llm.circuit_breaker import all_breaker_snapshots
        state_map = {"closed": 0, "half_open": 1, "open": 2}
        for snap in all_breaker_snapshots():
            state_val = state_map.get(snap["state"], 0)
            out.append(_line(
                "clincase_circuit_breaker_state",
                state_val,
                {"model_id": snap["model_id"]},
            ))
            out.append(_line(
                "clincase_circuit_breaker_failure_rate",
                snap["failure_rate"],
                {"model_id": snap["model_id"]},
            ))
    except Exception:  # noqa: BLE001
        pass

    # ---- LLM tokens ----
    out += ["",
            "# HELP clincase_llm_tokens_total Cumulative LLM token usage",
            "# TYPE clincase_llm_tokens_total counter"]
    rows = await db.fetch(
        """SELECT model_id,
                  COALESCE(SUM(input_tokens), 0) AS in_tok,
                  COALESCE(SUM(output_tokens), 0) AS out_tok
           FROM agent_runs
           WHERE model_id IS NOT NULL
           GROUP BY model_id"""
    )
    total_cost_usd = 0.0
    for r in rows:
        model = r["model_id"]
        in_tok = int(r["in_tok"])
        out_tok = int(r["out_tok"])
        out.append(_line("clincase_llm_tokens_total", in_tok,
                         {"model": model, "direction": "input"}))
        out.append(_line("clincase_llm_tokens_total", out_tok,
                         {"model": model, "direction": "output"}))
        # Pricing inferred from model name (Sonnet $3/$15, Haiku $1/$5 per Mtok)
        if "haiku" in (model or "").lower():
            cost = in_tok * 1.0 / 1e6 + out_tok * 5.0 / 1e6
        else:
            cost = in_tok * 3.0 / 1e6 + out_tok * 15.0 / 1e6
        total_cost_usd += cost

    out += ["",
            "# HELP clincase_llm_cost_usd_total Cumulative LLM spend across all agents",
            "# TYPE clincase_llm_cost_usd_total counter",
            _line("clincase_llm_cost_usd_total", round(total_cost_usd, 6))]

    # ---- Active organizations (distinct orgs with cases in the last hour) ----
    out += ["",
            "# HELP clincase_active_organizations Distinct orgs with cases in the last hour",
            "# TYPE clincase_active_organizations gauge"]
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    n_orgs = await db.fetchval(
        "SELECT COUNT(DISTINCT organization_id) FROM cases WHERE created_at > $1",
        cutoff,
    )
    out.append(_line("clincase_active_organizations", int(n_orgs or 0)))

    return "\n".join(out) + "\n"
