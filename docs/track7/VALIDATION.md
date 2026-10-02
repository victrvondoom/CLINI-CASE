# CLINI-CASE Track 7: official HL7 validator result

**Status: RUN on 2026-10-02.** The official HL7 validator was run on the Bundle the current implementation generates.
This is raw validator output for one synthetic Bundle. It is **not certification**, not a claim of full FHIR/OAH
conformance, and the OneAquaHealth (OAH) guide is a **draft CI build**, not an approved clinical standard.
Machine-readable record (every issue, nothing suppressed): [`validation-result.json`](validation-result.json).

## What was validated

| Item | Value |
|---|---|
| Input | Synthetic Bundle exported from the current code by `backend/scripts/export_track7_validator_bundle.py` |
| Input SHA-256 | `3e0e2260bd20ff55601d45a634a1e2b3cab5fdcaba4cbb8428259a4366978542` |
| Validator | official HL7 `validator_cli.jar` **6.10.4** (GitHub release, SHA-256 `1106b9d5...653cc`, matches the release's published digest) |
| Java | Temurin OpenJDK 21.0.12.1 (portable, checksum-verified; no system install) |
| FHIR version | R4 **4.0.1** |
| OAH IG | `hl7.eu.fhir.oah#0.1.0-ci-build`, source commit `b907cf0869b59d82d9138b3d147fca66f333d911` |
| OAH package | **Built locally** with SUSHI 3.x from that exact commit (see below); SHA-256 `9010a86f5c83db419d89179b0f439c4558b785878bc05361e202021073412e65` |

## Result (real counts, three runs)

| Run | Errors | Warnings | Information |
|---|---:|---:|---:|
| Core R4 4.0.1 only (no OAH, terminology off) | **0** | 21 | 7 |
| Core + OAH package (terminology off) | **0** | 16 | 3 |
| Core + OAH package + terminology server `https://tx.fhir.org/r4` | **0** | 15 | 3 |

The OAH profiles (`location-oah`, `specimen-oah`, `observation-indicators-oah`) load and are applied; no profile
constraint produced an error. The run with the OAH package removes the "profile definition not found" findings of the core-only run.

## What the remaining warnings say (not hidden, not fixed here)

| Count | Finding | Meaning |
|---:|---|---|
| 10 | `dom-6`: resource should have narrative | FHIR best-practice recommendation; the generated resources carry no human-readable `text` |
| 2 + 2 | CLINI-CASE code system `.../CodeSystem/one-health` has no published definition | Our local codes cannot be checked against a published CodeSystem |
| 1 | Location `type` has no code from `ServiceDeliveryLocationRole` | The sample site's `type` is text-only |
| 1 | Provenance `reason` has no code from `PurposeOfUse` | Reason is free text |
| 1 | Provenance `activity` codes are not in `provenance-activity-type` | Local activity codes |
| 1 | UCUM unit `ug/L` not verified | Only without a terminology server; verified when the server is used |
| 1 | OAH temporary code system `temporarySystem-oah-eu` not found (core-only run) | Resolved only where the OAH package is loaded; the OAH guide marks it temporary |
| 1 (info) | No Questionnaire identified for the exposure-history `QuestionnaireResponse` | Not validated against a questionnaire |

These are real findings about the current output. None is an error; several are cheap follow-ups (narrative text, published code-system definition).

## Reproduce

```powershell
# 1. Tooling (official sources; verify the SHA-256 values shown by each release page)
#    validator_cli.jar 6.10.4: https://github.com/hapifhir/org.hl7.fhir.core/releases/tag/6.10.4
#    Java 21 JRE (e.g. Temurin) any recent build
# 2. Build the OAH package from the pinned commit (no published package exists; see below)
git clone https://github.com/hl7-eu/oah; cd oah; git checkout b907cf0869b59d82d9138b3d147fca66f333d911
npx fsh-sushi .            # 0 errors, 7 profiles, 11 value sets, 1 code system
cd ../backend
python scripts/hl7_validate.py package --source ../oah --out oah-0.1.0-ci-build.local.tgz
# 3. Validate the CURRENT bundle and rewrite validation-result.json
python scripts/hl7_validate.py validate --java <java> --jar validator_cli.jar --oah-package oah-0.1.0-ci-build.local.tgz
```

On Windows behind a TLS-inspecting antivirus, the script passes `-Djavax.net.ssl.trustStoreType=Windows-ROOT` so Java trusts the machine store.

## Why the OAH package is built locally

On 2026-10-02 the package endpoints (`packages.fhir.org`, `packages2.fhir.org`, `build.fhir.org/ig/hl7-eu/oah/package.tgz`,
`hl7.eu/fhir/ig/oah/package.tgz`) all returned HTTP 404, and the `hl7-eu/oah` repository has one branch (`master`) and no releases.
SUSHI compiled the pinned source with 0 errors. The package contains only SUSHI's conformance resources (profiles, extensions, logical
models, value sets, code system; no examples). It is **not the IG Publisher's output**: it has no pre-generated snapshots (the validator
generates them) and no rendered pages. Treat it as a faithful build of the pinned source, not as the official artifact.

## What this does and does not show

- **Shows:** the generated Bundle parses as R4 4.0.1, has no validator-reported errors against core R4 or the locally built OAH profiles, and the
  validator's remaining notes are listed above.
- **Does not show:** conformance certification; any assay or lab truth; terminology correctness of CLINI-CASE or OAH temporary codes; behavior
  for non-synthetic data. All inputs are synthetic.

## Application-level checks (separate from the validator)

`python -m pytest` runs the application's own contract validation (FHIR R4B base models plus selected pinned OAH constraints, see
[OAH_CONFORMANCE.md](../OAH_CONFORMANCE.md)). That is partial contract validation, not the HL7 validator.
