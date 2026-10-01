"""Offline verifier: python scripts/verify_passport.py <passport.json>."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.onehealth.passport import verify_portable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify an Evidence Passport without network access"
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        result = verify_portable(json.loads(args.file.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        result = {"status": "INTEGRITY FAILURE", "valid": False}
    print(result["status"])
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
