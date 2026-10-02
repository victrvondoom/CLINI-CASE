# CLINI-CASE final review — 2026-10-02

Branch: `feature/unified-journey`. Changes remain uncommitted and unpushed because the final instruction in the supplied request requires review of this report first. Existing unfinished changes were preserved and verified together with this pass.

## A. Tests and build

| Check | Result |
|---|---|
| `python -m pytest` (backend) | 682 passed, 106 deselected; one existing python-multipart deprecation warning |
| `python -m pytest tests/onehealth tests/interop -q` | Passed under the repository's default test selection |
| Passport signing tests, explicitly reported | 8 passed; original, edited content, recomputed hashes, wrong key, unsigned and HTTP verification paths |
| `npm test -- --run` (frontend) | 26 files, 128 tests passed |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; existing large Three.js chunk warning retained |
| `python -m ruff check app tests` | Passed |
| `git diff --check` | Passed; Git's LF/CRLF notices are informational |

Evidence logs and screenshots are local, ignored artifacts in the workspace and `backend/.cache/track7/`. No credentials, keys or fetched real data were added to Git.

## B. Official validator

The official HL7 validator was rerun against a freshly exported Bundle from the current implementation, using FHIR R4 4.0.1 and the locally built package from the pinned draft OAH source. The exact validated Bundle remains in `backend/.cache/track7/current-validation/bundle.json`; its SHA-256 matches the recorded input.

| Run | Errors | Warnings | Information |
|---|---:|---:|---:|
| Core R4, terminology off | 0 | 21 | 7 |
| Core + pinned OAH package, terminology off | 0 | 16 | 3 |
| Core + pinned OAH package + terminology server | 0 | 15 | 3 |

Validator: 6.10.4. OAH source: `b907cf0869b59d82d9138b3d147fca66f333d911`, package `hl7.eu.fhir.oah#0.1.0-ci-build`, built locally with SUSHI. Input SHA-256: `3e0e2260bd20ff55601d45a634a1e2b3cab5fdcaba4cbb8428259a4366978542`. Commands, artifact hashes and every issue are retained in [validation-result.json](validation-result.json); context is in [VALIDATION.md](VALIDATION.md).

This is one synthetic Bundle's validation evidence, not certification, full OAH conformance, or an approved clinical standard. Temporary/local terminology definitions and the documented warnings remain limitations.

## C. Third-party FHIR

The refreshed check against `https://hapi.fhir.org/baseR4` stored a freshly generated synthetic Bundle as `Bundle/76658` (HTTP 201), retrieved it (HTTP 200), and preserved all 5 compared semantic evidence fields. See [third-party-result.json](third-party-result.json) and [THIRD_PARTY_INTEROP.md](THIRD_PARTY_INTEROP.md). This is an additional generic FHIR path, not proof of OAH conformance. Public-server availability does not gate the local System B demo.

## D. Evidence Passport signature

Ed25519 signs the deterministic manifest payload using the persistent local demo key, with algorithm, key identifier, payload hash and signature stored in the passport. Verification uses the trusted local key and recomputes the manifest from submitted content. This pass fixed the content-only tamper case so both package integrity and signature verification fail after the measured value is edited.

Browser evidence: original passport → `Signature verified`; edited copy, measured value 18.2 → 183 → `Verification failed`, broken hash chain and invalid signature, changed artifacts named. Nothing is saved by the tamper demonstration. Recomputed-hash forgery and wrong-key rejection are covered by tests. The signer is explicitly CLINI-CASE/demo-system; no laboratory, clinician, government, legal-authenticity or third-party attestation is claimed.

## E. External environmental data

The reproducible Water Quality Portal query was refreshed and yielded 8 curated real arsenic observations for USGS station `USGS-11173200`. Source columns, original values, transformations, retrieval timestamp and provenance remain in the local output. See [DATA_SOURCES.md](DATA_SOURCES.md) and `backend/scripts/fetch_external_water_data.py`.

Raw data remains outside Git because redistribution permission for the aggregated portal source was not established. Offline tests use handwritten rows; the deterministic synthetic fixture remains the offline demo fallback. SQLite demo mode accepts synthetic evidence only; importing real evidence requires the appropriately configured non-demo gateway.

## F. Safe-mapping UX and navigation

The sidebar now has Main, Workflow and Platform areas instead of dozens of primary destinations. Contextual workspaces preserve discovery of the existing environmental, intake, safety, research and clinical tools. Oncology, OncoTwin and CardioTwin are optional Clinical Context choices. All existing route registrations remain.

Dashboard and public hero wording now represent the connected platform. Dashboard shows the six major workflow areas. Cases includes server-derived evidence-case cards with source, current stage, summary, progress, last activity and a link to the exact job/stage, while preserving clinical-case tools.

The sidebar reset was caused by the pathname-keyed outer error boundary remounting the whole shell. The boundary now resets error state without changing shell identity. Scroll, collapsed state and group preferences persist. Browser evidence: navigation to Architecture retained the exact sidebar element and scrollTop 140 → 140; back/forward also retained shell identity. Regression tests cover scroll and group state. Page scroll restores on history navigation; route content uses a restrained 160 ms animation with reduced-motion support and lazy-route loading inside the shell.

Safe approval is server-enforced and limited to deterministic allowlisted mappings. Generic arsenic and unresolved concepts stay manual. Browser flow approved 12 eligible dissolved-arsenic fixture mappings together, left `legacy_note` unresolved for an individual reject decision, and then continued through generation, exchange and verification. The ambiguous-arsenic exclusion, roles, tenancy and version handling are covered by backend/frontend tests.

## G. Demo and browser results

- Plain local SQLite launcher + independent HTTP System B: passed exchange, semantic round trip and retest. This launcher fixture preserved 13/13 fields; counts describe each actual source rather than a fixed marketing number.
- Interactive dissolved-arsenic `/journey` fixture: 17/17 semantic fields preserved after receiver IDs changed; passport verified and edited copy rejected. Ten stage links remain available; later clinical review/consent and follow-up are not falsely marked complete.
- Browser loaded Dashboard, Cases, Journey, Clinical Context, OncoTwin, CardioTwin, Oncology, AquaHealth, One Health, Interoperability, Research Lab, Observability, Runtime and Architecture without a page error boundary or captured browser errors. Contextual links return to the saved job/stage.
- Desktop and 390px mobile screenshots were visually inspected. Compact icons have accessible names/tooltips; group buttons have explicit accessible labels and expanded states; sign out remains usable when compact.
- Existing kind cluster checked read-only from its control-plane container: API, frontend, receiver and Postgres pods are Running/Ready; API, frontend and receiver deployments have 1/1 available replicas. These are existing images, not a deployment of this uncommitted frontend.
- Host kubectl has a stale certificate configuration. Verification used the cluster's own admin kubeconfig inside `clinicase-control-plane`; no TLS checks were disabled and the host configuration was not rewritten.
- Backup screen captures: `dashboard.png`, `journey-verified.png`, `passport-tamper-rejected.png`, `mobile-context.png`, `runtime.png` in ignored `backend/.cache/track7/`. Video recording was attempted but ffmpeg is unavailable; no completed four-minute submission video or 15-second Kubernetes video is claimed.

## H. Remaining limits and review items

Validator warnings and local/draft terminology limits remain. Public services can become unavailable. The demo signature is only a demo-system signature. Real-source redistribution permission is unconfirmed. SQLite does not enable persistent clinical-case linkage; PostgreSQL and applicable consent/review remain required. Existing clinical/twin capabilities retain their own evidence limitations. The build retains its optional Three.js chunk warning.

The proprietary LICENSE was not changed. Public visibility does not itself grant execution rights; the owner-specific judge authorization still needs the evidence described in [JUDGE_ACCESS.md](../JUDGE_ACCESS.md) and [LICENSE_REVIEW.md](../LICENSE_REVIEW.md).

Official hackathon rules and updates were checked live. The development-period and earlier update start dates conflict; [HACKATHON_BUILD_SCOPE.md](../HACKATHON_BUILD_SCOPE.md) conservatively uses the rules' September 16–30 period. October work is disclosed as post-period hardening, with no backdating, rewritten history or eligibility guarantee.

After review, publication should use a conventional commit on the current branch, without force-push or history changes. No commit or push has been performed in this pass.
