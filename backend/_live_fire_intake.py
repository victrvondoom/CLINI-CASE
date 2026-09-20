"""Live-fire test of the Document Intake pipeline against AWS Bedrock.

Runs the EXACT code path the production /intake/parse-document endpoint
would run — same classifier, same vision prompt, same LLMClient — except
we skip FastAPI auth + DB persistence so the test can run with just AWS
credentials.

Pre-req: AWS Workshop temporary credentials in env vars
  $env:AWS_ACCESS_KEY_ID     = "ASIA..."
  $env:AWS_SECRET_ACCESS_KEY = "..."
  $env:AWS_SESSION_TOKEN     = "FwoG..."
  $env:LLM_PROVIDER          = "bedrock"
  $env:AWS_REGION            = "us-east-1"
  $env:BEDROCK_MODEL_ID      = "us.anthropic.claude-sonnet-4-6-v1:0"

Run:
  D:\\xzashr.ai Files\\clincase-workspace\\ClinCase\\backend\\.venv\\Scripts\\python.exe \\
    _live_fire_intake.py

Output:
  ops/aws/intake_live_fire_result.json — the actual IntakeResult that
  comes back from a real Sonnet 4.6 vision invoke on the synthetic Indian
  oncology Rx fixture. Screenshot this for the demo.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


async def main() -> int:
    fixture = HERE / "tests" / "fixtures" / "intake" / "handwritten_rx.png"
    if not fixture.exists():
        print(f"FATAL: fixture not found at {fixture}", file=sys.stderr)
        return 2

    raw = fixture.read_bytes()
    print(f"fixture       : {fixture.name} ({len(raw):,} bytes)")
    print(f"sha256        : {hashlib.sha256(raw).hexdigest()[:32]}…")

    # Force the production code path to use the Bedrock provider.
    import os
    if os.environ.get("LLM_PROVIDER", "").lower() != "bedrock":
        print(
            "WARN: LLM_PROVIDER is not 'bedrock'. Set it before running, e.g.\n"
            "  $env:LLM_PROVIDER='bedrock'\n"
            "Falling back to whatever the factory returns — the runner will "
            "raise NotImplementedError and the result will be a HITL-routed "
            "empty IntakeResult.",
            file=sys.stderr,
        )

    # Construct an IntakeDocument exactly as the FastAPI endpoint does.
    from app.models.intake import IntakeDocument
    doc = IntakeDocument(
        filename="handwritten_rx.png",
        mime_type="image/png",
        image_b64=base64.b64encode(raw).decode("ascii"),
        sha256=hashlib.sha256(raw).hexdigest(),
        source="upload",
    )

    # Run the actual production runner — classifier + vision call + assembly.
    from app.agents.intake import parse_document
    print("\ninvoking Document Intake (classifier → Bedrock vision → IntakeResult)…")
    result = await parse_document(doc)

    # ---- Pretty-print the result ----
    print()
    print("=" * 72)
    print("CLASSIFICATION")
    print("=" * 72)
    print(f"  document_type  : {result.classification.document_type}")
    print(f"  confidence     : {result.classification.confidence:.2f}")
    print(f"  rationale      : {result.classification.rationale}")
    print(f"  quality_flags  : {result.classification.quality_flags}")

    print()
    print("=" * 72)
    print(f"OCR · engine={result.ocr.engine}  confidence={result.ocr.overall_confidence:.2f}")
    print("=" * 72)
    print(f"  pages          : {result.ocr.pages}")
    print(f"  PHI redactions : {result.ocr.phi_redactions_applied}")
    print(f"  fields         : {len(result.ocr.extracted_fields)}")
    for f in result.ocr.extracted_fields:
        bar = "█" * int(f.confidence * 20)
        print(f"    {f.confidence:.2f} {bar:<20}  {f.name:<35}  {f.value}")

    print()
    print("=" * 72)
    print("CLINICAL SNAPSHOT (partial — feeds into Clinical Extractor)")
    print("=" * 72)
    print(json.dumps(result.clinical_snapshot_partial, indent=2)[:2000])

    print()
    print("=" * 72)
    print("ROUTING")
    print("=" * 72)
    print(f"  requires_human_review : {result.requires_human_review}")
    print(f"  risk_flags            : {result.risk_flags}")

    print()
    print("=" * 72)
    print("AUDIT (CMS-0057-F § IV.A)")
    print("=" * 72)
    print(json.dumps(result.audit, indent=2))

    # Save the full IntakeResult to disk for the demo screenshot
    out = HERE.parent / "ops" / "aws" / "intake_live_fire_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print()
    print(f"saved IntakeResult to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
