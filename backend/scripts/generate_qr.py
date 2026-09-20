"""Generate QR codes for the live ClinCase endpoints — for the demo deck.

Each QR encodes a deep-link a judge can scan during Q&A:
    /api/v1/architecture/layers
    /api/v1/foundry/manifest
    /api/v1/responsible-ai/model-card.md
    /api/v1/healthz/deep
    /roi (frontend)
    /architecture (frontend)
    /compliance (frontend)
    /industrialize (frontend)

Output: ops/demo/qr-codes/*.png

Run:
    cd backend && .venv/Scripts/python.exe -m scripts.generate_qr [--base-url https://api.clincase.example.com]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "ops" / "demo" / "qr-codes"


# (label, url-suffix, audience hint)
TARGETS = [
    ("architecture-layers",     "/api/v1/architecture/layers",        "judge: show me the architecture"),
    ("foundry-manifest",        "/api/v1/foundry/manifest",            "judge: Cognizant Foundry compatibility"),
    ("model-card",              "/api/v1/responsible-ai/model-card.md","compliance officer: model card"),
    ("healthz-deep",            "/api/v1/healthz/deep",                "SRE: per-layer health"),
    ("capabilities",            "/api/v1/capabilities",                "demo verification: feature flags"),
    ("version",                 "/api/v1/version",                     "incident correlation"),
    ("frontend-architecture",   "/architecture",                       "live UI: 5-layer diagram"),
    ("frontend-roi",            "/roi",                                "live UI: ROI calculator"),
    ("frontend-compliance",     "/compliance",                          "live UI: org compliance scorecard"),
    ("frontend-industrialize",  "/industrialize",                      "live UI: Cognizant Foundry panel"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate QR codes for ClinCase live endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Base URL the QR codes encode (default: http://localhost:8000)")
    parser.add_argument("--frontend-base-url", default="http://localhost:5173",
                        help="Frontend base URL for /architecture, /roi, etc.")
    args = parser.parse_args()

    try:
        import qrcode  # type: ignore[import-not-found]
    except ImportError:
        print("missing dep: pip install qrcode[pil]", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    index_md_lines = ["# ClinCase demo QR codes", "",
                      f"Generated against backend `{args.base_url}` and frontend `{args.frontend_base_url}`. Re-run via `python -m scripts.generate_qr --base-url <url> --frontend-base-url <url>`.",
                      "",
                      "| Label | Audience | URL | QR |",
                      "|---|---|---|---|"]

    for label, suffix, audience in TARGETS:
        base = args.frontend_base_url if not suffix.startswith("/api") else args.base_url
        url = f"{base.rstrip('/')}{suffix}"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        out_path = OUT_DIR / f"{label}.png"
        img.save(out_path)
        index_md_lines.append(f"| `{label}` | {audience} | `{url}` | ![{label}](./{label}.png) |")
        print(f"  {out_path.name}  ({url})")
        written += 1

    (OUT_DIR / "README.md").write_text("\n".join(index_md_lines) + "\n", encoding="utf-8")
    print(f"\nwrote {written} QR codes + README to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
