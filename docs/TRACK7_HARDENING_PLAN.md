# Track 7 hardening inspection and implementation plan

Inspected 2026-10-01 before implementation. Target repository: victrvondoom/CLINI-CASE. Existing branch and Git history are retained.

## Architecture report

A. Existing: tenant-scoped One Health exposures, six evidence gates, explicit consent and review, AquaHealth citizen observations, OncoTwin patient context, reviewer-attested clinical cases, independent CardioTwin scenario context; gateway typed mappings, FHIR/OAH generation, HTTP receiver, CAS persistence, deterministic and optional governed AI paths.

B. Weaknesses: gateway transactions and exposure review are disconnected; no verifiable revision manifest; follow-up completion accepts a report without a linked new measurement; demo memory resets; README leads with oncology and makes an unsupported broad originality claim; historical duplicate frontends clutter the root.

C. Sufficient foundations: existing FHIR exporter/decoder/validator, exposure assessment/ablation, reviewer roles, organization scoping, clinical context panels, gateway HTTP adapter and SQLite receiver. Reuse them.

D. Must not change: clinical authorization, seven-agent pipeline, NCCN criteria, OncoTwin physiology, CardioTwin prediction/calibration, current routes and permissions, AquaHealth safety boundaries. Environment evidence is context, never a disease-model input.

E. New work: versioned hash-chain passports atomically persisted with records; offline verifier; explicit gateway-to-exposure binding; retest creates a linked unverified successor and completes the original environmental task atomically; computed epistemic ceiling; consent checks against current bound record; actual receiver rejection challenge; measured field loss report; focused simple/expert UX and documentation; reproducible demo launcher.

F. Regression risks: CAS conflicts and partial cross-record updates; stale exports after consent withdrawal; accidental import trust promotion; changed demo credentials affecting shortcuts; script moves affecting paths. Tests must cover these boundaries. Keep default existing storage behavior for compatibility; enable durable synthetic-only SQLite explicitly for a database-free demo, PostgreSQL for real records/live AI.

G. Timeline: current Git commits include Sep 30 One Health and Oct 1 gateway work. Official rules list Sep 16-30, while Devpost announces an Oct 4 extension. Record exact dates and distinguish reused platform from new additions; organizer clarification remains necessary for eligibility rather than backdating anything.

H. Standards gaps: existing R4-targeted exchange uses R4B base models plus pinned draft OAH and local checks. External HL7 validator and terminology-server results must remain distinct from local results. No certified LOINC mapping, clinical pilot or clinical validation is claimed.

## Incremental implementation

1. Add shared revision-manifest primitives and durable synthetic storage, preserving PostgreSQL CAS and atomic writes. Test tampering, restart survival and tenant isolation.
2. Bind approved gateway data to an AquaHealth observation and existing exposure workflow. Add atomic retest and computed ceiling. Export updated evidence through the same gateway.
3. Add passport export/integrity APIs, offline verification, field loss accounting and actual receiver rejection. Block stale/withdrawn exchanges.
4. Lead navigation/README with One Health. Add passport, retest and gateway links to the existing workbench; simple/expert gateway mode. Preserve all platform routes.
5. Archive tracked historical frontends; move operational scripts with path compatibility; document history, AI assistance, license restrictions, conformance, future pilot and score evidence.
6. Run existing and new backend/frontend tests, typecheck, build, lint; execute network golden path, return, rejection, passport verification and retest. Run external validator/live AI only when prerequisites exist and report actual results.

Official sources checked: [rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules), [deadline updates](https://oneaquahealth-ieee-hackathon.devpost.com/updates), [WHO arsenic](https://www.who.int/news-room/fact-sheets/detail/arsenic), [HL7 validation](https://hl7.org/fhir/R4/validation.html).
