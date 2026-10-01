"""Public agent manifest endpoint.

Surfaces the 7-agent / 22-sub-agent decomposition for the frontend Agents
page and any external MCP / TriZetto AI Gateway integration that wants to
introspect the system.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.manifest import AGENT_MANIFEST, flatten_sub_agents, total_sub_agents
from app.analytics.agent_metrics import fetch_agent_metrics
from app.auth import get_current_user
from app.db import db

router = APIRouter(prefix="/agents", tags=["agents"])

# Resolve prompt files relative to the `app/` directory so the path works
# the same locally (ClinCase/backend/app/...) and inside the Docker container
# (/app/app/...). Repo-root-relative paths break in Docker because WORKDIR
# is /app and `parents[3]` resolves to `/`, not the project root.
_APP_DIR = Path(__file__).resolve().parents[1]
_PROMPTS_DIR = _APP_DIR / "prompts"


@lru_cache(maxsize=1)
def pipeline_graph() -> dict[str, Any] | None:
    """Topology of the compiled LangGraph pipeline — the real nodes and edges, not a hand-drawn diagram.

    Returns None if the graph cannot be built (the manifest must still be servable)."""
    try:
        from app.graph.build import build_full_graph

        g = build_full_graph().get_graph()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("pipeline graph could not be built")
        return None
    skip = {"__start__", "__end__"}
    edges = [
        {"source": e.source, "target": e.target, "conditional": bool(e.conditional)}
        for e in g.edges
    ]
    # Execution order: walk from __start__ following the first (unconditional-preferred) edge.
    nxt: dict[str, str] = {}
    for e in sorted(edges, key=lambda x: x["conditional"]):
        if "verifier" in (e["source"], e["target"]):
            continue  # optional gate (VERIFIER_ENABLED); the default pipeline order skips it
        nxt.setdefault(e["source"], e["target"])
    order: list[str] = []
    cur = nxt.get("__start__")
    while cur and cur not in skip and cur not in order:
        order.append(cur)
        cur = nxt.get(cur)
    # agents that are only reachable through conditional branches keep their graph position
    for n in g.nodes:
        if n not in skip and n not in order:
            order.append(n)
    return {"nodes": [n for n in g.nodes if n not in skip], "edges": edges, "order": order}


@router.get("/manifest")
async def agents_manifest() -> dict[str, Any]:
    """Return the full 7-agent / 22-sub-agent manifest plus the real pipeline topology."""
    graph = pipeline_graph()
    order = {n: i + 1 for i, n in enumerate(graph["order"])} if graph else {}
    agents = [{**a, "pipeline_index": order.get(a["name"])} for a in AGENT_MANIFEST]
    return {
        "n_agents": len(AGENT_MANIFEST),
        "n_sub_agents": total_sub_agents(),
        "agents": agents,
        "graph": graph,
    }


@router.get("/sub-agents")
async def sub_agents_flat() -> dict[str, Any]:
    """Flat list of every sub-agent across all parents — handy for /eval and /agents."""
    flat = flatten_sub_agents()
    return {"n": len(flat), "sub_agents": flat}


@router.get("/metrics")
async def agents_metrics(
    hours: int = Query(default=24, ge=1, le=24 * 30, description="Look-back window in hours."),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Real per-agent invocations / success / latency / tokens / cost for the caller's organisation."""
    try:
        return await fetch_agent_metrics(user["organization_id"], hours)
    except Exception as exc:  # noqa: BLE001 - never fabricate numbers when the database is unavailable
        raise HTTPException(
            503, "Agent metrics need the case database, which is unavailable."
        ) from exc


@router.get("/{agent_name}/runs")
async def agent_recent_runs(
    agent_name: str,
    limit: int = Query(default=10, ge=1, le=50),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the N most recent runs for an agent, scoped to the user's org."""
    try:
        rows = await db.fetch(
            """SELECT ar.id, ar.case_id, ar.started_at, ar.finished_at,
                      ar.latency_ms, ar.model_id, ar.input_tokens,
                      ar.output_tokens, ar.error_text
               FROM agent_runs ar
               JOIN cases c ON c.id = ar.case_id
               WHERE ar.agent_name = $1
                 AND c.organization_id = $2
               ORDER BY ar.started_at DESC
               LIMIT $3""",
            agent_name,
            user["organization_id"],
            limit,
        )
        return {"agent_name": agent_name, "runs": [dict(r) for r in rows]}
    except Exception:
        # DB-less deployments: surface an empty result rather than crashing.
        return {"agent_name": agent_name, "runs": [], "db_unavailable": True}


def _resolve_prompt_path(prompt_path: str) -> Path:
    """Resolve a manifest prompt_path to an absolute path under app/prompts/.

    Accepts both styles:
      • bare convention path:        prompts/<agent>/orchestrator.txt
      • repo-relative legacy path:   backend/app/prompts/<agent>/orchestrator.txt
        (we strip the backend/app/ prefix and resolve under _APP_DIR)

    Defends against directory traversal by anchoring under _APP_DIR.
    """
    p = prompt_path.lstrip("/")
    for prefix in ("backend/app/", "app/"):
        if p.startswith(prefix):
            p = p[len(prefix) :]
            break
    candidate = (_APP_DIR / p).resolve()
    if not str(candidate).startswith(str(_APP_DIR.resolve())):
        raise HTTPException(400, f"prompt_path escapes app/ root: {prompt_path}")
    return candidate


def _find_agent(agent_name: str) -> dict[str, Any] | None:
    """Locate an agent in the manifest by name (manifest uses `name`, the
    frontend ships `id`-style strings that are equivalent — both refer to
    the parent package name)."""
    for a in AGENT_MANIFEST:
        if a.get("name") == agent_name or a.get("qualified_name") == agent_name:
            return a
    return None


def _candidate_prompt_paths(agent_name: str) -> list[str]:
    """Manifest entries don't carry prompt_path, so fall back to convention.
    Each parent has a `prompts/<agent>/orchestrator.txt` (current layout) or
    a flat `prompts/<agent>.txt` (older). Paths are resolved relative to
    the app/ directory by _resolve_prompt_path."""
    return [
        f"prompts/{agent_name}/orchestrator.txt",
        f"prompts/{agent_name}.txt",
        f"prompts/{agent_name}_rerank.txt",
        f"agents/{agent_name}/prompt.txt",
    ]


def _locate_prompt_file(agent_name: str) -> tuple[Path | None, str | None]:
    for rel in _candidate_prompt_paths(agent_name):
        path = _resolve_prompt_path(rel)
        if path.exists():
            return path, rel
    return None, None


@router.get("/{agent_name}/prompt")
async def agent_prompt(
    agent_name: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the system prompt content for the given agent.

    Surfaces the actual `.txt` file from the repo so the /agents page can
    render the prompt that drives each LangGraph node — no separate prompt
    versioning DB needed for the demo.
    """
    agent = _find_agent(agent_name)
    if agent is None:
        raise HTTPException(404, f"Unknown agent '{agent_name}'")

    path, prompt_path = _locate_prompt_file(agent_name)
    if path is None:
        return {
            "agent_name": agent_name,
            "prompt_path": _candidate_prompt_paths(agent_name)[0],
            "content": None,
            "byte_size": 0,
            "error": (
                "Prompt file not found. Searched: " + ", ".join(_candidate_prompt_paths(agent_name))
            ),
        }
    content = await asyncio.to_thread(path.read_text, "utf-8")
    return {
        "agent_name": agent_name,
        "prompt_path": prompt_path,
        "content": content,
        "byte_size": len(content.encode("utf-8")),
        "line_count": content.count("\n") + 1,
    }


@router.post("/{agent_name}/contract-test")
async def agent_contract_test(
    agent_name: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Run the agent's contract test against its declared schema + prompt.

    Validates that:
      1. The agent exists in the manifest.
      2. Its prompt file exists on disk and is non-empty.
      3. Its input/output Pydantic schemas are declared.
      4. Its sub-agent decomposition is registered.

    Returns a structured PASS/FAIL the UI can render. Real pytest invocation
    is intentionally not wired here — that would require running the test
    runner inside the API process. CI handles that path."""
    agent = _find_agent(agent_name)
    if agent is None:
        raise HTTPException(404, f"Unknown agent '{agent_name}'")

    import time

    t0 = time.monotonic()
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "manifest.registered",
            "passed": True,
            "detail": f"agent {agent_name} present (kind={agent.get('kind')})",
        }
    )

    path, prompt_path = _locate_prompt_file(agent_name)
    if path is not None:
        content = await asyncio.to_thread(path.read_text, "utf-8")
        checks.append(
            {
                "name": "prompt.file_exists",
                "passed": True,
                "detail": f"{prompt_path} ({path.stat().st_size} B)",
            }
        )
        checks.append(
            {
                "name": "prompt.non_empty",
                "passed": bool(content.strip()),
                "detail": f"{len(content)} chars, {content.count(chr(10)) + 1} lines",
            }
        )
    else:
        checks.append(
            {
                "name": "prompt.file_exists",
                "passed": False,
                "detail": "no prompt file found via convention",
            }
        )

    has_input = bool(agent.get("input_schema"))
    has_output = bool(agent.get("output_schema"))
    checks.append(
        {
            "name": "contract.input_schema",
            "passed": has_input,
            "detail": str(agent.get("input_schema", "?"))[:80],
        }
    )
    checks.append(
        {
            "name": "contract.output_schema",
            "passed": has_output,
            "detail": str(agent.get("output_schema", "?"))[:80],
        }
    )

    n_sub = agent.get("n_sub_agents", len(agent.get("sub_agents") or []))
    checks.append(
        {
            "name": "decomposition.sub_agents",
            "passed": n_sub >= 1,
            "detail": f"{n_sub} sub-agents declared",
        }
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    return {
        "agent_name": agent_name,
        "status": "passed" if failed == 0 else "failed",
        "checks_passed": passed,
        "checks_failed": failed,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
    }
