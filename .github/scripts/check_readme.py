"""Check the README's current product contract without matching incidental prose."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "Start here",
    "One connected evidence journey",
    "OneAquaHealth Track 7 — Digital Health Standards",
    "From environmental evidence to human-health context",
    "Seven-agent oncology workflow",
    "NVIDIA and model governance",
    "Oncology, OncoTwin and CardioTwin in depth",
    "Standards, validation and technical proof",
    "Monitoring, observability and verification",
    "Deployment: one application, several modes",
    "Verification commands",
    "Repository map",
    "Limits and next validation work",
)


def check_readme(content: str) -> list[str]:
    """Return actionable failures; headings inside code blocks never count."""
    headings: list[tuple[int, str, int]] = []
    visible_lines: list[str] = []
    diagrams = 0
    fence: str | None = None
    for line_number, line in enumerate(content.splitlines()):
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            delimiter, language = fence_match.groups()
            if fence is None:
                fence = delimiter
                if language.strip() == "mermaid":
                    diagrams += 1
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence):
                fence = None
            visible_lines.append("")
            continue
        # Code samples and repository trees are substantive section content,
        # while their apparent Markdown headings remain excluded below.
        visible_lines.append(line)
        if fence is None:
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if heading:
                headings.append((len(heading[1]), heading[2], line_number))

    errors = []
    if not headings or headings[0][:2] != (1, "CLINI-CASE"):
        errors.append("README must begin with the '# CLINI-CASE' product heading")
    for required in REQUIRED_SECTIONS:
        matching = [(level, name, start) for level, name, start in headings if name == required]
        if len(matching) != 1:
            errors.append(f"README must contain one heading: {required}")
            continue
        level, _, start = matching[0]
        end = next(
            (position for depth, _, position in headings if position > start and depth <= level),
            len(visible_lines),
        )
        body = [line.strip() for line in visible_lines[start + 1 : end] if line.strip()]
        if not any(not line.startswith("#") and len(line) >= 40 for line in body):
            errors.append(f"README section needs explanatory content: {required}")
    if diagrams < 4:
        errors.append("README must retain at least four Mermaid workflow/architecture diagrams")
    if fence is not None:
        errors.append("README has an unclosed code fence")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("README.md")
    try:
        errors = check_readme(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors = [f"Cannot read README: {exc}"]
    for error in errors:
        print(f"::error::{error}")
    if errors:
        return 1
    print(f"README has all {len(REQUIRED_SECTIONS)} core sections and Mermaid workflow diagrams.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
