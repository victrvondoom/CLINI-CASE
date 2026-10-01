# Track 7 demonstration

Submission entry: `/onehealth`. `/interop` demonstrates the cross-system boundary. All observations, patients, reports and consent references in this demo are **synthetic**. Persona: Mira, a community volunteer reporting a household drinking-water source. No real pilot or clinical outcome is claimed.

## Start

Prerequisites: Python 3.11+, Node 20+, Docker Desktop running, and backend dependencies installed (`backend/requirements-dev.txt`). Use the existing backend virtual environment. From the repository root:

```powershell
.\start-track7.ps1
```

This starts PostgreSQL, the application, an independent HTTP receiver with separate SQLite storage, and Vite. It generates a private reviewer account and runs the complete deterministic reference journey. Login details are saved locally in ignored `backend/.cache/track7/demo-login.json`; do not publish that file. Existing accounts are preserved. Ports 8000, 8091 and 5173 must be free. Ctrl+C stops processes owned by the launcher.

`./start-track7.ps1 -SQLite` uses durable, tenant-scoped synthetic evidence storage when Docker is unavailable; it is not a replacement clinical database. `-AI` enables real semantic suggestions through the existing governed provider and requires a working local provider credential. Deterministic mapping is labelled as rules, not AI inference. Python equivalent: `backend/.venv/Scripts/python.exe backend/scripts/track7_demo.py --keep-running --open` (run from the root).

## Four-minute story

1. Open `/onehealth`: show the unified evidence journey and six evidence gates. A photograph cannot establish arsenic concentration or a person's exposure.
2. Open `/interop`, select **Start Track 7 Interoperability Demo**. Inspect the synthetic non-FHIR JSON, discovered fields and explicit deterministic/AI/unresolved labels. Accept or reject every field; ambiguous mappings require human decisions.
3. Generate the FHIR/OAH bundle. Show measured validation, round-trip fields and the persisted Evidence Passport. Clinical consent and verification are never inherited automatically from an import.
4. Transfer to the independent receiver. Show the actual acknowledgement and returned lab representation. Receiver reads its received bundle, not CLINI-CASE application state.
5. Run the local validation failure and the receiver rejection challenge. `ppm` violates the supported quantity contract; an actual HTTP rejection is recorded. Restore/regenerate the valid bundle before transfer.
6. Bind reviewed mappings to evidence; verify the synthetic lab report, record patient consent and pathway context, and review eligibility. The journey shows OncoTwin/CardioTwin/ClinCase context without changing their scores or authorization conclusions.
7. Record a new retest sample (18.2 to 8 ug/L in the automated story). The old sample remains immutable, its environmental task closes, the successor requires fresh verification and consent history. Export the successor and show its delivered receipt and passport.

The launcher executes this story through real HTTP requests and saves `runtime-metrics.json`, `evidence-passport.json` and `retest-passport.json` in the ignored cache. An existing ClinCase case can be linked only with explicit same-organization identity attestation; the demo does not fabricate a payer case.

## Offline integrity

```powershell
cd backend
.venv\Scripts\python.exe scripts/verify_passport.py .cache/track7/evidence-passport.json
```

Recomputes every chain hash and artifact digest without the application server. Hashes detect modifications relative to the retained chain; they are not signatures or proof of laboratory truth. An attacker replacing the entire unanchored chain can forge a new chain.

## Official external validation

The tested official HL7 validator is `validator_cli.jar` version **6.10.4**, from the [official release](https://github.com/hapifhir/org.hl7.fhir.core/releases/tag/6.10.4). With Java 21, from `backend`:

```text
java -jar .cache/track7/validator_cli.jar data/interop/valid-fhir.json -version 4.0.1 -tx n/a -output .cache/track7/hl7-outcome.json
```

Actual result: **WARNING: 0 errors, 22 warnings, 7 informational messages**. Core R4 loaded; the OAH package and terminology server were not loaded. Unknown draft profiles, unpublished local terminology, missing narratives and disabled terminology checks remain gaps. This is not an OAH certification result. The checked-in outcome/summary under `backend/data/interop/validation` preserves the evidence. On this workstation, TLS inspection required importing the workstation's trusted root into a disposable Java container; certificate verification stayed enabled. Do not disable TLS to reproduce validation.

See [manual checklist](TRACK7_MANUAL_CHECKLIST.md) and [conformance statement](OAH_CONFORMANCE.md).
