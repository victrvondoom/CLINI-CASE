# Track 7 OAH/FHIR conformance note

Target: FHIR R4 4.0.1. The source snapshot reviewed is the OneAquaHealth repository at commit `b907cf0869b59d82d9138b3d147fca66f333d911`, whose `sushi-config.yaml` identifies package `hl7.eu.fhir.oah#0.1.0-ci-build` and FHIR 4.0.1. The official site identifies this as a draft continuous build, not an authorized publication. This is source-level mapping verification, not certification.

## OAH artifacts emitted

| Resource | Exact canonical / terminology | What the pinned source supports | CLINI-CASE output |
|---|---|---|---|
| Location | `http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah` | `identifier` and `name` required; `mode` fixed to `instance`; optional coordinates must include longitude and latitude. `type` has no OAH-specific terminology binding. | Both site and waterbody carry the profile, business identifiers, name and instance mode. Environmental kind is text only; it is not falsely coded as a FHIR service-delivery location role. |
| Specimen | `http://hl7.eu/fhir/ig/oah/StructureDefinition/specimen-oah` | `subject` is required and constrained to `LocationOah`; `collection`, `collector` (PractitionerRole) and `collected[x]` (dateTime) are required; bodySite is prohibited. `type` has an extensible binding to the OAH specimen type value set. | Site relationship, collector role and collection time are present; bodySite is absent. Water specimen is coded `http://snomed.info/sct#11713004` (`Water`) and retains text `Water sample`. |
| Observation | `http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah` | `status` fixed to `final`; `code` required with a preferred binding to `http://hl7.eu/fhir/ig/oah/ValueSet/oah-indicators-no-health-oah-vs`; `subject` is required `LocationOah`; specimen references `SpecimenOah`; effective time and performer are required; value is CodeableConcept or Quantity. | The emitted observation has these elements and its location/specimen references resolve. Explicit dissolved arsenic uses the verified OAH code below. Other arsenic concepts remain text-only rather than receiving invented OAH codes. |

Verified observation terminology at the pinned commit:

- CodeSystem canonical: `http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu` (the guide labels this system temporary and experimental).
- Exact supported concept: code `arsenic-dissolved`, display `Arsenic dissolved`; it is included by the OAH Indicators (Non-Health) value set.
- The pinned code-system source contains no `total-arsenic`, `arsenic-total`, `arsenic-inorganic`, or equivalent inorganic/total arsenic concept. Generic `arsenic` therefore remains ambiguous. Total/inorganic are represented only as CLINI-CASE local text concepts; neither is presented as an OAH coding or verified terminology mapping.
- No LOINC or SNOMED code is asserted for arsenic. The one SNOMED code emitted is the OAH specimen-type example `11713004` (`Water`), not an analyte mapping.

Workflow, exchange-contract and synthetic-classification tags elsewhere in the Bundle use the repository's CLINI-CASE local contract system. Those local values are not OAH terminology and do not become verified merely because they appear in a FHIR resource. External receivers need an agreed local contract for them.

## What local validation means

The current application check uses the installed `fhir.resources` R4B models plus explicit CLINI-CASE checks for the pinned OAH constraints above, unique semantic roles, closed references, supported resource types, quantity contract (`ug/L` or `mg/L`), provenance, and normalized semantic round-trip. It is a custom partial contract check, not full FHIR R4 profile validation. It does not perform complete profile slicing/invariant evaluation or validate all terminology in a terminology service. A passing application result is not proof of OAH conformance or certification.

All demo records and examples are synthetic. Human mapping approval confirms only the selected mapping decision; it does not verify a laboratory assay, establish chemical speciation not present in the source, establish health causation, or constitute patient consent. The exchange is not a production clinical-data service.

See [the validator status and reproduction details](track7/VALIDATION.md) for the external HL7 validator result and current limitations.
