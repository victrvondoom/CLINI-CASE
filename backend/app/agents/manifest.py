"""Aggregate manifest of all parent agents and their sub-agents.

Single source of truth for the architecture. Each parent package under
`app.agents.<parent>/` exposes:

  • a parent Agent[I, O] instance named `<parent>` (lowercase)
  • a `SUB_AGENTS` list of sub-agent instances

This module **auto-discovers** them by walking `app.agents.*` at import
time. Adding or removing a parent requires zero edits here — just create
or delete the package.

The contract: a directory under `app/agents/` is a parent package iff its
`__init__.py` exposes both `<dirname>` (the parent instance) and a
`SUB_AGENTS` list. Anything else (the `framework` runtime, the
`__pycache__` dir, etc.) is skipped.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from app.agents.framework import Agent

# Names under `app.agents.*` that are NOT parent agent packages
_NON_PARENT_PACKAGES = {"framework", "manifest"}


def _discover_parents() -> list[Agent[Any, Any]]:
    """Walk `app.agents.*`, import each candidate package, collect parent
    instances by name convention. Order: by `parent.<some_attr>` if present,
    else by package import order (stable since pkgutil.iter_modules is
    alphabetic on disk)."""
    parents: list[Agent[Any, Any]] = []
    import app.agents as agents_pkg

    for module_info in pkgutil.iter_modules(agents_pkg.__path__):
        name = module_info.name
        if not module_info.ispkg or name.startswith("_") or name in _NON_PARENT_PACKAGES:
            continue
        try:
            mod = importlib.import_module(f"app.agents.{name}")
        except Exception:  # noqa: BLE001 — skip broken packages, manifest must boot
            continue
        candidate = getattr(mod, name, None)  # convention: instance has same name as package
        if isinstance(candidate, Agent):
            parents.append(candidate)
    return parents


def _discover_sub_agents(parent_instance: Agent[Any, Any]) -> list[Agent[Any, Any]]:
    """A parent's package exposes its sub-agents via `SUB_AGENTS` (list of instances)."""
    parent_module = importlib.import_module(f"app.agents.{parent_instance.name}")
    return list(getattr(parent_module, "SUB_AGENTS", []))


# =============================================================================
# Build the manifest at import time
# =============================================================================


PARENT_AGENTS: list[Agent[Any, Any]] = _discover_parents()


def _parent_manifest_entry(
    parent: Agent[Any, Any], subs: list[Agent[Any, Any]], index: int
) -> dict[str, Any]:
    base = parent.manifest_entry()
    base.update({
        "index": index,
        "kind": "orchestrator",
        "n_sub_agents": len(subs),
        "sub_agents": [s.manifest_entry() for s in subs],
    })
    return base


AGENT_MANIFEST: list[dict[str, Any]] = [
    _parent_manifest_entry(parent, _discover_sub_agents(parent), index=i + 1)
    for i, parent in enumerate(PARENT_AGENTS)
]


# =============================================================================
# Helpers (back-compat with the old hand-listed manifest)
# =============================================================================


def total_sub_agents() -> int:
    return sum(len(a["sub_agents"]) for a in AGENT_MANIFEST)


def llm_backed_sub_agents_count() -> int:
    return sum(
        1 for a in AGENT_MANIFEST for s in a["sub_agents"] if s["is_llm_backed"]
    )


def deterministic_sub_agents_count() -> int:
    return total_sub_agents() - llm_backed_sub_agents_count()


def reflection_enabled_count() -> int:
    """Sub-agents with quality_threshold > 0 (i.e. self-grading enabled)."""
    return sum(
        1 for a in AGENT_MANIFEST for s in a["sub_agents"]
        if s.get("quality_threshold", 0) > 0
    )


def flatten_sub_agents() -> list[dict[str, Any]]:
    """Flat list of every sub-agent, prefixed with its parent."""
    out: list[dict[str, Any]] = []
    for parent in AGENT_MANIFEST:
        for sub in parent["sub_agents"]:
            out.append({
                "parent_id": parent["name"],
                "parent_display": parent["name"],
                **sub,
            })
    return out


def all_sub_agent_instances() -> list[Agent[Any, Any]]:
    out: list[Agent[Any, Any]] = []
    for parent in PARENT_AGENTS:
        out.extend(_discover_sub_agents(parent))
    return out


def get_sub_agent(parent_id: str, sub_name: str) -> Agent[Any, Any] | None:
    """Resolve a sub-agent instance by (parent_agent, name)."""
    for s in all_sub_agent_instances():
        if s.parent == parent_id and s.name == sub_name:
            return s
    return None


def get_parent_agent(parent_id: str) -> Agent[Any, Any] | None:
    """Resolve a parent agent instance by name."""
    for p in PARENT_AGENTS:
        if p.name == parent_id:
            return p
    return None
