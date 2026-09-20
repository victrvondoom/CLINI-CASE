# ClinCase — Backup Demo Recording Script

**Use:** Pre-record this 5-minute screen capture **before May 7**. If the live demo fails on stage, switch to this video.

**Tooling:** OBS Studio (free) at 1920×1080 60fps, .mp4 H.264. Save to `ops/demo/recordings/clincase-demo-{date}.mp4`.

---

## Pre-recording setup

- [ ] Browser at 100% zoom (no extra zoom — judges' projector will scale)
- [ ] Tab order pre-arranged: dashboard / cases / case-detail / roi / compliance / architecture / industrialize
- [ ] Backend `make backend.dev` running clean
- [ ] Frontend `make frontend.dev` running clean
- [ ] Trastuzumab APPROVE fixture pre-loaded (case_id ready to land on)
- [ ] PD-L1 DENY fixture pre-loaded (second tab; only switch if live recording goes long)
- [ ] OBS scenes: "Browser only" (clean for the demo path), "Browser + face cam" (for the open + close)
- [ ] Mic levels checked — no clipping, no static
- [ ] Background noise minimized (close window, mute notifications, AC off)

---

## Recording sequence

### Segment 1 — Cold open (0:00–0:10) — face cam

> *"Hi — I'm Preethi from Team AeroFyta. This is the live ClinCase demo, recorded at our Pune setup the day before the hackathon finals."*

Cut to browser-only mode.

### Segment 2 — Dashboard (0:10–0:25)

Tab on `/dashboard`. Pause 5 seconds on the live KPI tiles.

> *"ClinCase dashboard. Live KPI tiles — direct savings month-to-date, average decision time, annualized projection. All from `/api/v1/business-value/org` — live-introspected, not mocks."*

### Segment 3 — Case selection (0:25–0:40)

Tab on `/cases`. Click into the trastuzumab fixture case.

> *"This is a stage IIIa HER2-positive breast cancer prior auth submitted by an oncology coordinator in Aetna's network. Patient initials JD."*

### Segment 4 — Run ClinCase (0:40–2:00) ← **the longest segment, the SSE trace shines here**

Click **Run ClinCase**.

> *"Watch the right panel. Each agent reports as it runs."*

**Silence for 8 seconds.** Then narrate as agents complete:

> *"Clinical Extractor pulled HER2 IHC 3+ from the FHIR pathology resource. Policy Retriever surfaced Aetna oncology policy section 4.2. Necessity Reasoner ran four atomic criteria. Decision Composer is now writing the rationale with citations."*

When the 7-agent trace completes (~50-90s):

> *"Done. Ninety seconds. APPROVE — confidence 0.94. Five citations to specific Aetna policy sections."*

### Segment 5 — Business value (2:00–2:30)

Point at BusinessValuePanel that just rendered.

> *"$1,499.75 saved on this case. Eighteen minutes returned to the clinic. Twenty times faster than the AMA-published 18-minute median for manual oncology PA processing."*

### Segment 6 — Compliance scorecard (2:30–3:00)

Point at ComplianceScorecardCard.

> *"CMS-0057-F live scorecard. Six of six in-force clauses satisfied. Section IV.B.1 turnaround time, section IV.B.2 specific-reason notice, section IV.D auditability — all green."*

### Segment 7 — TriZetto submit (3:00–3:45)

Click **Submit to TriZetto AI Gateway**.

Wait for response.

> *"Submitted to the TriZetto AI Gateway as a Facets prior_auth_event v3 envelope and a QNXT case_event v2 envelope. Mock receiver in this dev environment, but in production this lands directly in TriZetto Facets — the platform running 80 million US healthcare member lives."*

Expand the Facets envelope JSON.

> *"Notice the SHA-256 decision hash — tamper-evident over the verdict, rationale, citations, and model ID."*

### Segment 8 — Evidence Pack (3:45–4:15)

Click **Download Evidence Pack**.

JSON file lands. Open in a JSON viewer.

> *"Auditor-grade Evidence Pack. Single JSON file with case, decision, every agent invocation, every reviewer action, the live compliance scorecard, the live business value, and the TriZetto envelope. SHA-256 over the bundle. CMS-0057-F section IV.D auditability — twelve seconds end to end."*

### Segment 9 — ROI calculator (4:15–4:45)

Tab on `/roi`. Slider already on **Humana 6M MA**.

Drag slider down to 1M then back up to 6M.

> *"Live ROI calculator. At Humana scale — six million Medicare Advantage enrollees — half a star is one-point-two-six billion dollars per year in CMS quality bonuses. ClinCase's projected lift band is plus-zero-point-two to plus-zero-point-four stars on PA-influenced measures."*

### Segment 10 — Architecture (4:45–4:55)

Tab on `/architecture`. Scroll down past the layers.

> *"Five named layers. Live-introspectable. AI velocity gap addressed, AI adaptation gap addressed, Agent Foundry stage Build, TriZetto AI Gateway native."*

### Segment 11 — Close (4:55–5:00) — face cam

Cut to face cam.

> *"That's ClinCase. Five minutes. Anything you'd like to dig into — we're in the room."*

---

## Post-recording

- [ ] Watch the full recording **at 1.5×** to catch verbal stumbles
- [ ] Trim head/tail, normalize audio
- [ ] Export at 1080p / 8 Mbps / H.264 / .mp4
- [ ] Upload to: (1) local `ops/demo/recordings/`, (2) team Google Drive, (3) team YouTube as Unlisted
- [ ] Save URL in `ops/demo/RECORDING_URLS.md` (private; not committed)
- [ ] Test playback on the venue projector format if known

---

## When to use the recording

Use the recording **immediately** if:
- Backend boot fails
- Bedrock 5xx storm (no LLM responses)
- Live agent run exceeds 2 minutes
- Frontend renders error states for `/business-value` or `/compliance`
- Browser crashes or restarts mid-pitch

**Do NOT use** the recording if:
- The live demo just runs slowly (15 sec extra is fine)
- One panel has stale data (still better than recording)
- A judge interrupts with a question (answer the question on the live screen)

When you switch to the recording: *"We had a small issue with the live LLM call — let me show you the same flow recorded yesterday."* Don't apologize. Move forward.
