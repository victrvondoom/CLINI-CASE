"""Bulk-swap the placeholder hostname (clincase.xzashr.com) for the live
AWS S3 endpoint across the docs + pptx generators.

Run after the May-6 AWS deployment landed. The print HTMLs were handled
by ops/demo/print/_swap_qr.py. This script handles the source generators
that bake URLs into the Word docs and PowerPoint deck.

We keep the swap minimal — JUST the hostname. Prose narratives that
mention "Cloudflare Pages" etc. are left for a follow-up rewrite so we
don't burn time inventing fresh marketing copy from a script.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE_HOST = "clincase-demo-26697.s3-website-us-east-1.amazonaws.com"
LIVE_URL = f"http://{LIVE_HOST}/"

# Both forms appear in the .js files — order matters (longest first)
PAIRS = [
    ("https://clincase.xzashr.com", f"http://{LIVE_HOST}"),
    ("clincase.xzashr.com", LIVE_HOST),
]

TARGETS = [
    ROOT / "docs" / "_build_doc1_glossary.js",
    ROOT / "docs" / "_build_doc2_story.js",
    ROOT / "docs" / "_build_doc3_qna.js",
    ROOT / "docs" / "_build_doc8_build_journal.js",
    ROOT / "pptx" / "build_winning_deck.js",
]


def swap(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    before = sum(raw.count(old) for old, _ in PAIRS)
    if before == 0:
        return {"file": path.name, "swapped": 0, "skipped": "no refs"}
    for old, new in PAIRS:
        raw = raw.replace(old, new)
    path.write_text(raw, encoding="utf-8")
    return {"file": path.name, "swapped": before}


def main() -> int:
    print(f"Replacing -> {LIVE_HOST}", file=sys.stderr)
    rows = [swap(t) for t in TARGETS]
    total = sum(r.get("swapped", 0) for r in rows)
    for r in rows:
        print(r)
    print(f"\nTotal references swapped: {total}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
