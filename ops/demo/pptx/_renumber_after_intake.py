"""Renumber slides after inserting Document Intake at slot 10.

Effect:
  - Comments "// SLIDE N — <topic>" matched on topic substring (avoids the
    SLIDE 11 collision between newly-renamed TECH STACK and BUSINESS IMPACT)
  - addPageNum totals: 19 → 20 across all slides
  - addPageNum slide numbers: slides 11..18 → 12..19 (the new slide takes
    slot 10, pushing the rest down one)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "build_winning_deck.js"

# Comment renames keyed on TOPIC (unique). The new SLIDE 10 (Document Intake)
# and SLIDE 11 (Tech Stack — already manually renamed by my edit) are skipped.
_COMMENT_RENAMES = [
    # (old_number, new_number, topic_substring_unique_to_that_section)
    (11, 12, "BUSINESS IMPACT"),
    (12, 13, "MARKET HIERARCHY"),
    (13, 14, "SCALABLE / REUSABLE"),
    (14, 15, "STRATEGIC FIT"),
    (15, 16, "COMPLIANCE"),
    (16, 17, "ROADMAP"),
    (17, 18, "TEAM"),
    (18, 19, "THE ASK"),
    (19, 20, "THANK YOU"),
]


def renumber(text: str) -> tuple[str, dict]:
    counts = {"comments": 0, "page_total_only": 0, "page_bumped": 0}

    for old, new, topic in _COMMENT_RENAMES:
        pat = rf'^// SLIDE {old} — ({re.escape(topic)})'
        new_text, k = re.subn(pat, f"// SLIDE {new} — \\1", text, flags=re.MULTILINE)
        text = new_text
        counts["comments"] += k

    # addPageNum: slides 2..10 get total bumped /19 → /20 (number unchanged)
    for n in range(2, 11):
        pat = rf'addPageNum\(s, {n}, 19(\s*,\s*true)?\);'
        def repl(m, n=n):
            tail = m.group(1) or ""
            return f"addPageNum(s, {n}, 20{tail});"
        new_text, k = re.subn(pat, repl, text)
        text = new_text
        counts["page_total_only"] += k

    # addPageNum: slides 11..18 (descending so we don't double-bump) → 12..19, /19 → /20
    for n in range(18, 10, -1):
        pat = rf'addPageNum\(s, {n}, 19(\s*,\s*true)?\);'
        def repl(m, n=n):
            tail = m.group(1) or ""
            return f"addPageNum(s, {n + 1}, 20{tail});"
        new_text, k = re.subn(pat, repl, text)
        text = new_text
        counts["page_bumped"] += k

    return text, counts


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    if "addPageNum(s, 10, 20)" not in raw:
        print("ABORT: expected the new Document Intake slide marker not found", file=sys.stderr)
        return 1
    out, counts = renumber(raw)
    SRC.write_text(out, encoding="utf-8")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
