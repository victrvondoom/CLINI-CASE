# Track 7 demo script (about 5 minutes)

Use synthetic fixtures only. Suggested screen: `/interop` workbench, then the Evidence Passport.
The separate-process HTTP path is reproducible with:

```powershell
python backend/scripts/track7_network_demo.py
```

For the interactive UI, start the local stack with `./start-track7.ps1 -SQLite`. That launcher
starts the API and independent receiver as separate processes and points System A at System B over
HTTP. The fast embedded-ASGI test mode is not the network demonstration.

## Run of show

- **0:00 — Problem.** “Environmental, laboratory, and health systems use different schemas and
  terminology. Moving JSON between them is not enough; meaning and evidence must survive.”
- **0:30 — Messy external JSON.** Show a synthetic lab record with a sample identifier, location,
  collection time, laboratory, analyte, value, and unit. Point out that source field names are not
  standardized concepts.
- **1:00 — Semantic mapping.** Show schema discovery and deterministic/optional AI suggestions.
  Emphasize that suggestions are constrained to supported targets.
- **1:30 — Human approval.** Approve supported mappings. Show generic `arsenic` as ambiguous and
  needing review; do not infer a chemical species from it.
- **2:00 — OAH/FHIR generation.** Generate the Bundle and identify the Location, Specimen,
  Observation and provenance/workflow context. Explain that the dissolved-arsenic code is used only
  when that qualifier is explicit and supported by the pinned guide.
- **2:30 — Validation.** Show local contract validation. Say plainly that it is not a completed
  official full OAH profile validation.
- **3:00 — Real HTTP transfer.** Show System A sending to the independent System B process at
  `127.0.0.1:8091`; name the receiver as a separate process, not an in-process mock.
- **3:30 — System B changes IDs.** Show the acknowledgement and that System B assigned new resource
  IDs and rewrote references while retaining its own received Bundle.
- **3:45 — Return Bundle.** Fetch the receiver's stored returned Bundle over HTTP.
- **4:00 — Round-trip verification.** Show semantic fields and references passing after local
  decoding; raw JSON equality is not used.
- **4:15 — Fail-closed example.** Use the intentionally unsupported `ppm` unit: the current
  application contract accepts `ug/L` or `mg/L`, so validation fails, an OperationOutcome is
  returned, and transfer is blocked. Restore a supported unit to resume the successful path.
- **4:30 — Evidence Passport.** Show mapping/reviewer, validation, transfer acknowledgement,
  hashes and round-trip result. State that all records are synthetic.
- **4:40–5:00 — Deployment portability (20 seconds).** “The workflow runs locally without cloud
  dependency. The same small container setup is Kubernetes-ready; AWS/Bedrock are optional
  deployment/provider adapters.” Do not imply EKS or a production cloud deployment.

## One-sentence close

“CLINI-CASE is a governed semantic bridge: AI may suggest mappings, a human approves them,
validation can block unsafe data, and an independent system can return the information without
relying on the original resource IDs.”
