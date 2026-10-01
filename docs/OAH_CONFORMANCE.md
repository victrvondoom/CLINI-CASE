# One-page exchange conformance statement

Target: FHIR R4 4.0.1; draft OAH `hl7.eu.fhir.oah#0.1.0-ci-build`, pinned source commit `b907cf0869b59d82d9138b3d147fca66f333d911`. Scope: **FHIR R4-targeted OAH exchange with pinned profile-aware contract checks and round-trip validation.** No certification is claimed.

| Resource | Meaning / profile | Local coverage | Round-trip |
|---|---|---|---|
| Location | Waterbody/site; selected `location-oah` constraints | name, type, references | Site / waterbody |
| Specimen | Laboratory sample; selected `specimen-oah` constraints | ID, collector, collection date, site | Native sample |
| Observation | Arsenic measurement; selected `observation-indicators-oah` constraints | final status, local analyte, quantity, UCUM contract, method, issued/effective dates, specimen/performer | Native sample |
| Organization | Laboratory | name, identity, internal performer references | Laboratory name |
| PractitionerRole | Sampling role | role, organization/collector references | Collector |
| Patient | Only applicable consented patient context | local identifier consistency | History patient ID |
| Consent | Sharing permission | status, scope, patient and native-history consistency | Consent reference/status |
| QuestionnaireResponse | Source/exposure history | required typed answers, dates, patient/source identity | Sample and history fields |
| Task | Environmental follow-up / applicable clinical review | status, intent, focus, review-state consistency | Workflow claims retained as source claims |
| Provenance | Source/transformation/reviewer history | agent, target, time, action, note | Source audit preserved |
| Practitioner | Authenticated reviewer identity | identity and agent references | Actor IDs |

All resources: R4B base models from the existing `fhir.resources` package, selected draft OAH constraints, local exchange contract, duplicate identities, closed internal references, required fields, dates, coding-system consistency and quantity units. The gateway additionally checks resource allowlist, provenance, active patient-linked consent and measured native-field round-trip. It never resolves arbitrary external references.

Local laboratory concepts remain `total_arsenic` / `inorganic_arsenic` under the repository CodeSystem; there is **no verified LOINC/SNOMED/ICD/RxNorm mapping**. UI/API expose system, code, status, source and null external-verification time. UCUM `ug/L` and `mg/L` are the supported local exchange contract; unsupported `ppm` is rejected, with no silent unit conversion.

Validation outcomes are separate: local PASS/FAIL; external HL7 validator PASS/FAIL/WARNING/NOT_TESTED. See `DEMO_RUNBOOK.md` for a pinned official validator command and `TRACK7_HARDENING_VERIFICATION.md` for actual results. Full draft package slicing, all R4 invariants and terminology-server conformance are not implied by local success. [HL7's validation guidance](https://hl7.org/fhir/R4/validation.html) explains why static validation alone does not establish complete conformance.
