# CLINI-CASE — full demo recording script

Spoken narration is in **Say**. What to click is in **Do**. What to point at is in **Show**.
All data in the demo is synthetic. Say so once at the start and once at the end; it is the honest framing and judges respect it.

Live app: https://clini-case.onrender.com · Source: https://github.com/victrvondoom/CLINI-CASE

## Judge-first Track 7 path (5 minutes)

Keep the central story on one path: **evidence context → semantic safety → human approval → FHIR/OAH validation → independent exchange → round-trip proof → Evidence Passport**. The sidebar's **Interoperability** area is the home for this path; related tools are links from that area rather than extra primary destinations.

For the precise route-to-requirement map and current implementation boundaries, see [Track 7 workflow map](TRACK7_WORKFLOW_MAP.md).

Optional connected-service setup is documented in [Service integrations](SERVICE_INTEGRATIONS.md).

1. **0:00–0:25 — `/track7`.** State the problem, synthetic-data boundary, and no-causality claim.
2. **0:25–1:00 — `/aquahealth/map`.** Show recorded observation locations. Use **Context explorer** only if time allows.
3. **1:00–1:35 — `/oah-bridge`.** Select one scenario; show location, dated weather context, evidence class, and FHIR resource preview. Say: “This is a separate synthetic context scenario; it is not imported into the exchange job.”
4. **1:35–4:35 — `/interop`.** Select ambiguous arsenic; start the job; show deterministic mapping, human semantic review, FHIR/OAH generation, break validation with `ppm`, restore `ug/L`, transfer to System B, return, and field-level round-trip proof. Keep this as the main demonstration.
5. **4:35–5:00 — Evidence Passport / `/journey/<job>`.** Show the retained proof chain and close with the limits: synthetic data, application-level pinned checks, no official HL7/OAH certification, no causal or diagnostic claim.

**Keep the handoff honest:** `/oah-bridge` provides scenario context and a FHIR preview; `/interop` is the stateful, human-reviewed exchange and round-trip. The two scenario datasets are not currently connected by an import action. Do not imply that the explorer's preview was the bundle transferred in the workbench.

The remainder of this document is an optional broader platform tour. It is not the Track 7 judge path. Keep Oncology, OncoTwin, CardioTwin, ROI, and runtime pages after the interoperability proof, and shorten or omit them when the judging slot is limited.

## Before you press record

1. **Wake the server.** The free instance sleeps. Open https://clini-case.onrender.com/api/v1/healthz about a minute before recording, so the first page isn't slow.
2. **Attach the database first (important).** Pages that save or list data — new observations, cases, accounts, policies — need `DATABASE_URL` set in Render. Without it they show empty states or errors. Either add it, or record locally with `./start-track7.ps1 -SQLite`.
3. **AI features need `OPENROUTER_API_KEY`.** Without it, say "deterministic mode" and show the rules-based path; do not claim live AI suggestions.
4. Browser at 1920×1080, zoom 100%, bookmarks bar hidden, light theme (toggle top-right on the login page).
5. Open the app in a fresh private window so there is no stale session.
6. Run time: about 27 minutes for the optional full-platform tour. Use the **Judge-first Track 7 path** below for a focused 5-minute submission recording.

---

## Section 1 — Opening (0:00–1:30)

**Do:** open `/` (landing page). Slowly scroll once, then stop at the top.
**Say:** "Environmental sensors, community reports, laboratories and hospitals all describe the same reality with different fields, units and vocabularies. CLINI-CASE is a One Health interoperability gateway: it makes those differences visible, requires a human to approve any interpretation, produces a standards-based exchange, and then proves another system kept the meaning. Everything you see today is synthetic data; no real patient or pilot is claimed."

**Do:** open `/track7`.
**Say:** "This is our submission for OneAquaHealth Track 7, Digital Health Standards. The central claim: heterogeneous environmental, laboratory and health data can become a governed standards-based exchange without AI silently inventing clinical meaning."
**Show:** the headline claim and the clinical-boundary note. **Say:** "We do not claim an environmental measurement caused a specific disease. We preserve the evidence chain for human review."

## Section 2 — Sign in, no password (1:30–2:15)

**Do:** open `/login`. Point at the theme toggle (top right), then the three demo accounts.
**Say:** "Three roles. Admin has full access. Reviewer does evidence review. Coordinator creates observations and cases. For this demo each is one click, no password."
**Do:** click **Reviewer**. You land on the dashboard.
**Say:** "Role-based access is real: later I'll show the admin-only settings page."
*Optional:* sign out, click **Create one** to show `/signup` exists, then return. Only do this if the database is attached, otherwise sign-up shows a clear "database not connected" message.

## Section 3 — The core: Track 7 interoperability (2:15–9:00)

### 3a. `/onehealth` — the submission entry (2:15–3:15)
**Do:** open `/onehealth`.
**Say:** "This is the One Health home. Persona: Mira, a community volunteer reporting a household drinking-water source. Her observation and a laboratory result are different systems' views of the same water."
**Show:** the "New laboratory evidence" section and the linked evidence list. **Say:** "Evidence arrives from several sources and is bound to one traceable record."

### 3b. `/interop` — the five-step gateway (3:15–8:15)
**Do:** open `/interop`. Work down the numbered panels.

1. **Source Data | System A.** Select the **arsenic | speciation unknown** sample. **Say:** "System A says only 'arsenic' with a value. It does not say total arsenic or inorganic arsenic. That difference matters medically."
2. **AI Mapping / Schema Discovery.** Start the import. **Say:** "Schema discovery reads field names. If a model is enabled it sees field names and an allowlist only — never patient data. Deterministic rules run first and are labelled as rules, not AI."
3. **Human Review.** Open the semantic safety gate. **Say:** "Here's the safety point. `arsenic → value` does not establish `total_arsenic` or `inorganic_arsenic`. A model suggestion cannot set the analyte or approve the mapping. A human must." Approve as the reviewer. *Optional:* switch to **arsenic_dissolved** and say "its qualifier stays dissolved; it never silently becomes inorganic."
4. **FHIR/OAH Bundle.** Generate the bundle. **Say:** "A FHIR R4 collection Bundle following the One Health data profile draft." Open `/fhir/metadata` in a new tab briefly: "the public CapabilityStatement; the API stores collection bundles and does not execute transactions."
5. **Validation / Break It.** Change the quantity unit to `ppm`. **Say:** "Watch: validation returns an OperationOutcome and the transfer is blocked." Restore `ug/L`, validate again, then **transfer to System B**.
   **Say:** "Honest scope: these are our pinned, partial profile checks, not full HL7 terminology validation."

**Do (continue on the same page):** show the receiver acknowledgement and System B's **new resource IDs**, then return the bundle to Lab A.
**Say:** "System B is a separate process with separate storage. IDs and package hashes differ, but the gateway compares sample fields, site, source identity, exposure history and provenance — and the semantic checks pass. That is the round-trip proof."

### 3c. Evidence Passport (8:15–9:00)
**Do:** open the Evidence Passport from the page.
**Show:** reviewer, mapping revision, validation, transfer, acknowledgement, returned-bundle hash, field results.
**Say:** "Hashes show integrity against the retained chain. They are not a laboratory signature and not proof of causation."

## Section 4 — The unified journey (9:00–11:30)

**Do:** open `/journey` (the "One Health Interoperability Gateway" page).
**Say:** "Everything we just did, as one connected journey: intake, understand, map, review, standardize, validate, exchange, round-trip, then clinical context and follow-up."
**Do:** click a recent job to open `/journey/<job>`, then click individual stages. **Show:** each stage cites its own proof events and status is a read-only server projection. **Say:** "Stages can't be marked done by clicking; they complete only when the proof event exists."
**Do:** use the sidebar to touch the workflow areas: **Intake tools**, **Evidence**, **Review**, **Clinical context**, **Follow-up**, **Research**. **Say:** "Same data, organised by what you're doing."

## Section 5 — AquaHealth (11:30–15:00)

Say first: "AquaHealth is the community side: freshwater observation turned into evidence."

| Page | Do | Say |
|---|---|---|
| `/aquahealth` | Show the overview. Point at ecosystem status, data confidence, data sources. | "Status plus a confidence rating — it tells you how sure the assessment is, not just what it is." |
| `/aquahealth/observations/new` | Walk the form: **Where**, **Which water did you look at?**, **When**. Use Yes / Not sure / Skip answers. Submit. | "A volunteer records what they actually saw. 'Not sure' and 'Skip' are first-class answers — we never force a guess." |
| `/aquahealth/observations` | Filter by **Pending review**, then open one. | "Every observation has a review state: pending, in review, reviewed." |
| `/aquahealth/observations/<id>` | Show detail and its evidence. | "One observation, its provenance, its review decision." |
| `/aquahealth/map` | Show observation locations and waterbodies. | "Where the evidence is coming from." |
| `/aquahealth/trends` | Show adverse signals per visit, biodiversity groups, dissolved oxygen. | "Trends only from visits where a measurement was actually supplied." |
| `/aquahealth/one-health` | Show ecosystem, animals and communities; note "No potential pathways identified" if shown. | "Pathways are listed only when evidence supports them; an empty state is a valid answer." |
| `/aquahealth/community` | Show your contribution and badges. | "Contribution feedback keeps volunteers engaged." |
| `/aquahealth/evaluation` | Read the **What this benchmark establishes** and **Limitations** headings. | "We publish limitations next to results." |

## Section 6 — Oncology prior-authorisation (15:00–19:00)

Say first: "The same platform carries a clinical use: prior authorisation for oncology, with a seven-agent pipeline and mandatory human review."

| Page | Do | Say |
|---|---|---|
| `/dashboard` | Show KPIs. | "Operational view for the coordinator and reviewer." |
| `/intake` | Start a case with a synthetic document (sample PDFs are in `demo_pdfs/`). | "Documents become structured clinical facts; PHI sanitising happens first." |
| `/cases` | Show the list and status chips. | "Each case has a turnaround clock tied to the CMS-0057-F timelines." |
| `/cases/<id>` | Open one. Show the verdict, rationale, citations, appeal letter editor, documentation-gap panel. | "Verdict, reasoning and the policy citation behind it — and the human can edit the appeal letter." |
| `/cases/<id>/compare` | Open Compare. | "How each payer's policy and decision differ for the same case." |
| `/cases/bulk-import` | Show the page. | "Batch intake for a backlog." |
| `/sandbox` | Run a scenario. | "A what-if sandbox. Read the on-page note: verdicts here are a documentation heuristic, not the agent pipeline." |
| `/policies` | Show the policy library and a `/policies/<id>/diff`. | "Policy versions and exactly what changed between them." |
| `/agents` | Switch the 24 h / 7 d / 30 d range. | "Per-agent performance and latency." |
| `/cohorts` | Switch 30 days / 90 days / 1 year. | "Approval rate by payer, time-to-decision, verdict mix." |
| `/onco` | Scroll the capability cards: OncoGuideline Engine, Genomic Authorization, Denial Predict + Auto-Appeal, CMS-0057-F compliance, Peer-to-Peer briefing kit, Off-label justification, Bundled regimen. | "Each card is a distinct capability on one shared evidence base." |

## Section 7 — OncoTwin digital twin (19:00–22:00)

| Page | Do | Say |
|---|---|---|
| `/twin` | Show the command view. | "A patient's digital twin, built from deterministic models — no database or LLM key needed for the twin itself." |
| `/twin/overview` | Read the "ClinCase is extended, not replaced" heading. | "The twin sits on top of the authorisation workflow; it doesn't replace it." |
| `/twin/demo` | Click through the tabs: **Living twin**, **Trajectory**, **What-if**, **Evidence**, **ClinCase**. | "Living twin: the patient as the system understands them today. Trajectory: where they're heading. What-if: change a treatment and see the modelled effect. Evidence: every number traces to a source. ClinCase: links back to the authorisation case." |
| `/twin/lab` | Show the ablation and early-warning charts. | "We remove one data type at a time to show what each contributes, and compare against simpler baselines." |
| `/twin/ops` | Show latency, the stress test, and the model-purpose table. | "Operational health and a stress test: does the twin fail safe?" |

Say: "The twin explains and supports; it does not diagnose or decide."

## Section 8 — CardioTwin (22:00–23:00)

**Do:** open `/cardiotwin`, then `/cardiotwin/evaluation`.
**Say:** "The same twin pattern applied to cardiology." **Show:** calibration comparison, model comparison, leakage audit, hierarchical consistency. **Say:** "We publish a leakage audit — evidence the results are not inflated by test-set contamination."

## Section 9 — Governance, proof and platform (23:00–26:00)

| Page | Do | Say |
|---|---|---|
| `/compliance` | Show the compliance view; mention print → Save as PDF. | "An exportable compliance record." |
| `/eval` | Show confusion matrix, per-payer accuracy, disagreement taxonomy. | "Measured accuracy, with how and where it disagrees." |
| `/roi` | Pick a payer scenario preset. | "A cost model with named scenarios; treat as illustrative." |
| `/architecture` | Show KPIs and platform alignment. | "How the pieces fit." |
| `/industrialize` | Show CI pipeline, gated production deploy, SLOs, runbook, tenant onboarding. | "It's built to be operated, not just demoed." |
| `/runtime` | Show deployment topology. | "This page reflects the actual running topology: containers locally, Kubernetes-ready. We make no EKS claim." |
| `/settings` | Sign in as **Admin** first. Show users and organisation details. | "Admin-only user management — this is where role separation shows." |

## Closing (26:00–27:00)

**Do:** return to `/`.
**Say:** "To recap: heterogeneous environmental, laboratory and clinical data goes in; a human approves every interpretation; a standards-based exchange comes out; and a second system proves the meaning survived. AI helps, but never decides. Everything is open source on GitHub, deployed from the repository, and every claim is paired with its limit. Thank you."

---

## Cheat sheet — do not say these

- Do **not** say "validated against official HL7/OAH" — only partial pinned checks ran.
- Do **not** say "AI-powered mapping" unless a provider key is set; say "rules first, optional AI suggestions."
- Do **not** say the hash chain is a "signature" or proves lab truth.
- Do **not** say it caused a disease, or that it is deployed on AWS/EKS.
- Do say "synthetic", "human review required", and "demo workspace".

## If something goes wrong on camera

| Symptom | Likely cause | Fix |
|---|---|---|
| First page takes ~50 s | Free instance was asleep | Pre-warm with the healthz URL |
| Empty lists, save fails | No `DATABASE_URL` | Attach it in Render → Environment |
| "Account creation needs the database" | Same | Same |
| AI step returns nothing | No `OPENROUTER_API_KEY` | Add it, or narrate the deterministic path |
| Demo button says "off on this server" | `DEMO_PASSWORDLESS_LOGIN` unset | Set it to `true` in Render |
