# Track 7 validation record

Status for this verification: **local application contract tests pass; external HL7/OAH validation was not run.** No claim of full FHIR/OAH conformance or certification is made.

## Validator and target

- Intended external validator: official HL7 `validator_cli.jar`, version 6.10.4 (this version is recorded in the repository's earlier core-only validation artifact; the JAR is not present in the current environment).
- FHIR target: R4 4.0.1.
- OAH source reviewed: `hl7.eu.fhir.oah#0.1.0-ci-build`, source commit `b907cf0869b59d82d9138b3d147fca66f333d911`.
- The OAH guide identifies itself as a draft CI build, not an authorized publication. The version label is a mutable CI version; an immutable package archive plus checksum is required for reproducible full profile validation.

## Current environment result

- Attempted local check: `java -version` and `where.exe java`; neither found a Java runtime.
- `backend/.cache/track7/validator_cli.jar` is absent, and no validator JAR is checked into the repository.
- On 2026-10-01, the package endpoints `https://packages.fhir.org/hl7.eu.fhir.oah/0.1.0-ci-build`, `https://packages2.fhir.org/packages/hl7.eu.fhir.oah/0.1.0-ci-build`, and the guide site's `package.tgz` URL returned HTTP 404. The official CI HTML and the exact pinned FSH source were reachable, but that is not a validator package.
- Therefore a full OAH package validation cannot be reproduced in this local environment. The external result is **NOT RUN**, with errors and warnings **not measured** (not zero). No substitute success is inferred from the application validator.
- The pre-existing `backend/data/interop/validation/summary.json` records an older *core FHIR only* run on a different saved fixture: validator_cli 6.10.4, zero errors, 22 warnings and 7 informational messages with terminology disabled and OAH profiles unavailable. It is historical evidence only, not a result for this verification or the current generated bundle.

Machine-readable status is in [`validation-result.json`](validation-result.json). Its `null` warning/error counts mean “not measured.”

## Local application validation

This is the existing application validation path, not an HL7 validator result. It uses the installed FHIR R4B base models and explicit partial OAH/CLINI-CASE contract checks described in [OAH_CONFORMANCE.md](../OAH_CONFORMANCE.md). It does not execute all FHIR R4 profile invariants, complete slicing, or terminology-server validation.

To export a fresh synthetic Bundle after dependencies are installed:

```powershell
cd backend
python scripts/export_track7_validator_bundle.py
```

The default file is `backend/.cache/track7/oah-validation-bundle.json` (ignored). The script reports only the local application check and explicitly labels external validation `NOT_RUN_BY_THIS_SCRIPT`.

The current verification exported the synthetic bundle with SHA-256 `547a879a8f0276b500e7ffcf5b14c6add4e9bd7c769ff2ca670a4dd9a58a88f4`; local application validation passed. `python -m pytest` passed 540 tests with 105 tests deselected by the repository's default configuration; the focused One Health/interop run passed 75 tests; frontend tests passed 111 tests and the production build passed. `ruff check app tests` passed. Pytest emitted one existing Starlette multipart pending-deprecation warning. These checks do not upgrade the external validator status.

## External validator command when prerequisites exist

The current OAH CI package is not downloadable from the tested package endpoints, so the command below is a documented template only. It must not be reported as executed until an immutable package archive built from the pinned commit and its SHA-256 are available. Install Java 21 and obtain the official validator CLI 6.10.4 from the [HL7 FHIR Core release](https://github.com/hapifhir/org.hl7.fhir.core/releases/tag/6.10.4); keep both downloaded artifacts in the ignored cache.

```powershell
cd backend
python scripts/export_track7_validator_bundle.py
java -jar .cache/track7/validator_cli.jar `
  .cache/track7/oah-validation-bundle.json `
  -version 4.0.1 `
  -ig .cache/track7/hl7.eu.fhir.oah-0.1.0-ci-build.tgz `
  -tx n/a `
  -output .cache/track7/oah-validation-outcome.json
```

`-tx n/a` intentionally disables terminology-service calls; even if this command is later run successfully, terminology validation remains untested. A terminology-enabled run needs an agreed reachable terminology service and must record its version/configuration. Record the package SHA-256, validator version, exact command, and OperationOutcome counts before changing this status to `RUN`.

## Result details and limits

| Check | Result | Errors | Warnings | Notes |
|---|---|---:|---:|---|
| Local application validation and Track 7 tests | PASS (backend 540; One Health/interop 75; frontend 111) | N/A | N/A | Custom partial contract, not full profile validation |
| Official HL7 core validator on the current generated fixture | NOT RUN | Not measured | Not measured | Java and validator JAR unavailable here |
| Official HL7 validator with the OAH package | NOT RUN | Not measured | Not measured | OAH package archive unavailable from checked sources |
| OAH terminology validation | NOT RUN | Not measured | Not measured | No terminology service was used |

All input records are synthetic. Passing these checks cannot validate a real lab assay, establish unsupported arsenic speciation, prove a human-health relationship, or establish production readiness.
