"""Renumber slides + update totals after inserting the Neuro-SAN AAOSA
slide between (old) Slide 7 and (old) Slide 8.

Effect on build_winning_deck.js:
  - addPageNum(s, N, 18[, dark])  for N in 2..6  → addPageNum(s, N, 19[, dark])
  - addPageNum(s, N, 18[, dark])  for N in 9..17 → addPageNum(s, N+1, 19[, dark])
  - // SLIDE N — ...               for N in 9..18 → // SLIDE N+1 — ...

Slides 7, 8 (new), 9 (renamed) are already correct (set by hand in the
redesign edits). Slide 1 + last slide had no page-num call originally.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "build_winning_deck.js"


def renumber(text: str) -> tuple[str, dict]:
    counts = {"page_total_only": 0, "page_bumped": 0, "comment_bumped": 0}

    # 1. Bump section-header comments first (high N down to low N to avoid
    #    double-bumping). Affects 9..18.
    for n in range(18, 8, -1):
        pat = rf'^// SLIDE {n} — '
        new = f'// SLIDE {n + 1} — '
        new_text, k = re.subn(pat, new, text, flags=re.MULTILINE)
        text = new_text
        counts["comment_bumped"] += k

    # 2. Page-number calls. Order: bump 17..9 (becomes 18..10) FIRST; then
    #    fix the totals on 2..6 (no number change, just /18 → /19).
    for n in range(17, 8, -1):
        # Match addPageNum(s, N, 18) and addPageNum(s, N, 18, true)
        pat = rf'addPageNum\(s, {n}, 18(\s*,\s*true)?\);'
        def repl(m, n=n):
            tail = m.group(1) or ""
            return f"addPageNum(s, {n + 1}, 19{tail});"
        new_text, k = re.subn(pat, repl, text)
        text = new_text
        counts["page_bumped"] += k

    for n in range(2, 7):
        pat = rf'addPageNum\(s, {n}, 18(\s*,\s*true)?\);'
        def repl(m, n=n):
            tail = m.group(1) or ""
            return f"addPageNum(s, {n}, 19{tail});"
        new_text, k = re.subn(pat, repl, text)
        text = new_text
        counts["page_total_only"] += k

    return text, counts


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    if "addPageNum(s, 8, 19)" not in raw or "addPageNum(s, 9, 19)" not in raw:
        print("ABORT: expected redesigned Slide 7/8/9 markers not found", file=sys.stderr)
        return 1
    out, counts = renumber(raw)
    SRC.write_text(out, encoding="utf-8")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
