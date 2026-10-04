# One CLINI-CASE evidence journey

CLINI-CASE presents **one user-facing journey** instead of separate products. Oncology, the Track 7
gateway, One Health, AquaHealth, OncoTwin and CardioTwin all remain intact; the journey is an
orchestration and presentation layer that drives them through their **existing APIs**.

```
INGEST → UNDERSTAND → MAP → REVIEW → STANDARDIZE → VALIDATE → EXCHANGE → VERIFY → CLINICAL CONTEXT → FOLLOW-UP
```

## Design

| Concern | How it works |
|---|---|
| State | `GET /api/v1/journey/{job_id}` is a **read-only server projection** (`backend/app/journey/projection.py`) of the persisted interop job, its bound One Health evidence record, that record's consented connections, and the Evidence Passport integrity check. Nothing is stored twice; the browser keeps only the job id in the URL. |
| Proof | Every completed stage cites the **logged event that proves it** (event type, time, actor, correlation id) from the job's own event log. The UI's "View details · N proof" drawer shows it. |
| Actions | Buttons call the **existing** `/api/v1/interop/*` endpoints with `expected_version`. The server enforces roles, tenancy, consent and every workflow rule; the journey then re-reads the projection, so it can never show progress the backend has not recorded. |
| Concurrency | A stale version returns HTTP 409 from the gateway. The journey shows the server's message, reloads the current state and lets the reviewer retry; nothing is silently overwritten. |
| Next action | Each stage exposes at most one *legal* next action, mirroring backend rules (e.g. transfer only after the exact generated bundle validated). |
| Recovery | A transfer persisted as `processing` with no outcome (interrupted) is shown as retryable, not complete. Validation of an edited challenge payload asks for re-validation of the generated bundle rather than reporting a failure. |
| Access | Same as the gateway: reviewer or admin, tenant-scoped. Other organisations get 404; coordinators get 403 with guidance. |

## Stages and the capabilities that power them

| # | Stage | Existing capability / API | Complete when (proof event) |
|---|---|---|---|
| 1 | Ingest | Track 7 gateway `POST /interop/demo`, `/import` (JSON, CSV, FHIR) or `/from-evidence` | job exists (`source_received` / `reviewed_evidence_exchange_created`) |
| 2 | Understand | gateway schema discovery (runs at ingest) | fields detected (`schema_discovered`) |
| 3 | Map | `POST /interop/map` — deterministic, or governed AI suggestions behind the semantic firewall | mappings proposed (`mappings_proposed`) |
| 4 | Review | `POST /interop/mappings/{id}/approve|reject` — human review gate; generic "arsenic" needs an explicit total/inorganic decision | no pending decisions and no required target missing (`mapping_accepted` / `mapping_rejected`) |
| 5 | Standardize | `POST /interop/generate-fhir` — OAH/FHIR R4 collection Bundle | bundle present (`bundle_generated`) |
| 6 | Validate | gateway exchange-contract validation (`/interop/validate`) | the validation covers the current bundle digest and passed (`validation_passed`) |
| 7 | Exchange | `POST /interop/transfer` — independent System B over HTTP | delivered transfer of the current bundle (`transfer_delivered`) |
| 8 | Verify | `POST /interop/return` — semantic round trip after System B reassigns IDs; Evidence Passport hash chain | round trip passed and passport chain valid (`return_exchange_validated`) |
| 9 | Clinical context | `POST /interop/bind-evidence` → One Health evidence record → `GET /onehealth/exposures/{id}/journey` (AquaHealth observation, evidence review, gateway, and consent-gated OncoTwin / CardioTwin / ClinCase case links) | consent recorded (`onehealth_evidence_bound`) |
| 10 | Follow-up | One Health follow-up and laboratory retest (`/onehealth/exposures/{id}/followup`, `/retest`) in the evidence workbench | follow-up completed or retest linked |

The round-trip count is whatever the backend measured for that record. The built-in interactive
fixture includes 17 semantic fields (13 laboratory sample fields plus waterbody, source observation
id, exposure history and provenance); the separate-process network fixture reports 13/13. These
are fixture-specific evidence counts, not model-accuracy scores. The UI never hard-codes the count.

## Routes

| Route | Purpose |
|---|---|
| `/journey` | Start a journey (synthetic dissolved or generic-arsenic laboratory export, or import a JSON record) and resume recent journeys |
| `/journey/:jobId` | Redirects to the stage that needs work next |
| `/journey/:jobId/:stageId` | One stage: status, summary, facts, proof, next legal action, details drawer |
| `/runtime` | Deployment topology of the whole application |

Every pre-existing route is preserved (a frontend test asserts the full route inventory). The
gateway workbench (`/interop`) and evidence workbench (`/onehealth`) offer **Continue in unified
journey**; the journey links back to them for advanced operations such as the receiver challenge,
consent capture and retest forms. After sign-in, Dashboard is the default entry; its workflow
navigation opens `/journey`, and evidence-case cards resume the saved job/stage.

## Golden-path demo (about 4 minutes)

1. Sign in as a reviewer → **Evidence journey** → choose *Dissolved arsenic laboratory export* → **Start evidence journey**.
2. **Map** → *Propose mappings*.
3. **Review** → *Review mappings*: approve each proposed target, reject the unresolved `legacy_note`.
4. **Standardize** → *Generate OAH/FHIR bundle* (validation runs with it).
5. **Exchange** → *Send to System B*.
6. **Verify** → *Return and verify round trip*: all semantic fields preserved, resource IDs reassigned, passport chain valid; *Export Evidence Passport*.
7. **Clinical context** → *Bind to One Health evidence*: three capabilities open immediately; patient-linked OncoTwin, CardioTwin and ClinCase links stay closed until consent is recorded in the evidence workbench.
8. **Follow-up** → record the environmental follow-up or a laboratory retest in the evidence workbench.
9. Open **Runtime** to show the same application running as containers on kind.

The generic-arsenic variant demonstrates the semantic firewall: approval is refused until a reviewer
explicitly confirms total or inorganic arsenic.

## Runtime view

`GET /api/v1/runtime` reports only real data: the process environment (including the Kubernetes
Downward API identity injected by `k8s/`), server configuration, the live route table, and live probes
of **server-configured** endpoints (the receiver's `/healthz`, the frontend's `/healthz`, `SELECT 1` on
PostgreSQL, Redis `PING` when configured). Client input never chooses a probe target, credentials are
never returned, and probe failures are reported as fixed categories. The page is titled
**Live cluster topology** only when the API runs in Kubernetes; otherwise **Deployment topology**. No CPU,
memory, replica or cloud metrics are shown.

## Limitations

- The journey starts at the interoperability gateway. Oncology prior-authorization cases (the 7-agent
  pipeline) appear as clinical context only through the evidence record's **consented** case link; no
  environmental record is linked to a clinical case without that explicit, consented binding.
- Laboratory verification, consent capture and retest forms remain in the evidence workbench; the
  journey shows their state and links there.
- Validation is partial contract validation, not HL7/OAH certification (see the validation record).
