"""Swap the placeholder QR (encodes clincase.xzashr.com) with the live
AWS S3 QR (encodes the deployed showcase) across all three print HTMLs.

This is a one-shot script run by Claude Code on 2026-05-06 after the
S3 deployment landed. The new QR points to:
  http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com/

Idempotent: running it again is a no-op (the marker comment ensures
we don't re-swap an already-swapped file).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PRINT_DIR = Path(__file__).resolve().parent
SVG_PATH = PRINT_DIR / "_qr.svg"
LIVE_URL = "http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com/"
LIVE_HOST = "clincase-demo-26697.s3-website-us-east-1.amazonaws.com"
TARGETS = [
    PRINT_DIR / "architecture_poster.html",
    PRINT_DIR / "sample_artifacts_booklet.html",
    PRINT_DIR / "roi_tam_a3fold.html",
]

NEW_PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"')
NEW_VIEWBOX_RE = re.compile(r'viewBox="([^"]+)"')


def extract_new_qr() -> tuple[str, str]:
    raw = SVG_PATH.read_text(encoding="utf-8")
    vb_m = NEW_VIEWBOX_RE.search(raw)
    path_m = NEW_PATH_RE.search(raw)
    if not vb_m or not path_m:
        raise SystemExit("FAILED to extract viewBox/path from _qr.svg")
    return vb_m.group(1), path_m.group(1)


def build_replacement(viewbox: str, path_d: str, *, inline_style: bool) -> str:
    """Build the new <svg>...</svg> block.

    inline_style=True replicates the booklet's style="width:100%; ..."
    attribute; the poster + ROI fold use no inline style.
    """
    style_attr = ' style="width:100%; height:100%; display:block;"' if inline_style else ""
    return (
        f'<!-- CLINCASE-LIVE-AWS-QR · encodes {LIVE_URL} (deployed 2026-05-06) -->\n'
        f'        <svg viewBox="{viewbox}"{style_attr} preserveAspectRatio="xMidYMid meet" '
        f'aria-label="QR code linking to live ClinCase showcase on AWS S3">\n'
        f'          <path fill="#fff" d="M0 0h360v360H0z"/>\n'
        f'          <path transform="scale(8)" stroke="#0f172a" fill="none" d="{path_d}"/>\n'
        f'        </svg>'
    )


# Match only the <svg>...</svg> for the placeholder QR. The booklet
# wraps the svg in a sizing <div>, so we can't anchor on the comment.
OLD_SVG_RE = re.compile(
    r'<svg[^>]*?aria-label="QR code linking to https://clincase\.xzashr\.com">'
    r'.*?</svg>',
    re.DOTALL,
)

# Comment mentions of the placeholder URL — rewrite to the live URL.
OLD_COMMENT_RE = re.compile(r'https://clincase\.xzashr\.com')

# Caption text — bare hostname under the QR, used in all three files.
CAPTION_RE = re.compile(r'clincase\.xzashr\.com')


def swap_file(path: Path, viewbox: str, path_d: str) -> dict:
    raw = path.read_text(encoding="utf-8")
    if "CLINCASE-LIVE-AWS-QR" in raw:
        return {"file": path.name, "skipped": "already swapped"}

    # Booklet uses an inline-style attr to fill its wrapping div; the
    # poster + ROI fold leave styling to the surrounding container.
    inline_style = "sample_artifacts_booklet" in path.name

    # Build the replacement <svg>; OLD_SVG_RE captures from <svg to </svg>
    # so the replacement is just the <svg> itself (no outer comment).
    style_attr = ' style="width:100%; height:100%; display:block;"' if inline_style else ""
    indent = "          " if inline_style else "        "
    new_svg = (
        f'<svg viewBox="{viewbox}"{style_attr} preserveAspectRatio="xMidYMid meet" '
        f'aria-label="QR code linking to live ClinCase showcase on AWS S3">\n'
        f'{indent}  <path fill="#fff" d="M0 0h360v360H0z"/>\n'
        f'{indent}  <path transform="scale(8)" stroke="#0f172a" fill="none" d="{path_d}"/>\n'
        f'{indent}</svg>'
    )

    n_svg = len(OLD_SVG_RE.findall(raw))
    if n_svg == 0:
        return {"file": path.name, "error": "no SVG block matched"}
    raw = OLD_SVG_RE.sub(new_svg + " <!-- CLINCASE-LIVE-AWS-QR -->", raw, count=n_svg)

    n_comment = len(OLD_COMMENT_RE.findall(raw))
    raw = OLD_COMMENT_RE.sub(LIVE_URL, raw)

    n_caption = len(CAPTION_RE.findall(raw))
    raw = CAPTION_RE.sub(LIVE_HOST, raw)

    path.write_text(raw, encoding="utf-8")
    return {
        "file": path.name,
        "svg_blocks_replaced": n_svg,
        "comment_urls_swapped": n_comment,
        "captions_swapped": n_caption,
    }


def main() -> int:
    viewbox, path_d = extract_new_qr()
    print(f"viewBox: {viewbox}", file=sys.stderr)
    print(f"path d length: {len(path_d)} chars", file=sys.stderr)

    rows = [swap_file(t, viewbox, path_d) for t in TARGETS]
    for r in rows:
        print(r)

    err = [r for r in rows if r.get("error")]
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
