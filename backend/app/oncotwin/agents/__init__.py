"""OncoTwin agents + twin graph (kept outside app.agents so the ClinCase 7-agent manifest is unchanged)."""
from __future__ import annotations

from typing import Any

from app.oncotwin.agents.twin_agents import ONCOTWIN_AGENTS


def oncotwin_manifest() -> dict[str, Any]:
    from app.oncotwin.agents.graph import TOPOLOGY

    entries = []
    for i, agent in enumerate(ONCOTWIN_AGENTS, start=1):
        e = agent.manifest_entry()
        e.update({"index": i, "kind": "twin_agent", "n_sub_agents": 0, "sub_agents": []})
        entries.append(e)
    return {"n_agents": len(entries), "agents": entries, "graph": TOPOLOGY,
            "note": "Deterministic agents on the ClinCase Agent[I, O] framework; ClinCase's 7-agent graph is unchanged."}


__all__ = ["ONCOTWIN_AGENTS", "oncotwin_manifest"]
