# CLINI-CASE demo script (about 5 minutes)

**CLINI-CASE: One Health Interoperability Gateway.** Synthetic data only.

- **Primary:** the local deterministic demo (no cloud, no public server, no Kubernetes needed).
- **Backup:** a recorded video of the same run, for a flaky network or projector.
- **Secondary:** a 15-second clip of the same application running on Kubernetes (kind). It is a deployment note,
  not the demo.

```powershell
./start-track7.ps1 -SQLite      # API, independent System B receiver and UI, as separate processes
```

Then open `/journey` and sign in with the private local login the launcher prints. The fast embedded-ASGI test mode is
not the network demonstration. The separate-process HTTP path alone is reproducible with
`python backend/scripts/track7_network_demo.py`.

## Run of show

1. **0:00 Problem.** Water-quality labs, environmental data and health systems use different schemas and terminology.
   Moving JSON between them is not enough; meaning and evidence have to survive.
2. **0:30 Real data in.** On `/journey`, import a record (the fetched Water Quality Portal rows, see
   [DATA_SOURCES.md](DATA_SOURCES.md), or the built-in synthetic lab record). The page shows ten stages and one next action.
3. **1:00 Understand and map.** Deterministic mapping first. AI is optional and constrained to supported targets; it is
   off in this run (`ai_status: deterministic_offline`).
4. **1:30 Safe mappings, human in the loop.** Review shows three groups: *safe*, *requires review*, *unresolved*.
   Click **Approve N safe mappings**: one audited batch. The generic label `arsenic` stays in *requires review*: a person
   must say total or inorganic. Do not infer a species.
5. **2:15 Standardize and validate.** Generate the OAH/FHIR R4 Bundle. Show the validation panel, then the recorded
   official validator result: **0 errors**, warnings listed in full ([VALIDATION.md](VALIDATION.md)). Say plainly: not
   certification, and the OAH guide is a draft CI build.
6. **2:45 Exchange.** System A sends to System B over HTTP. System B reassigns resource ids and returns its own copy.
7. **3:15 Verify.** Round trip: **17 of 17** semantic fields preserved for the built-in record (the count is the
   number of fields in the decoded sample, so it differs by record; meaning, not raw JSON equality).
8. **3:30 Third-party FHIR server (optional).** *Run third-party FHIR check*: a public HAPI R4 server accepts the Bundle
   and returns it ([THIRD_PARTY_INTEROP.md](THIRD_PARTY_INTEROP.md)). Say: this is generic FHIR R4 interoperability, not
   OAH conformance. If the network is down, skip it; nothing else depends on it.
9. **3:45 Evidence Passport signature.** Do this on the Verify stage **before** opening clinical context: binding evidence
   (stage 9) deliberately blocks passport export until the bundle is regenerated from the bound record. On Verify, click **Verify Passport signature**: signature verified. Click
   **Change one value, then verify**: an edited copy is rejected (hash and signature fail, the changed record is named).
   Say: this is a CLINI-CASE demo-system signature, not a laboratory, clinician, government or third-party attestation.
10. **4:15 Fail closed.** Use the unsupported unit `ppm`: validation fails, an OperationOutcome is returned and transfer is
    blocked. Restore a supported unit to continue.
11. **4:30 Context.** Consented clinical context and follow-up, if time allows. Environmental evidence never changes
    cancer authorization or twin-model inputs.
12. **4:45 Deployment (15 seconds, optional).** Show the Kubernetes clip: the same containers on a local kind cluster,
    `/runtime` showing the live topology. Do not imply EKS or a production cloud deployment.

## One-sentence close

"CLINI-CASE is a governed semantic bridge: AI may suggest, a person approves, validation can block unsafe data, an
independent system returns the information without relying on the original ids, and the evidence is tamper-evident."

## Navigation and backup

After signing in, Dashboard is the default entry. Cases shows existing clinical cases plus evidence-case cards that resume their exact journey stage. Sidebar areas expose contextual tools; Oncology, OncoTwin and CardioTwin are optional Clinical Context branches. Back to Journey returns to the last open job/stage.

Primary demo: plain local launcher with deterministic synthetic evidence. The public FHIR check is optional; failure does not stop System B. Kubernetes is a secondary topology showcase. Backup screenshots captured during this verification are in ignored `backend/.cache/track7/` (`dashboard.png`, `journey-verified.png`, `runtime.png`). Browser video recording requires ffmpeg, which is absent on this workstation; no completed submission video is claimed.
