"""Generate the QR SVG for all three ClinCase print materials.

The QR encodes the live AWS S3 static-website endpoint where the
12-route standalone showcase is hosted. ECC level H (30%) so the QR
keeps scanning even with a logo overlay or print smudge.

Output:
  _qr.svg                         — standalone (used as reference)

The same SVG <path> is hand-pasted into the three print HTMLs:
  architecture_poster.html
  sample_artifacts_booklet.html
  roi_tam_a3fold.html
"""
from __future__ import annotations

import sys
from pathlib import Path

import segno

# Live AWS endpoint (deployed 2026-05-06; see ops/aws/DEPLOYMENT_EVIDENCE.md)
URL = "http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com/"

OUT_DIR = Path(__file__).resolve().parent
SVG_PATH = OUT_DIR / "_qr.svg"


def main() -> int:
    qr = segno.make(URL, error="h")
    print(f"QR version: {qr.version}", file=sys.stderr)
    print(f"QR error correction: {qr.error}", file=sys.stderr)
    print(f"Modules: {qr.symbol_size()[0]}", file=sys.stderr)

    qr.save(
        SVG_PATH,
        kind="svg",
        scale=8,
        border=0,
        dark="#0f172a",
        light=None,  # transparent
        omitsize=True,  # we set viewBox manually
        svgclass="segno",
    )

    raw = SVG_PATH.read_text(encoding="utf-8")
    print(f"Wrote {SVG_PATH} ({len(raw)} bytes)", file=sys.stderr)
    print("--- BEGIN INLINE SVG ---")
    print(raw)
    print("--- END INLINE SVG ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
