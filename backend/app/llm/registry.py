"""Config-driven model registry and deterministic router (Phases 5-6).

* No model ids are hard-coded here. The registry is built from existing settings (so default behaviour
  is unchanged) and may be extended or overridden with ``MODEL_REGISTRY_JSON`` (inline JSON or a file
  path). Entries carry a ``status``: only ``active`` entries are routable; ``unverified`` (account/region
  availability not confirmed) and ``disabled`` entries are refused, never silently substituted.
* Routing is a pure function of (provider, tier, optional per-role override, explicit fallback chain).
  The decision records *why* a model was chosen, and any fallback taken is explicit and recorded.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from app.config import settings

Status = Literal["active", "unverified", "disabled"]


class ModelRoutingError(Exception):
    """No routable model for the request (refused; the router never guesses a substitute)."""


@dataclass(frozen=True)
class ModelEntry:
    provider: str
    tier: str  # "standard" | "lite" | any configured tier name
    model_id: str
    region: str | None = None
    status: Status = "active"
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    fallbacks: tuple[str, ...] = ()  # explicit ordered tier names to try if this one is unroutable


@dataclass(frozen=True)
class RouteDecision:
    model_id: str
    provider: str
    tier: str
    reason: str
    fallback_from: str | None = None
    considered: tuple[str, ...] = field(default_factory=tuple)


def _builtin() -> list[ModelEntry]:
    """Entries derived from existing settings so today's behaviour is exactly preserved."""
    return [
        ModelEntry("bedrock", "standard", settings.BEDROCK_MODEL_ID, settings.AWS_REGION),
        ModelEntry("bedrock", "lite", settings.BEDROCK_HAIKU_MODEL_ID, settings.AWS_REGION),
        ModelEntry("openrouter", "standard", settings.OPENROUTER_MODEL),
        ModelEntry("openrouter", "lite", "anthropic/claude-haiku-4.5"),
        ModelEntry("anthropic", "standard", settings.ANTHROPIC_MODEL),
        ModelEntry("anthropic", "lite", "claude-haiku-4-5"),
    ]


def _load_overrides() -> list[ModelEntry]:
    raw = os.environ.get("MODEL_REGISTRY_JSON", "").strip()
    if not raw:
        return []
    if not raw.startswith(("[", "{")) and os.path.isfile(raw):
        with open(raw, encoding="utf-8") as fh:
            raw = fh.read()
    data = json.loads(raw)
    out = []
    for d in data if isinstance(data, list) else data.get("models", []):
        d = dict(d)
        d["fallbacks"] = tuple(d.get("fallbacks", ()))
        out.append(ModelEntry(**d))
    return out


def load_registry() -> dict[tuple[str, str], ModelEntry]:
    """(provider, tier) -> entry; overrides replace built-ins with the same key."""
    reg = {(e.provider, e.tier): e for e in _builtin()}
    for e in _load_overrides():
        reg[(e.provider, e.tier)] = e
    return reg


def route(
    tier: str,
    *,
    provider: str | None = None,
    registry: dict[tuple[str, str], ModelEntry] | None = None,
) -> RouteDecision:
    """Deterministically choose a model for ``tier``; raises ModelRoutingError rather than guessing."""
    prov = provider or settings.LLM_PROVIDER
    reg = registry if registry is not None else load_registry()
    first = reg.get((prov, tier))
    tried: list[str] = []
    cand, origin = first, None
    queue = list(first.fallbacks) if first else []
    while True:
        if cand is not None:
            tried.append(f"{cand.tier}:{cand.status}")
            if cand.status == "active" and cand.model_id:
                reason = "configured tier" if origin is None else f"explicit fallback from {origin}"
                return RouteDecision(cand.model_id, prov, cand.tier, reason, origin, tuple(tried))
        if not queue:
            break
        origin = origin or tier
        cand = reg.get((prov, queue.pop(0)))
    raise ModelRoutingError(
        f"no active model for provider={prov!r} tier={tier!r} (considered: {tried or 'none'})"
    )
