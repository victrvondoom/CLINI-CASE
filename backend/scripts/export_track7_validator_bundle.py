"""Export a deterministic synthetic Track 7 Bundle for external HL7 validation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.onehealth import fhir  # noqa: E402
from app.onehealth.models import AuditEvent, ExposureRecord, LabSample, now  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND / ".cache/track7/oah-validation-bundle.json",
        help="Output file (default: ignored backend/.cache/track7 path)",
    )
    args = parser.parse_args()

    timestamp = now()
    record = ExposureRecord(
        id="track7-oah-validator-synthetic",
        organization_id="synthetic-validation-only",
        observation_id="source-record-validation-1",
        waterbody_id="waterbody-validation-1",
        waterbody_name="Synthetic validation waterbody",
        synthetic=True,
        sample=LabSample(
            sample_id="sample-validation-1",
            location_name="Synthetic validation site",
            kind="stream",
            laboratory="Synthetic validation laboratory",
            collector="Synthetic validation team",
            report_reference="report-validation-1",
            method="Synthetic method; not a real assay",
            collected_at=timestamp - timedelta(days=1),
            reported_at=timestamp,
            analyte="dissolved_arsenic",
            value=18.2,
            unit="ug/L",
        ),
        audit=[
            AuditEvent(
                action="synthetic_validator_fixture_created",
                actor_id="validation-script",
                at=timestamp,
                note="Synthetic fixture only; no laboratory or health evidence",
            )
        ],
    )
    bundle = fhir.export(record)
    local = fhir.validate(bundle)
    if not local["valid"]:
        raise SystemExit(f"Local application validation failed: {local['operation_outcome']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "sha256": fhir.digest(bundle),
                "application_validation": "PASS",
                "external_hl7_validation": "NOT_RUN_BY_THIS_SCRIPT",
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
