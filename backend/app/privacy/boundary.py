"""Prompt data minimization; screening is not certified de-identification."""

from __future__ import annotations

from datetime import date
from typing import Any

_IDENTITY_FIELDS = frozenset(
    {
        "identifier",
        "telecom",
        "address",
        "contact",
        "photo",
        "text",
        "meta",
        "fullUrl",
        "presentedForm",
        "attachment",
        "communication",
        "generalPractitioner",
        "managingOrganization",
    }
)
_PERSON_TYPES = {"Patient", "Practitioner", "RelatedPerson", "Organization"}


def screen_text(text: str) -> str:
    from app.agents.clinical_extractor.sub_agents.phi_sanitizer import _PATTERNS

    for _, pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def prepare_fhir(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Return a minimized copy and alias-to-original map for local citation repair."""
    aliases: dict[str, str] = {}
    entries = bundle.get("entry", [])
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
        rid = resource.get("id")
        if isinstance(rid, str) and rid not in aliases:
            aliases[rid] = f"resource-{len(aliases) + 1}"

    def walk(value: Any, key: str = "") -> Any:
        if isinstance(value, list):
            return [walk(item, key) for item in value]
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            person = value.get("resourceType") in _PERSON_TYPES
            for field, item in value.items():
                if (
                    field in _IDENTITY_FIELDS
                    or (person and field in {"name", "birthDate"})
                    or ("reference" in value and field == "display")
                    or field in {"family", "given", "prefix", "suffix"}
                ):
                    continue
                result[field] = walk(item, field)
            if value.get("resourceType") == "Patient" and value.get("birthDate"):
                try:
                    born = date.fromisoformat(value["birthDate"])
                    today = date.today()
                    age = (
                        today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                    )
                    if 0 <= age <= 130:
                        result["ageYears"] = age
                except (TypeError, ValueError):
                    pass
            return result
        if isinstance(value, str):
            if key == "id":
                return aliases.get(value, "redacted-id")
            if key == "reference":
                return aliases.get(value.rsplit("/", 1)[-1], "redacted-reference")
            return screen_text(value)
        return value

    return walk(bundle), {alias: original for original, alias in aliases.items()}


def restore_source_ids(value: Any, alias_map: dict[str, str]) -> Any:
    """Restore citation IDs locally after provider processing."""
    if isinstance(value, dict):
        return {
            key: (
                alias_map.get(item, item)
                if key == "source_resource_id" and isinstance(item, str)
                else restore_source_ids(item, alias_map)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [restore_source_ids(item, alias_map) for item in value]
    return value
