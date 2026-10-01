"""Run the Track 7 exchange through an independent local HTTP receiver process.

Usage from the repository root:
    python backend/scripts/track7_network_demo.py

The script starts a local SQLite-backed CLINI-CASE API and a separate System B
Uvicorn process, then executes the same authenticated import/approve/generate/
validate/transfer/return flow as the workbench. No Docker or cloud service is used.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

from track7_demo import main as run_demo  # noqa: E402


async def main(args: argparse.Namespace) -> None:
    await run_demo(
        argparse.Namespace(
            api_port=args.api_port,
            receiver_port=args.receiver_port,
            frontend_port=0,
            sqlite=True,
            ai=False,
            open=False,
            keep_running=False,
            network_only=True,
        )
    )

    metrics_path = BACKEND / ".cache/track7/runtime-metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("receiver_mode") != "HTTP network":
        raise RuntimeError("System A did not report the independent HTTP receiver mode")
    if metrics.get("roundtrip_status") != "passed" or not metrics.get(
        "resource_ids_reassigned"
    ):
        raise RuntimeError("The returned bundle did not pass ID-independent semantic round-trip")
    if not metrics.get("roundtrip_sample_preserved"):
        raise RuntimeError("The returned bundle's normalized sample differs from the source")

    print("\nSYSTEM A - CLINI-CASE API (separate local process)")
    print("  |\n  v")
    print("HTTP TRANSFER - FHIR Bundle sent to 127.0.0.1:" + str(args.receiver_port))
    print("  |\n  v")
    print("SYSTEM B - independent receiver process validated and stored the Bundle")
    print("  |\n  v")
    print("ID REASSIGNMENT - returned resource IDs and internal references rewritten")
    print("  |\n  v")
    print("HTTP RETURN - returned Bundle received by CLINI-CASE")
    print("  |\n  v")
    print(
        "ROUND-TRIP PASS - semantic sample fields preserved; "
        f"{metrics['roundtrip_fields_preserved']}/{metrics['roundtrip_fields_total']} checked"
    )
    print(f"Runtime evidence: {metrics_path.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--receiver-port", type=int, default=8091)
    asyncio.run(main(parser.parse_args()))
