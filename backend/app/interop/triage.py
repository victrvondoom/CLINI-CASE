"""Which pending mappings may be approved as a batch. Human review is reduced, never removed.

A mapping is "safe" only when every condition below holds; anything else stays an individual,
reviewer-owned decision. The generic arsenic label can never be safe: dissolved/total/inorganic
speciation must be confirmed by a person.
"""

from __future__ import annotations

from typing import Any, Literal

from app.interop.models import TARGETS

Triage = Literal["safe", "review", "unresolved", "decided"]
MIN_CONFIDENCE = 0.8
SAFE_TERMINOLOGY = {"oah_verified_preferred", "local_code"}


def is_generic_arsenic(source_field: str) -> bool:
    return source_field.strip().lower().replace(" ", "_") == "arsenic"


def classify(mapping: dict[str, Any]) -> Triage:
    """safe | review (needs a person) | unresolved (no allowlisted target) | decided (already answered)."""
    if mapping.get("decision") != "pending":
        return "decided"
    target = mapping.get("target")
    if not target or target not in TARGETS:
        return "unresolved"
    deterministic = mapping.get("origin") == "deterministic"
    confident = float(mapping.get("confidence") or 0) >= MIN_CONFIDENCE
    terminology_ok = mapping.get("concept") is None or mapping.get("terminology_status") in SAFE_TERMINOLOGY
    if deterministic and confident and terminology_ok and not is_generic_arsenic(mapping["source_field"]):
        return "safe"
    return "review"


def summarize(mappings: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"safe": [], "review": [], "unresolved": []}
    for mapping in mappings:
        kind = classify(mapping)
        if kind in groups:
            groups[kind].append(mapping["source_field"])
    return groups
