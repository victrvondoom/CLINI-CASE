"""Run the official HL7 FHIR validator on the CURRENT Track 7 Bundle and record the real result.

Two subcommands, both stdlib-only:

  package   Build a loadable OAH package (.tgz) from SUSHI output of the pinned hl7-eu/oah source.
  validate  Export the current synthetic Bundle, run validator_cli.jar (core, +OAH, +OAH+terminology),
            and write docs/track7/validation-result.json with every issue (nothing suppressed).

Nothing here certifies conformance. The OAH package is built locally from a pinned commit because no
published package exists; see docs/track7/VALIDATION.md.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.onehealth import fhir  # noqa: E402

KEEP = ("StructureDefinition", "ValueSet", "CodeSystem", "ImplementationGuide")
TX_SERVER = "https://tx.fhir.org/r4"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(source: Path, out: Path) -> None:
    """Pack SUSHI's conformance resources (no examples) into an FHIR package archive."""
    resources = source / "fsh-generated" / "resources"
    files = [p for p in sorted(resources.glob("*.json")) if p.name.split("-")[0] in KEEP]
    manifest = {
        "name": "hl7.eu.fhir.oah",
        "version": "0.1.0-ci-build",
        "canonical": "http://hl7.eu/fhir/ig/oah",
        "type": "fhir.ig",
        "fhirVersions": ["4.0.1"],
        "dependencies": {"hl7.fhir.r4.core": "4.0.1", "hl7.fhir.uv.xver-r5.r4": "0.1.0"},
        "description": "Built locally with SUSHI from hl7-eu/oah commit "
        f"{fhir.OAH_COMMIT}; NOT an official publication.",
    }
    with tarfile.open(out, "w:gz") as tar:

        def add(name: str, data: bytes) -> None:
            info = tarfile.TarInfo("package/" + name)
            info.size, info.mtime = len(data), 0  # fixed mtime keeps the archive reproducible
            tar.addfile(info, io.BytesIO(data))

        add("package.json", json.dumps(manifest, indent=2).encode())
        for path in files:
            add(path.name, path.read_bytes())
    print(f"{len(files)} resources -> {out}\nsha256 {sha256(out)}")


def export_bundle(path: Path) -> str:
    """Write the bundle the current implementation generates; return its SHA-256."""
    subprocess.run(
        [sys.executable, str(BACKEND / "scripts" / "export_track7_validator_bundle.py"), "--output", str(path)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return sha256(path)


def run_once(
    label: str, args: argparse.Namespace, bundle: Path, extra: list[str], outcome: Path
) -> dict[str, object]:
    command = [
        args.java,
        "-Djavax.net.ssl.trustStoreType=Windows-ROOT" if sys.platform == "win32" else "-Dfile.encoding=UTF-8",
        "-jar",
        str(args.jar),
        str(bundle),
        "-version",
        "4.0.1",
        *extra,
        "-output",
        str(outcome),
    ]
    outcome.unlink(missing_ok=True)
    proc = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if not outcome.exists():
        return {
            "label": label,
            "status": "NOT_RUN",
            "reason": (proc.stderr or proc.stdout)[-500:],
            "command": [str(c) for c in command],
        }
    issues = json.loads(outcome.read_text(encoding="utf-8")).get("issue", [])
    counts = Counter(i["severity"] for i in issues)
    return {
        "label": label,
        "status": "RUN",
        "command": [str(c) for c in command],
        "errors": counts.get("error", 0) + counts.get("fatal", 0),
        "warnings": counts.get("warning", 0),
        "information": counts.get("information", 0),
        "issues": [
            {
                "severity": i["severity"],
                "code": i.get("code"),
                "location": (i.get("expression") or [""])[0],
                "message": i.get("details", {}).get("text", ""),
            }
            for i in issues
        ],
    }


def validate(args: argparse.Namespace) -> None:
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    bundle = work / "bundle.json"
    bundle_sha = export_bundle(bundle)
    java = subprocess.run([args.java, "-version"], capture_output=True, text=True)
    oah = Path(args.oah_package)
    runs = [
        run_once("core R4 4.0.1 only (no OAH, terminology off)", args, bundle, ["-tx", "n/a"], work / "core.json"),
        run_once("core + OAH package (terminology off)", args, bundle, ["-ig", str(oah), "-tx", "n/a"], work / "oah.json"),
    ]
    if not args.no_terminology:
        label = f"core + OAH package + terminology server {TX_SERVER}"
        runs.append(run_once(label, args, bundle, ["-ig", str(oah), "-tx", TX_SERVER], work / "oah-tx.json"))
    result = {
        "recorded_on": datetime.now(UTC).date().isoformat(),
        "status": "RUN" if all(r["status"] == "RUN" for r in runs) else "PARTIAL",
        "claim": "Raw validator output for one synthetic Bundle. Not certification, not full conformance, not a clinical standard.",
        "input_bundle": {
            "sha256": bundle_sha,
            "generator": "backend/scripts/export_track7_validator_bundle.py",
            "synthetic": True,
        },
        "validator": {
            "name": "official HL7 validator_cli.jar",
            "version": args.validator_version,
            "jar_sha256": sha256(Path(args.jar)),
            "java": (java.stderr.splitlines() or ["unknown"])[0],
        },
        "fhir_version": "4.0.1",
        "oah_ig": {
            "package": "hl7.eu.fhir.oah#0.1.0-ci-build",
            "source_commit": fhir.OAH_COMMIT,
            "publication_status": "draft CI build; not an authorized publication",
            "package_origin": "built locally with SUSHI from the pinned commit; no published package exists",
            "local_package_sha256": sha256(oah),
        },
        "runs": runs,
        "unmeasured": ["Terminology validation of CLINI-CASE and OAH temporary code systems (definitions not published)"],
    }
    Path(args.result).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for run in runs:
        print(run["label"], "->", {k: run.get(k) for k in ("status", "errors", "warnings", "information")})
    print("wrote", args.result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    pkg = sub.add_parser("package")
    pkg.add_argument("--source", type=Path, required=True, help="extracted hl7-eu/oah source after `sushi .`")
    pkg.add_argument("--out", type=Path, required=True)
    val = sub.add_parser("validate")
    val.add_argument("--java", required=True)
    val.add_argument("--jar", required=True)
    val.add_argument("--oah-package", required=True)
    val.add_argument("--validator-version", default="6.10.4")
    val.add_argument("--work", default=str(BACKEND / ".cache" / "track7"))
    val.add_argument("--result", default=str(BACKEND.parent / "docs" / "track7" / "validation-result.json"))
    val.add_argument("--no-terminology", action="store_true")
    args = parser.parse_args()
    if args.command == "package":
        package(args.source, args.out)
    else:
        validate(args)


if __name__ == "__main__":
    main()
