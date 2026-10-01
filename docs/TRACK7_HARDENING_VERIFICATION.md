# Track 7 verification — 2026-10-01

Repository: `victrvondoom/CLINI-CASE`. This report distinguishes tested behavior from remaining external requirements.

| Check | Result |
|---|---|
| OneHealth + interop tests | 67 passed, including 13 hardening tests |
| PostgreSQL restart/CAS test | 1 passed, 12 deselected; actual local PostgreSQL |
| Frontend regression tests | 23 files, 111 tests passed |
| Frontend TypeScript / production build | Passed; existing large Three.js chunk warning remains |
| Ruff app/tests/new CLIs | Passed |
| New OneHealth/interop strict types | 16 files passed with `--follow-imports=silent` |
| Existing configured models/graph type check | 12 files passed |
| Recursive strict typing of all imported modules | 75 existing errors across 11 untouched OncoTwin/AquaHealth/auth files; not claimed green |
| Browser | Front door, login, OneHealth journey, gateway resume, simple/expert controls, passport verification and receiver challenge exercised; no browser errors or blank/overlay failure observed |
| Offline passport CLI | VALID PASSPORT |
| Live semantic model | NOT VERIFIED: OpenRouter rejected configured credential; deterministic path remains available and labelled |
| Official HL7 validator 6.10.4 / core R4 | WARNING: 0 errors, 22 warnings, 7 information; terminology and OAH package NOT_TESTED |

## Actual separate-process golden path

The launcher ran application + independent receiver + PostgreSQL over explicit HTTP. Source correlation `ig-9cec8d3e91ed4e21b3391f3260db9437`; returned exchange and successor `ig-4d6958aaf5bc478ab66455fe0ccb4a65` are traceable through events. Runtime metrics are checked in under `backend/data/interop/validation/runtime-metrics.json`.

13 source fields detected; 12 mapped; all 13 decisions explicitly reviewed (one rejected); 10 FHIR resources acknowledged; 13 native fields preserved on return; sample equality true. Local validation passed all **three measured check groups**, not a fabricated number of individual HL7 invariants. The modified-unit receiver challenge returned an actual rejection. The source passport had 21 verified revisions and passed independent offline recomputation.

The imported sample was bound to an actual synthetic AquaHealth observation. Laboratory verification, consent/pathway history and human review were performed through the existing APIs. The updated evidence was transferred. A separately identified retest reduced the synthetic measurement from 18.2 to 8 ug/L (difference -10.2), reset verification/history/review, was freshly verified and consented, then delivered with its own passport. This is measurement comparison, not a clinical outcome.

## Regression and integrity coverage

New tests cover binding, evidence ceilings and ablation, real receiver rejection/rejection-log persistence, withdrawal/export/return boundaries, atomic two-record retest and stale-version rejection, four artifact-tamper cases plus offline CLI, SQLite cross-process restart/CAS and tenant isolation, PostgreSQL reconnect/CAS, source size/field/control-character limits, adversarial mapping suggestions, authorization and tenant separation. Existing gateway tests retain schema/mapping/review/FHIR validation, broken references, duplicate identities, units, consent/provenance, round-trip and retry coverage.

New frontend tests cover the actual ceiling/passport rendering, loaded connections/retest comparison, withdrawal restrictions, versioned exchange navigation, focused front door and absence of a prefilled demo password. Existing clinical frontend tests remain in the passing suite.

## Limits

Full draft OAH profile/terminology validation is incomplete. No standard terminology mapping is fabricated. Hashes are not signatures or an externally anchored ledger. Previously downloaded payloads cannot be recalled. Evidence binding spans existing AquaHealth and gateway transactions, so a crash can leave an unlinked synthetic source observation; retest succession itself is atomic. No real pilot, production-scale benchmark, eligibility guarantee or promised judge score is claimed. Manual items are listed separately in `TRACK7_MANUAL_CHECKLIST.md`.

Added/modified files: [inventory](TRACK7_CHANGED_FILES.md). New APIs and unified routes: [Track 7 guide](ONEHEALTH_TRACK7.md). Start: `./start-track7.ps1`; submission entry `/onehealth`, exchange workbench `/interop`, retained previous landing `/platform`.
