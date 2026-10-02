# Track 7 demonstration

Submission entry: `/onehealth`. `/interop` demonstrates the cross-system boundary. All observations, patients, reports and consent references in this demo are **synthetic**. Persona: Mira, a community volunteer reporting a household drinking-water source. No real pilot or clinical outcome is claimed.

## Start

Prerequisites: Python 3.11+, Node 20+, Docker Desktop running, and backend dependencies installed (`backend/requirements-dev.txt`). Use the existing backend virtual environment. From the repository root:

```powershell
.\start-track7.ps1
```

This starts PostgreSQL, the application, an independent HTTP receiver with separate SQLite storage, and Vite. It generates a private reviewer account and runs the complete deterministic reference journey. Login details are saved locally in ignored `backend/.cache/track7/demo-login.json`; do not publish that file. Existing accounts are preserved. Ports 8000, 8091 and 5173 must be free. Ctrl+C stops processes owned by the launcher.

`./start-track7.ps1 -SQLite` uses durable, tenant-scoped synthetic evidence storage when Docker is unavailable; it is not a replacement clinical database. `-AI` enables real semantic suggestions through the existing governed provider and requires a working local provider credential. Deterministic mapping is labelled as rules, not AI inference. Python equivalent: `backend/.venv/Scripts/python.exe backend/scripts/track7_demo.py --keep-running --open` (run from the root).

For a repeatable network-only run without Docker or a frontend process, use
`python backend/scripts/track7_network_demo.py`. It starts CLINI-CASE and System B as separate local
processes, transfers and returns the generated Bundle over HTTP, and exits only after semantic
round-trip assertions pass.

## Five-minute story

| Time | Show |
|---|---|
| 0:00–0:25 | Open `/interop`. Environmental sensors, citizen observations, labs and health systems use different schemas and vocabularies. The gateway decides which mappings are supported before data crosses the boundary. |
| 0:25–0:55 | Select **arsenic | speciation unknown**, start the synthetic System A import and show schema discovery. Explain that the optional model gets field names and an allowlist only. |
| 0:55–1:45 | At the semantic safety gate, show `arsenic → value` does not establish `total_arsenic` or `inorganic_arsenic`. Human approval is required; model suggestions cannot set the analyte or approve the mapping. Optionally switch to **arsenic_dissolved** to show its source qualifier stays dissolved and does not become inorganic. |
| 1:45–2:15 | Generate the OAH/FHIR R4 collection Bundle. Show the FHIR API's `/fhir/metadata` CapabilityStatement and the selected validation result. The API stores collection Bundles; it does not execute transactions. |
| 2:15–3:05 | Change the quantity unit to `ppm`. Validation returns an OperationOutcome and transfer stays blocked. Restore `ug/L`, validate again, and transfer to the separate System B receiver. |
| 3:05–3:55 | Show the receiver acknowledgement and System B's new resource IDs. Return its FHIR Bundle to Lab A. The gateway compares sample fields, site, source identity, exposure history and provenance; IDs and package hashes differ, while semantic checks pass. |
| 3:55–4:40 | Open the Evidence Passport. Show reviewer, mapping revision, validation, transfer, acknowledgement, returned bundle hash and the round-trip field results. State that hashes show integrity against the retained chain, not a lab signature or proof of causation. |
| 4:40–5:00 | Architecture: the local demo runs with a local database and independent receiver. Containers can run on Kubernetes; EKS is optional and no cloud deployment is claimed. Bedrock is an optional model adapter. |

Optional continuation: bind the reviewed mapping to the synthetic AquaHealth observation; verify the synthetic lab report, record consent and pathway context, then create a retest. The original stays immutable and the successor requires fresh verification and consent. The comparison is a measurement change, not a clinical outcome.

### FHIR API quick reference

- `GET /fhir/metadata` — FHIR R4 CapabilityStatement; this route is public metadata.
- `POST /fhir/Bundle` — authenticated create for a validated collection Bundle, with `Content-Type: application/fhir+json`.
- `GET /fhir/Bundle/{id}` — authenticated tenant-scoped read.
- `POST /fhir/Bundle/$validate` — authenticated validation OperationOutcome. Invalid content still returns HTTP 200 as required by the FHIR operation contract.
- `POST /fhir/$validate` remains a local convenience alias; it is not advertised as a system-level FHIR operation.

The application checks are pinned, partial OAH checks, not full HL7 profile or terminology validation. An earlier core-only result (0 errors, 22 warnings and 7 informational messages) used a different saved fixture with the OAH package and terminology service absent; it is not evidence for the current bundle. This workstation currently lacks Java/the validator JAR and the pinned draft package archive. See [`track7/VALIDATION.md`](track7/VALIDATION.md) for the precise status and reproducible steps; no full OAH validation is claimed.

## Optional container and Kubernetes showcase

The normal demo launcher above is the shortest path. For the container showcase, copy `.env.example` to `.env` only if `.env` does not already exist, then start a fresh PowerShell session and provide throwaway local secrets. Do not replace or publish an existing `.env`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$env:TRACK7_POSTGRES_PASSWORD = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$env:INTEROP_RECEIVER_TOKEN = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
docker compose -f docker-compose.track7.yml up --build
```

Open `http://localhost:5173`. The API, PostgreSQL and independent receiver are available on localhost ports 8000, 15432 and the internal-only 8091 service, respectively. Stop with Ctrl+C; `docker compose -f docker-compose.track7.yml down` removes the containers but preserves the named demo data volumes. This local stack is not a production deployment.

For a local Kubernetes (kind) cluster that runs the whole application (frontend, API, the independent receiver and PostgreSQL) with Pod Security Admission, default-deny NetworkPolicies and generated secrets, use the orchestrator in [`k8s/`](../k8s/) instead of compose. It builds and loads the images, applies the manifests and can prove the Track 7 network exchange against the cluster. [KUBERNETES.md](KUBERNETES.md) has the prerequisites, security posture and troubleshooting. It is a local portability showcase, not production hardening or EKS evidence.

```powershell
python k8s/cluster.py up           # build, create the kind cluster, deploy, wait until Ready
python k8s/cluster.py verify       # health, login, Track 7 network demo, NetworkPolicy checks
python k8s/cluster.py credentials  # print the generated demo password (explicit opt-in)
python k8s/cluster.py down         # delete the cluster when the disposable showcase is done
```

The launcher executes this story through real HTTP requests and saves `runtime-metrics.json`, `evidence-passport.json` and `retest-passport.json` in the ignored cache. An existing ClinCase case can be linked only with explicit same-organization identity attestation; the demo does not fabricate a payer case.

## Offline integrity

```powershell
cd backend
.venv\Scripts\python.exe scripts/verify_passport.py .cache/track7/evidence-passport.json
```

Recomputes every chain hash and artifact digest without the application server. Hashes detect modifications relative to the retained chain; they are not signatures or proof of laboratory truth. An attacker replacing the entire unanchored chain can forge a new chain.

## Official external validation

No external validation was executed for the current generated Bundle. The earlier checked-in core-only result (validator_cli 6.10.4; 0 errors, 22 warnings and 7 informational messages) used a different fixture, omitted the OAH package, and disabled terminology. It is not a current result. This workstation has no Java runtime or validator JAR, and the pinned draft package archive is not available from the checked package endpoints. See [the dated validation record](track7/VALIDATION.md) for the exact outcome and conditional command; errors and warnings for full OAH validation are unmeasured, not zero.

See [manual checklist](TRACK7_MANUAL_CHECKLIST.md) and [conformance statement](OAH_CONFORMANCE.md).
