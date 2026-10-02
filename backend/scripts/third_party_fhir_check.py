"""Run the optional third-party FHIR R4 interoperability check and record the result.

Sends a freshly generated SYNTHETIC Bundle to the configured third-party FHIR server, reads it back and
compares the semantic fields. Writes a JSON evidence record. A generic FHIR server does not validate OAH
profiles, so this is an extra external FHIR path, not an OAH conformance result.

  python scripts/third_party_fhir_check.py --out ../docs/track7/third-party-result.json [--system-trust]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402
from app.interop import external_fhir  # noqa: E402


def generate_bundle() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bundle.json"
        subprocess.run(
            [sys.executable, str(BACKEND / "scripts" / "export_track7_validator_bundle.py"), "--output", str(path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return json.loads(path.read_text(encoding="utf-8"))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", default=settings.EXTERNAL_FHIR_BASE_URL)
    parser.add_argument("--timeout", type=float, default=settings.EXTERNAL_FHIR_TIMEOUT_S)
    parser.add_argument("--system-trust", action="store_true", help="trust the OS certificate store (needs truststore)")
    args = parser.parse_args()
    result = await external_fhir.exchange(
        generate_bundle(),
        synthetic=True,
        base_url=args.base_url,
        request_timeout_s=args.timeout,
        system_trust=args.system_trust or settings.EXTERNAL_FHIR_SYSTEM_TRUST,
    )
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "endpoint", "resource_id", "detail")}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
