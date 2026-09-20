"""Generate a high-res PNG QR for the THANK YOU slide of the pitch deck.

Output: ops/demo/pptx/_qr_aws.png  (600x600, transparent bg, dark navy modules)

The PPT build script (build_winning_deck.js) embeds this PNG into slide
18 via pptxgenjs addImage(). Encodes the live AWS S3 endpoint so audience
members can scan during the live pitch.
"""
from __future__ import annotations

from pathlib import Path

import segno

URL = "http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com/"
OUT = Path(__file__).resolve().parent / "_qr_aws.png"


def main() -> int:
    qr = segno.make(URL, error="h")
    qr.save(
        OUT,
        scale=12,           # 12 px per module → ~600 px overall
        border=2,           # quiet zone for projector readability
        dark="#0F172A",     # match deck navy
        light=None,         # transparent → blends with slide background
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {qr.symbol_size()} pixels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
