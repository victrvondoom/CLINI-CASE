# Oncology upload and human review repair

Date: 2026-10-04. Scope: existing Intake, Cases, oncology review and document flows.

| Finding | Repair | Evidence | Status |
|---|---|---|---|
| Uploaded documents submitted empty FHIR Bundles | Map explicit document fields into Patient, Condition, MedicationRequest and Observation resources; send this Bundle from Intake/Cases | All four clinical demo PDFs pass the real multipart parser and agent 1 structural gate | Resolved locally |
| Missing clinical facts became fabricated defaults | Reject incomplete/conflicting documents; require patient, diagnosis, treatment and payer before saving; manual cases use entered facts | Intake/manual creation and incomplete-policy regressions | Resolved locally |
| Text-only diagnosis and biomarkers disappeared at the model boundary | Preserve screened clinical CodeableConcept text and missing-result reasons while dropping narrative/person text | Privacy regressions preserve diagnosis, HER2, stage, treatment and pending FISH | Resolved locally |
| AI DENY could become a final decision without review | Gate both synchronous and worker persistence, regardless of confidence; save an awaiting_review state without decisions or case.decided events | High-confidence DENY tested at both boundaries | Resolved locally |
| Mandatory review could hide appeal and patient letters | Finish draft generation before holding the proposed DENY; persist advisory outputs in versioned run state; label UI/PDF drafts and disable patient email/final submission | Pending readback, PDF labels and UI regressions | Resolved locally |
| Vercel lacks a persistent continuation worker | Atomically reserve the durable job and await remaining agents in the review request; explicit inline mode also works in the local demo | Human DENY, APPROVE and REFER tested through the actual resume graph | Resolved locally |
| Serverless interruption could leave letters stuck | Bound inline execution at 240 seconds; cancel model work with the request; recover only an expired current tenant-owned lease and fence previous attempts; reviewer retry button | Cancellation, deadline, active-versus-expired lease and UI retry regressions | Resolved locally |
| Old DENY drafts could appear after newer human approval | Reload only the newest run's completed job outputs; scope persisted appeal PDFs to the current run | Reviewed readback and stale-appeal regressions | Resolved locally |

Document provenance includes the uploaded byte SHA-256, source excerpts and resource references. PDF page boundaries retain blank pages; source page is unknown when an OCR adapter does not provide boundaries. No birth date, staging, LVEF, ECOG, billing code or terminology system is inferred from an absent fact. The deterministic mapper supports explicit labeled clinical documents; arbitrary narrative or an unreadable scan requires correction/manual clinical intake.

The Track 7 network demonstration was rerun using separate local HTTP processes. System B changed resource IDs/references and returned **13/13 semantic fields** intact. Unsupported units and a malformed received Bundle were rejected; Evidence Passport integrity was **CHAIN_VALID**. These are synthetic demonstration results, not clinical certification or a claim that every PDF is supported.

Verification uses offline API, agent, privacy, worker and frontend regressions, Ruff, compilation and the production frontend build. PostgreSQL/live-provider tests remain separate. The remote Supabase database, deployment environment and live Vercel site were not modified or verified by this repair. Existing workspace changes were preserved.

Final checks: **756 backend tests passed, 106 external/integration tests deselected; 137 frontend tests passed in 28 files; frontend type checking and production build passed; backend Ruff and compilation passed; `git diff --check` passed.** Existing multipart deprecation and optional large 3D bundle warnings remain non-blocking.

For judging, lead with `/journey` or `/interop`: explicit mapping, human approval, FHIR generation, validation, independent exchange and semantic round trip. Oncology PDF upload is a supporting example of converting a fragmented document into an auditable clinical Bundle. Use `demo_pdfs/01_APPROVE_breast_cancer_her2pos.pdf` first; `02_DENY_breast_cancer_lvef_low.pdf` demonstrates mandatory human review with visible draft letters. The filename is a scenario description, not a forced AI verdict.
