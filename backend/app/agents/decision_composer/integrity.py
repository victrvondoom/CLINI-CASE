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


def clinical_pointers(value: Any) -> set[str]:
    """Every pointer a clinical citation may legitimately use for this snapshot."""
    return _clinical_pointers(value)


_EXCERPT_INDEX = re.compile(r"(?:policy_)?excerpts\[(\d+)\]")


def _clinical_path(pointer: str, pointers: set[str]) -> str | None:
    """`snapshot.biomarkers.HER2 = 'Positive'` -> `biomarkers.HER2`, only if that path exists."""
    path = pointer.strip()
    if path.startswith("snapshot."):
        path = path[len("snapshot.") :]
    path = path.split("=", 1)[0].strip()
    return path if path in pointers else None


def normalize_citation_pointers(
    input: CitationLinkerInput, output: CitationLinkerOutput
) -> CitationLinkerOutput:
    """Rewrite pointer spellings some models use into the canonical forms, but only when the
    canonical form resolves to supplied evidence. Anything else is left for validation to reject."""
    pointers = _clinical_pointers(input.snapshot.model_dump())
    fixed = []
    for citation in output.citations:
        pointer = citation.pointer.strip()
        update: dict[str, Any] = {}
        path = _clinical_path(pointer, pointers)
        index = _EXCERPT_INDEX.fullmatch(pointer)
        if citation.kind == "clinical":
            if path is not None and path != pointer:
                update = {"pointer": path}
        elif index and int(index.group(1)) < len(input.excerpts):
            update = {"pointer": f"policy_excerpts[{index.group(1)}]"}
        elif path is not None:
            # A snapshot field mislabelled as policy evidence: it is clinical evidence.
            update = {"pointer": path, "kind": "clinical"}
        fixed.append(citation.model_copy(update=update) if update else citation)
    return output.model_copy(update={"citations": fixed})


def drop_unresolvable_citations(
    input: CitationLinkerInput, output: CitationLinkerOutput
) -> tuple[CitationLinkerOutput, int]:
    """Keep only citations that resolve to supplied evidence; return how many were dropped.
    Invented sources are never shown. Raises if no verifiable citation remains."""
    kept = []
    last_error: ValueError | None = None
    for citation in output.citations:
        single = output.model_copy(update={"citations": [citation], "every_claim_has_pointer": True})
        try:
            validate_citation_provenance(input, single)
        except ValueError as exc:
            last_error = exc
            continue
        kept.append(citation)
    if not kept:
        raise ValueError(f"No citation resolves to supplied evidence ({last_error}); review is required")
    return output.model_copy(update={"citations": kept}), len(output.citations) - len(kept)


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
