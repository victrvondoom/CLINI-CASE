# Additive Track 7 implementation plan

Inspection: existing onehealth API uses reviewer/admin dependencies, tenant organization IDs, strict Pydantic models, JSONB CAS storage and synthetic-only volatile fallback. Its exporter already supplies native resources, provenance, pinned OAH checks and semantic decoding. Frontend uses authenticated fetch, Tailwind tokens and lazy routes. Existing clinical modules are left intact.

1. Add typed gateway contracts and separated source/mapping/bundle/validation/transfer/event storage following JSONB CAS conventions.
2. Discover JSON/CSV fields; reuse governed LLM abstraction for optional typed semantic suggestions. Deterministic offline mode is explicitly labelled; unknown fields remain unresolved. Review every mapping before generation.
3. Normalize only supported arsenic lab fields into LabSample; call existing FHIR export/validate/read_evidence. Preserve all source fields separately, never invent missing assay or consent information.
4. Add standalone receiver ASGI app with its own storage and HTTP adapter, validation, acknowledgement, replay and return exchange. No internal clinical state reads.
5. Add authenticated /interop UI with mapping decisions, editable bundle, validation failure, transfer, returned representation, audit and measured counters.
6. Add synthetic fixtures, adversarial tests, API golden-path test, documentation; run existing Track 7/backend/frontend checks and visual verification.
