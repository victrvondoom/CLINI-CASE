# Track 7 conformance statement

## Purpose

This note describes the FHIR/OAH subset emitted and accepted by CLINI-CASE for the synthetic
OneAquaHealth Track 7 interoperability workflow. It records implemented mappings and validation
limits; it is not a declaration of certification or full conformance.

## Versions and supported exchange

- FHIR target: R4, version 4.0.1.
- OAH source snapshot: package `hl7.eu.fhir.oah#0.1.0-ci-build`, pinned source commit
  `b907cf0869b59d82d9138b3d147fca66f333d911`. The guide identifies this as a draft CI build,
  not an authorized publication.
- The gateway exchanges FHIR `Bundle` collections containing the supported resources actually
  used by the workflow: `Location`, `Specimen`, `Observation`, `Organization`, `PractitionerRole`,
  `Task`, `QuestionnaireResponse`, `Provenance`, `Practitioner`, and, for linked exposure history,
  `Patient` and `Consent`. This is not a general-purpose FHIR server for every resource.

## Profiles and terminology

The generated OAH profiles are:

- `http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah`
- `http://hl7.eu/fhir/ig/oah/StructureDefinition/specimen-oah`
- `http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah`

Terminology emitted by the current pathway:

- Explicitly dissolved arsenic: system
  `http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu`, code
  `arsenic-dissolved`, display `Arsenic dissolved`, as present in the pinned OAH source/value set.
  The source labels this code system temporary/experimental.
- Water specimen: SNOMED CT system `http://snomed.info/sct`, code `11713004`, display `Water`.
- Quantity units use UCUM system `http://unitsofmeasure.org`; the application contract accepts
  `ug/L` and `mg/L` for this workflow.
- Other workflow and contract codes use the CLINI-CASE local code system. They are not OAH
  terminology. Total/inorganic arsenic labels are represented as text, not as unsupported OAH
  terminology. No LOINC analyte code is emitted.

## Mapping and review workflow

The system discovers source fields and proposes deterministic/allowlisted mappings; an optional
governed AI adapter can suggest field targets but cannot assign terminology codes or certify
meaning. A reviewer must explicitly approve or reject each proposed mapping before FHIR generation.
Generic `arsenic` remains ambiguous and requires human review; it is not inferred to mean total,
inorganic, or dissolved arsenic. An explicit dissolved qualifier is coded only with the verified
pinned OAH term. No unapproved mapping can proceed to generation or transfer.

## Validation performed and not performed

Performed locally: installed FHIR R4B base-model parsing plus custom application checks for the
selected pinned OAH constraints, supported resource roles, closed references, units, provenance,
synthetic package handling, and semantic decoding/round-trip. This is custom partial contract
validation.

Not performed: complete official FHIR R4 profile validation against the OAH IG package, full
profile slicing/invariants, complete terminology validation using a terminology service, or
certification. The official HL7 validator could not be run reproducibly in the recorded environment;
see [`VALIDATION.md`](VALIDATION.md) and [`validation-result.json`](validation-result.json). The
application check is not a substitute for those checks.

## Round-trip and network interoperability

The automated exchange path compares decoded semantic fields rather than serialized JSON. The
separate-process demo starts CLINI-CASE and System B independently on localhost, sends the Bundle
over HTTP, lets System B validate/store it and replace resource IDs while rewriting references,
then returns it over HTTP. CLINI-CASE checks the returned semantic content and acknowledgement.
Resource IDs and Bundle hashes are expected to change. The embedded ASGI transport remains for fast
automated tests and is not evidence of a separate network process.

## Data limits and explicit non-claims

All demo examples are synthetic. Synthetic validation does not establish assay accuracy, laboratory
provenance, or behavior with real environmental or clinical systems. The workflow preserves
environmental/health context but makes no causal health inference.

CLINI-CASE is not clinically certified; this prototype is not a production deployment; no causal
health inference is made; and no unsupported terminology inference is made. No full FHIR/OAH
compliance claim is made.
