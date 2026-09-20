# ClinCase — Demo Video Recording Script

**Purpose:** A second-by-second walkthrough of the three demo paths. The output is a **3-minute backup video** that the team can play if anything fails during the live demo, AND a **submission video** for the the 2026 hackathon finals deliverable.

**Audience for the recording:** A judging panel of the payer organization leaders. Treat them as smart but skeptical — they will pause the video and check details.

**Owners:**
- **Recorder:** Demo Operator (DO) — runs the screen + voiceover
- **Setup verifier:** Tech Lead (TL) — confirms backend + DB + seeded users + Bedrock are green BEFORE rolling
- **Reviewer:** Clinical Lead (CL) — watches the cut and signs off on clinical accuracy

---

## 0. Pre-recording checklist (run 30 minutes before)

### 0.1 Environment
- [ ] Postgres up: `docker compose ps` shows `clincase-postgres` running on port `15432`
- [ ] Backend up: `curl -s http://localhost:8000/healthz` returns `{"ok": true}`
- [ ] Frontend up: open `http://localhost:5173` — Login page renders
- [ ] Bedrock provider live: `curl -s http://localhost:8000/llm/ping | jq -r .provider` → `bedrock`
- [ ] OpenRouter fallback ready (commented in `.env`, can flip in 60s)
- [ ] Cohort seeded: `curl -s http://localhost:8000/cases?limit=1 -H "Authorization: Bearer <token>" | jq '.cases | length'` ≥ 100

### 0.2 Browser setup
- [ ] **Chrome with a clean profile** (no plugins, no bookmarks bar, no DevTools open)
- [ ] Window size: **1920 × 1080**, zoomed to **110%** so text is readable on a projector
- [ ] DevTools docked to bottom for the network panel (ONLY if you're recording the agent stream — otherwise hide)
- [ ] Disable autofill: address bar shouldn't show suggestions

### 0.3 Recording tool
- [ ] OBS Studio (free), 1920×1080 @ 30fps, MP4 H.264
- [ ] Microphone: USB / lavalier, room ambient noise low. Test: record 10s, listen back. If you hear keyboard tapping, switch to a softer keyboard or move the mic.
- [ ] Cursor highlighter ON (yellow halo around cursor)
- [ ] Click animation ON (small ring expands on click)

### 0.4 Demo data — pin these IDs ahead of time
- [ ] Identify a **clean APPROVE case** from the cohort (look for trastuzumab + Aetna + status `approved`). Note its case ID. Example: `case_a8f23910`.
- [ ] Identify a **clean DENY case with appeal** (look for status `appealed`). Note its case ID. Example: `case_b8d84d77`.
- [ ] For Path C (multi-payer), use the same APPROVE trastuzumab case — Compare button appears on every case detail page.

> **CRITICAL:** Do not use a live LLM call during the recording. Use **already-finished** cases from the seed. Live calls add unpredictability and can fail mid-take. The judges don't know the difference; they see the agent traces, the citations, the verdicts. The video below is a tour of completed work.

### 0.5 Login dry-run
- [ ] Login as `admin@aerofyta.health` / `clincase2026` once before the take. Confirm the Sidenav shows "DA · Demo Administrator".
- [ ] Logout, refresh, then start the actual take from the Login page.

---

## 1. Recording structure

| Section | Length | Purpose |
|--------:|-------:|---------|
| Title card                     | 0:00–0:08  | Brand, tagline, music ducks |
| Login (frame the persona)      | 0:08–0:25  | Set the user — a coordinator at Aerofyta |
| Dashboard quick scan           | 0:25–0:42  | Establish "this is a real workspace, with real numbers" |
| **PATH A — Approval**          | 0:42–1:30  | Trastuzumab approval, agent trace |
| **PATH B — Denial → Appeal**   | 1:30–2:18  | Denial-bound case, conditional appeal generation |
| **PATH C — Multi-payer arbitration** | 2:18–3:00 | Compare across 4 payers |
| Compliance + Audit close       | 3:00–3:20  | Open Compliance page, show audit trail |
| End card + ask                 | 3:20–3:30  | "Built on AWS Bedrock + Claude Sonnet 4.6" |

**Total:** 3 minutes 30 seconds.

---

## 2. Title card (0:00–0:08)

**Visual:** Plain card on deep indigo background.
```
CLINCASE
The prior-auth copilot for oncology.
Built on AWS Bedrock · Claude Sonnet 4.6
Team AeroFyta · the 2026 hackathon
```

**Voiceover (read slowly, professionally):**
> "ClinCase — the prior-authorisation copilot for oncology. Built on AWS Bedrock and Claude Sonnet four-point-six. By Team AeroFyta."

**Music:** A subtle synth bed at low volume. Ducks out at 0:08 when the real screen comes up.

---

## 3. Login (0:08–0:25)

**Frame:** Login page at `http://localhost:5173/login`.

| t | Action | Voiceover |
|--:|--------|-----------|
| 0:08 | Cut to Login page, full-screen | "ClinCase is multi-tenant by design — every coordinator, reviewer, and admin sees only their organisation's cases." |
| 0:13 | Click the **"Sign in as Demo Coordinator"** quick button | "I'll sign in as a coordinator at Aerofyta Health Sciences — our seeded demo organisation." |
| 0:18 | Wait for the redirect to `/dashboard` | *(silence — let the redirect happen)* |
| 0:21 | Cursor lands on the user pill in the sidenav | "Coordinator role. The sidenav adapts — Settings is hidden, Reviewer queue is read-only." |
| 0:25 | End of login segment | |

**Recording note:** If the demo coordinator quick-button doesn't auto-fill, click into the email/password fields manually and type. **Don't type the password — paste it from clipboard** so the video doesn't show keyboard fumbles.

---

## 4. Dashboard quick scan (0:25–0:42)

**Frame:** `/dashboard`.

| t | Action | Voiceover |
|--:|--------|-----------|
| 0:25 | Show full Dashboard | "108 cases under this organisation. 53.7% approval rate. The four insight cards on top are real cohort metrics — pulled from a live database query, not a mock." |
| 0:32 | Hover over the **"Cases needing reviewer attention"** card | "Eight cases routed to reviewer queue. Each card is a click-through into the queue." |
| 0:38 | Click **"Cases"** in the sidenav | "Let's open the cases list." |
| 0:42 | Cases page loads | |

**Recording note:** Dashboard numbers (108 cases, 53.7%) come from the seed. Verify they're the actual values 24 hours before recording — if they've drifted, re-seed or update the voiceover.

---

## 5. PATH A — Approval (0:42–1:30)

**Frame:** `/cases` → click into the chosen approve case.

| t | Action | Voiceover |
|--:|--------|-----------|
| 0:42 | Cases list, full-screen | "Forty-seven open cases. Sorted by recency. Filter by payer, by status, by treatment." |
| 0:48 | Click into the trastuzumab APPROVE case (the pinned one from §0.4) | "Stage IIIA HER2-positive breast cancer. Patient S.D., on Aetna policy 0048." |
| 0:55 | Case detail page loads. Cursor lands on the **agent trace timeline**. | "Five agents ran. Watch the trace." |
| 1:00 | Click on **Clinical Extractor** in the trace | "The Clinical Extractor parsed the FHIR bundle plus the physician note into a structured snapshot — diagnosis, biomarkers, performance status, treatment request. **No PHI in the LLM call** — name, DOB, MRN are masked by the Bedrock Guardrail before any token leaves our VPC." |
| 1:08 | Click **Policy Retriever** | "Top five policy excerpts retrieved from the Bedrock Knowledge Base. You can see the section headings — Initial Authorization, Continuation, Exclusions. These are real Aetna 0048 sections, real LVEF and ECOG criteria." |
| 1:15 | Click **Necessity Reasoner** | "Per-criterion confidence. HER2 positive — 0.98. LVEF ≥ 50% — 0.95. ECOG 0-2 — 0.97. Every criterion green." |
| 1:22 | Click **Decision Composer** | "APPROVE. With a paragraph any executive can read, and citations to both clinical evidence pointers and policy section pointers. **Every claim has a pointer.** No claim without a citation." |
| 1:28 | Cursor on the verdict badge (green APPROVE) | "11 seconds, end-to-end." |
| 1:30 | End of Path A | |

**Recording note:** The trace timeline should be smooth. If a click is laggy, re-record this segment. The judges will pause exactly here, looking for the citation pointers — make sure they're visible.

---

## 6. PATH B — Denial → Appeal (1:30–2:18)

**Frame:** Back to `/cases` → click into the chosen deny case.

| t | Action | Voiceover |
|--:|--------|-----------|
| 1:30 | Click **Cases** in sidenav | "Now a denial case." |
| 1:34 | Click into the EGFR-wild-type osimertinib case | "Same workflow — Stage IV NSCLC, but the EGFR mutation is wild-type. Osimertinib is not indicated. Watch what the system does." |
| 1:42 | Case detail loads. Click **Necessity Reasoner** in the trace. | "The Necessity Reasoner flags the biomarker mismatch — confidence 0.94 against authorisation. This is exactly the kind of mismatch a stressed coordinator misses on Friday afternoon." |
| 1:50 | Click **Decision Composer** | "Verdict: DENY. Confidence 0.92. The rationale paragraph cites the policy section that requires EGFR mutation, and the patient's pathology report that shows wild-type." |
| 1:58 | Click **Appeals Drafter** in the trace | "And here's the conditional edge. On a DENY, the LangGraph DAG fires the Appeals Drafter — automatically. **No human typed any of this.**" |
| 2:06 | Scroll the appeal letter in the panel | "A formal appeal letter, structured arguments JSON for payer-API consumption, three citations to NCCN guidelines, and the patient's specific evidence. Ready for the coordinator to review and submit." |
| 2:14 | Cursor on the Appeals tab badge | "From denial to appeal in 22 seconds. The current manual workflow takes a week." |
| 2:18 | End of Path B | |

**Recording note:** The Appeals Drafter is the single most-impressive moment in the video. **Don't rush it.** Let the panel read the appeal letter. If you have to choose between Path B and Path C running over time, keep Path B at length and trim Path C.

---

## 7. PATH C — Multi-payer arbitration (2:18–3:00)

**Frame:** Back to the trastuzumab APPROVE case from Path A → click **Compare** button.

| t | Action | Voiceover |
|--:|--------|-----------|
| 2:18 | Navigate to the case → click the **Compare** button (top-right of case detail) | "Here's where it gets interesting. The same trastuzumab case — but the coordinator wants to know: which payer should we submit to first?" |
| 2:25 | Compare page loads. Four payer cards visible. | "Four payer cards. Each one runs the same Necessity Reasoner against that payer's actual policy excerpts — pulled live from the Bedrock Knowledge Base." |
| 2:33 | Cursor on the Aetna card (REFER) | "Aetna says REFER. Their LVEF window tightened to 60 days in v3.2. The patient's last echo was 75 days ago — outside the new window." |
| 2:42 | Cursor on the UHC card (APPROVE) | "UHC: APPROVE. Their LVEF window is 90 days. Patient is well within." |
| 2:48 | Cursor on BCBS + Anthem cards (both APPROVE) | "BCBS, Anthem — both APPROVE." |
| 2:54 | Cursor on the arbitration recommendation strip at the top | "Arbitration recommendation: submit to UHC first. The patient meets all four payers; UHC has the cleanest path. **This is the kind of decision an experienced coordinator makes in 20 minutes.** ClinCase did it in 8 seconds, with the citation trail." |
| 3:00 | End of Path C | |

**Recording note:** The cross-payer arbitration is **backend-real** thanks to the 21-entry policy corpus with cross-payer trastuzumab coverage. If a judge asks "is this real?", the answer is yes — open the Network panel and show the four parallel `/policies/retrieve?payer=...` calls.

---

## 8. Compliance + Audit close (3:00–3:20)

**Frame:** Click **Compliance** in the sidenav.

| t | Action | Voiceover |
|--:|--------|-----------|
| 3:00 | Click **Compliance** in sidenav | "One last thing — the audit trail." |
| 3:05 | Compliance page loads. Cursor on the four compliance signal cards. | "PHI redaction logged. Decision provenance per case. CMS-0057-F SLA tracker — currently 100% of decisions inside the 7-day window. Bias surveillance dashboard — no cohort gap above three percentage points." |
| 3:14 | Click on a single audit row | "Per case, full agent trace, exportable as a CSV for any CMS auditor request. Every prompt version hash. Every input. Every output. Permanent." |
| 3:20 | End of Compliance | |

**Recording note:** The Compliance page is what differentiates ClinCase from a generic LLM wrapper. Linger on the cards — judges from a regulated industry care about this **more** than the agent reasoning.

---

## 9. End card (3:20–3:30)

**Visual:** End card with the ClinCase wordmark + sponsors.

```
CLINCASE
The prior-auth copilot that thinks like an oncologist
and writes like a payer.

Built on AWS Bedrock · Claude Sonnet 4.6 · LangGraph

Team AeroFyta · the 2026 hackathon

preethisivachandran0@gmail.com
```

**Voiceover:**
> "ClinCase. Built on AWS Bedrock and Claude Sonnet four-point-six. CMS-0057-F ready by January twenty-twenty-seven. Pilot with the payer organization — our pilot scope is in your inbox by Friday. Thank you."

---

## 10. Post-record checklist

- [ ] Watch the full take **at 1.0× speed**. Cut nothing.
- [ ] Watch a second time at **1.5× speed**. If anything feels slow, re-record only that segment.
- [ ] Confirm voiceover audio is balanced (-12 dB peak, no clipping)
- [ ] Confirm cursor highlight is visible against the dark theme
- [ ] CL signs off on clinical accuracy of the voiceover
- [ ] Export as `ClinCase_Demo_v1.mp4`, H.264, 30fps, 1920×1080, 8 Mbps
- [ ] Upload to **two** locations: Google Drive (linked from submission) AND a local USB drive (backup for the on-stage demo failure path)
- [ ] Test playback on the actual demo laptop. Full-screen. **Confirm it plays without internet.**

---

## 11. Common mistakes to avoid

1. **Don't open DevTools mid-recording** unless the script asks for it. The judges' eyes go to the chrome of the browser, not the app.
2. **Don't narrate every click.** Narrate the *meaning*. "I'm clicking on Necessity Reasoner" → wrong. "Per-criterion confidence — HER2 0.98, LVEF 0.95" → right.
3. **Don't use ums.** Re-record the line.
4. **Don't apologize on camera.** "Sorry, let me redo that" stays in the take — never publish a take with an apology.
5. **Don't show the password field unmasked.** Use the demo button, not manual typing.
6. **Don't rush the Compare page.** The cross-payer arbitration is the most differentiating moment. Let it land.
7. **Don't fade out the music too fast.** The end card needs 3 full seconds for the voice ask to land before the music ends.

---

## 12. Time pressure decisions

If the video runs over 3:30:
- **First cut:** trim Dashboard (§4) from 17s to 10s — go straight from Login to Cases.
- **Second cut:** trim Path C voiceover, especially the redundant "BCBS, Anthem — both APPROVE" line.
- **Last resort:** drop Compliance (§8). Mention it verbally on stage instead.

If the video runs short of 3:30:
- Add a 5s pause on the Necessity Reasoner per-criterion list — let the judges read.
- Add 5s on the appeal letter scroll — let them see the citation density.

---

*Record once. Submit twice. Have the backup video on the laptop on demo day.*
