"""Deterministic citation provenance checks, independent of model self-report.

These checks establish that a pointer resolves to supplied evidence. They do
not establish clinical truth or prove that every factual claim is supported;
the human reviewer remains responsible for those judgments.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.decision_composer.schemas import CitationLinkerInput, CitationLinkerOutput


def _clinical_pointers(value: Any, path: str = "") -> set[str]:
    pointers: set[str] = set()
    if isinstance(value, dict):
        resource_id = value.get("source_resource_id")
        if resource_id:
            pointers.add(resource_id)
        for key, child in value.items():
            if child is not None and child != "" and child != []:
                child_path = f"{path}.{key}" if path else key
                pointers.add(child_path)
                pointers.update(_clinical_pointers(child, child_path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            child_path = f"{path}[{i}]"
            pointers.add(child_path)
            pointers.update(_clinical_pointers(child, child_path))
            if isinstance(child, dict) and child.get("name"):
                pointers.add(f"{path}.{child['name']}")
    return pointers


def validate_citation_provenance(input: CitationLinkerInput, output: CitationLinkerOutput) -> None:
    """Reject incomplete or unresolvable citations before creating a decision."""
    if not output.every_claim_has_pointer:
        raise ValueError("Citation linker reported incomplete claim coverage; review is required")
    clinical_pointers = _clinical_pointers(input.snapshot.model_dump())
    for citation in output.citations:
        pointer = citation.pointer.strip()
        if not citation.text.strip() or not pointer:
            raise ValueError("Citations require non-blank claims and source pointers")
        if citation.kind == "clinical":
            if pointer not in clinical_pointers:
                raise ValueError("Clinical citation references evidence absent from the snapshot")
            continue
        # Explicit references are unambiguous, and preserve section/title data
        # in the supplied excerpt rather than trusting invented LLM sources.
        index_match = re.fullmatch(r"policy_excerpts\[(\d+)\]", pointer)
        if index_match:
            if int(index_match.group(1)) < len(input.excerpts):
                continue
            raise ValueError("Citation references an unavailable policy excerpt")
        # Preserve legacy readable pointers, but require the policy identity
        # and an actual supplied section, not just a plausible policy number.
        normalized = " ".join(pointer.casefold().split())
        if any(
            excerpt.policy_id
            and excerpt.section_heading
            and re.search(
                r"(?<!\w)" + re.escape(excerpt.policy_id.casefold()) + r"(?!\w)", normalized
            )
            and excerpt.payer_id.casefold() in normalized
            and " ".join(excerpt.section_heading.casefold().split()) in normalized
            for excerpt in input.excerpts
        ):
            continue
        raise ValueError("Citation authority cannot be resolved to supplied policy evidence")
