# CLINI-CASE final publication verification — 2026-10-04

This record covers synchronization of the existing repository, preservation of prior Claude
Code/Codex edits, clinical upload/review repairs and documentation refinement. It does not
claim a new clinical architecture, a production deployment or clinical validation.

## Automated checks

| Check | Result |
|---|---|
| `python -m pytest` from backend | **756 passed, 106 deselected**; existing multipart deprecation warning |
| `python -m pytest tests/onehealth tests/interop -q` | **133 passed** |
| `python -m ruff check app tests` | Passed |
| Frontend `npm test -- --run` | **137 passed across 28 files** |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; optional Three.js chunk remains approximately 821 kB minified |
| `git diff --check` | Passed |
| README links and Mermaid | Local links checked; all eight diagrams rendered with Mermaid CLI |
| Git LFS integrity | Passed; no LFS-managed files in this checkout |

The frontend checks were repeated after browser-discovered login, proxy and drawer fixes.
Backend application code did not change after its final suite. Default pytest intentionally
excludes `integration` and `live` markers; this result is not PostgreSQL-backed or live-model
end-to-end verification.

## Independent HTTP Track 7 proof

`python backend/scripts/track7_network_demo.py --api-port 8131 --receiver-port 8132`
started separate application and System B processes. The receiver validated and stored the
FHIR Bundle, changed resource IDs and internal references, and returned it. **13/13 semantic
fields survived**. Invalid units and malformed bundles were blocked. The demonstration
recorded a valid event chain, a demo-system signature and subsequent retest exchange.

## Browser verification

The real browser used the loopback SQLite reference launcher with API **8141** and frontend
**5175**. Actual private demo login submitted successfully through the sign-in form.

The evidence journey exercised source import/schema discovery, deterministic mapping,
authenticated approval of twelve safe mappings and rejection of an unsupported field,
FHIR generation, current-bundle validation, independent HTTP delivery, returned-Bundle
verification and One Health evidence binding. The richer interactive fixture displayed
**17/17 fields preserved**, the receiver receipt and the demo Ed25519 signature.

In the bound evidence workbench, explicitly synthetic consent/history and laboratory review
were recorded. The unknown drinking pathway kept clinical review gated, as intended. A source
investigation was started and completed with a synthetic reference; missing exposure evidence
was not invented to force the clinical gate open. The independent scripted demonstration
separately exercised the new laboratory retest exchange.

**42 existing static routes** rendered meaningful content without an uncaught page exception,
Vite error overlay or route error boundary: Runtime, Journey, Interop, OneHealth, Dashboard,
Cases, bulk import, Intake, Sandbox, workflow tool pages, Oncology, OncoTwin and research/ops
pages, CardioTwin/evaluation, Policies, Agents, Cohorts, Reviewer, Compliance, ROI,
Industrialize, Architecture, Eval and the AquaHealth pages. This is route/render verification,
not proof that every backend action completed. Dynamic case pages require case data; admin
settings retain their role restriction.

`/runtime` truthfully showed a local process deployment, healthy independent receiver and
SQLite evidence mode. The SQLite launcher does not provide clinical PostgreSQL: clinical case
counts, queue/agent metrics and other database-backed views returned visible unavailable/503
responses. These are deployment limits, not hidden successful results. No live production site
or remote schema was modified during this verification.

Browser findings fixed:

- Login no longer applies a password-creation minimum length to existing valid credentials.
- Vite API and MCP proxies honor the launcher's `VITE_API_BASE` custom port.
- Evidence Drawer uses a body portal, escaping the route animation's stacking/containing
  context; its close button is now clickable above the fixed application header.
- Login footer describes the configurable provider rather than hardcoding AWS/Claude.

## NVIDIA verification

One live, patient-free synthetic connectivity request through the existing compatible client
passed against `integrate.api.nvidia.com`, model `nvidia/nemotron-3-super-120b-a12b`:
**48 input tokens, 6 output tokens**, expected connectivity response, normal stop.

The governed gateway is configured for clinical use; this probe specifically checks the
underlying provider client and does not exercise tenant audit, mapping quality or all seven
agents. No credential is written here. Full live clinical execution and accuracy remain
unverified by this publication.

## Standards evidence

The retained October 2 official-validator input hash matches its recorded result. A current
export passed local validation and reproduced that fixture's structure after generated
timestamps were normalized. Official HL7 validation was **not rerun** here. Its recorded
zero-error runs still include **21/16/15 warnings** across the three configurations. See
[the validation record](track7/VALIDATION.md); no certification or universal conformance is claimed.

## Kubernetes availability

Docker, kind and kubectl are installed, but Docker Desktop's Linux engine was stopped and
the existing kind API endpoint refused connections. `python k8s/cluster.py verify` could not
pass. The cluster was not recreated and deployment state was not mutated. The current
publication therefore includes the manifests/runbook, without claiming current live
Kubernetes health or isolation verification.

## Publication scope and remaining limits

The initial audit found 1,196 tracked files, 47 modified files and fourteen new intended files,
with no deletions. The fetched remote main matched the local starting commit. All publishable
paths were scanned for credentials and inappropriate generated artifacts; none were found.
Private environment files, credentials, local databases, logs, browser artifacts, caches,
dependencies and builds remain ignored. Later README/supporting docs and narrow browser fixes
are included in the same synchronization.

Remaining limitations are the stopped local cluster, unverified full live-model/clinical
accuracy, optional trust-store dependency when enabled, small/synthetic model evidence,
draft OAH/partial conformance and production hosting/worker/receiver capacity. Details are
visible in the README and [upload/review repair ledger](ONCOLOGY_UPLOAD_REVIEW_REPAIR.md).
