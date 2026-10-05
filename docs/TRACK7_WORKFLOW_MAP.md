# Track 7 workflow and feature map

This is the navigation and claim boundary for the OneAquaHealth Track 7 demonstration. Keep the judge-facing story centered on the governed exchange in `/interop`; supporting pages provide context or platform evidence.

## Judge-facing workflow

| Order | User task | Primary page | What can be shown | Boundary to state |
|---|---|---|---|---|
| 1 | Locate environmental observations | `/aquahealth/map` | Existing AquaHealth observations, review state, waterbody, and location context | Observation data depends on the configured database/demo seed. The globe's device location is optional and coarsened; scenario markers are synthetic. |
| 2 | Inspect contextual signals | `/oah-bridge` | Synthetic OAH scenario, geography, weather source/freshness/local time, evidence classification, FHIR resource preview, informational CDS Hooks card | This is a separate deterministic synthetic scenario. It is not imported into the `/interop` job. Weather is context, never causal proof. |
| 3 | Ingest and discover semantics | `/interop` | System A sample, deterministic mapping, optional field-name-only AI suggestions | This is the stateful Track 7 workbench. AI cannot assign analyte concepts or approve a mapping. |
| 4 | Review and standardize | `/interop` | Human mapping approval, FHIR/OAH bundle, validation and invalid-unit rejection | Pinned application checks only; not official HL7/OAH certification. |
| 5 | Exchange and prove preservation | `/interop` | Independent System B acknowledgement, returned FHIR, reassigned IDs, field-by-field round trip | Demonstration receiver and data are synthetic/local unless configured otherwise; no external partner exchange is implied. |
| 6 | Inspect retained proof and follow-up | Evidence Passport in `/interop`; `/journey/<job>`; `/onehealth` | Passport chain and job proof events; existing evidence and follow-up workbench | Hash integrity is not a lab signature, truth guarantee, or evidence of causation. Journey completion reflects proof events. |

The Interoperability area in the sidebar is the home for this sequence. The workflow strip orders the broad stages; the links within each stage are supporting tools. Oncology, OncoTwin, CardioTwin, research, and runtime remain platform capabilities and are not steps in the One Health evidence exchange.

## Extended brief: implementation status

| Requested capability | Current status |
|---|---|
| Geospatial evidence and privacy-aware location | Existing AquaHealth map plus bundled globe. User GPS is opt-in and coarsened; no device location is sent by the globe. OAH Bridge scenario locations are synthetic. |
| Weather and temporal context | OAH Bridge retrieves weather through the backend, retains source/retrieval/freshness and IANA local-time context, and labels it contextual. It is not joined into the `/interop` transaction. |
| Open street basemap | `/aquahealth/map` now offers MapLibre/OpenFreeMap tiles beside the existing 3D globe and offline plot; observation markers link to their records. |
| FHIR/OAH composition and validation | Implemented in the OAH Bridge preview and the separate Track 7 interoperability workbench. Validation is application-level and pinned. |
| HAPI FHIR REST server | The reviewer workbench can explicitly create a synthetic Bundle on HAPI and read it back. The Track 7 Compose stack has a loopback local HAPI server; the public test endpoint may retain posted data. |
| Human review, receiver acknowledgement, semantic round trip, Evidence Passport | Demonstrable in `/interop`; these capabilities are not performed by the OAH Bridge scenario explorer. |
| SMART on FHIR | Optional public-client authorization-code launch with PKCE and minimum Patient read scope is implemented at `/smart-on-fhir`. It needs EHR app registration and deployment client/redirect settings; no production EHR is registered by this code. |
| VAPID/Web Push | `/notifications` supports opt-in subscribe/unsubscribe and explicit generic test pushes. Backend VAPID and encryption secrets, HTTPS, browser permission, and persistent database are required; no automatic clinical alerts are sent. |
| Controlled public-health web intelligence and a relevance firewall | Not implemented in this extension. Do not imply that public-health articles, advisories, or web sources are ingested or relevance-scored. |
| Live web/public-health source relevance firewall; multi-agent evidence graph and conflict resolution; unified OAH Bridge passport | Not implemented or connected to the existing exchange workflow. The scenario pipeline is deterministic; do not describe it as a live multi-agent system. |
| Live surveillance, confirmed outbreak or clinical diagnosis | Not claimed. Synthetic scenarios and contextual environmental signals cannot establish these. |

## Navigation rules

- Keep `/interop` as the primary entry for the Track 7 proof.
- Link contextual pages from the stage where they help; do not add every tool as a primary sidebar destination.
- Label synthetic scenario pages and live contextual feeds separately.
- Preserve existing CLINI-CASE and AquaHealth routes; this map organizes their use without removing capabilities.
- In recordings and submissions, describe a capability only at the status shown above.
