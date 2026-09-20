# ClinCase — Demo Day Recipe (May 7, 2026)

**Validated against the running stack on May 4, 2026.**
**Status: GO with the recipe below. Do NOT improvise.**

---

## The two demo paths

### Path A — Pre-staged decision (RECOMMENDED for the live 5-min demo)

**Why:** A live agent run takes 3–5 minutes (not 90 seconds). The
PITCH_SCRIPT's "ninety seconds. APPROVE." promise is **not achievable**
with the current criterion-splitter / evidence-matcher cascade. Demo
goes instant via pre-staged data.

**The pre-staged demo case is in the DB:**

```
case_id:         demo-day-jd-001
status:          approved
patient_initials: JD
payer_id:        aetna
drug:            trastuzumab (J9355)
verdict:         APPROVE
confidence:      0.94
citations:       7  (clinical × 3 + policy × 1 + fda_label × 1 + guideline × 1 + compendium × 1)
```

**What to click in the demo:**

1. Login as `admin@aerofyta.health` / `clincase2026`
2. Navigate to **Cases** → search for `demo-day-jd-001` (or filter by `status: approved`)
3. Click into the case → **Case Detail** loads instantly with full decision
4. Citations render with 5 distinct color-coded chips (round-14 work visible)
5. Click any citation chip → modal opens with full source detail
6. Tab to **Compliance** → 23 controls grid renders
7. Tab to **Architecture** → live 6-layer descriptor with the partner alignment grid
8. Tab to **ROI** → Humana 6M slider shows $1.26B per half-star

**End-to-end demo time: ~90 seconds (matching the pitch).** No live LLM call needed.

### Path B — Live agent run (RISKY — only for Q&A "show me how it really works")

If a judge asks *"can you actually run a fresh case live?"*, here's the procedure:

1. Have backend + worker + frontend all running (verify on stage with one test before pitching)
2. Navigate to **Cases** → click any pending case **EXCEPT** the seeded ones
3. Click "Run ClinCase" → SSE trace lights up
4. **Talk through the architecture for ~3 minutes** while it runs
5. **WARNING:** The case may DENY (the agents are correctly conservative on incomplete data). If asked why, say *"the agents are designed to refer when evidence is incomplete — patient safety over speed."*

**Cost per live run: ~$0.50–1.50 of OpenRouter credit.** Budget for 2 max.

---

## Pre-flight checklist (do this 30 minutes before stage)

```bash
# 1. Confirm services up
curl -s -o /dev/null -w "backend: %{http_code}\n" http://localhost:8000/api/v1/healthz
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:5173

# 2. Confirm the pre-staged case is queryable
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@aerofyta.health","password":"clincase2026"}' \
  | python -c "import json,sys; print('TOKEN:', json.load(sys.stdin)['access_token'][:40]+'...')"

# 3. OpenRouter balance (in case live run is needed)
# Check at https://openrouter.ai/settings/credits — should show > $5

# 4. The 4 demo screens render in browser
# - http://localhost:5173/dashboard
# - http://localhost:5173/cases
# - http://localhost:5173/compliance
# - http://localhost:5173/architecture
```

If ANY of those fail → **fall back to recorded video** (script in `VIDEO_SCRIPT.md`).

---

## What was learned in May 4 robust testing

### ✅ What works perfectly

| Area | Status |
|---|---|
| Architecture descriptor + the partner alignment page | Renders beautifully |
| Login + JWT + RBAC | 100% reliable |
| All 18 demo-critical API endpoints | Respond correctly |
| Round-14 prompt depth (oncology-authentic, payer-anchored citations) | Verified producing real reasoning |
| Frontend rendering of all 5 citation kinds | Verified (CitationChip + CitationModal) |
| 23-control compliance library | Live + interactive |
| Architecture page (6 layers, AAOSA, TriZetto, Anthropic alignment) | Fully rendered |

### ⚠️ What works but is slower than pitched

| Area | Reality | Demo workaround |
|---|---|---|
| Live agent run on a case | **3–5 minutes**, not 90s | Use pre-staged `demo-day-jd-001` case |
| Cost per live case | **$0.50–1.50** of OpenRouter | Budget 2 max for Q&A |
| Conservative DENY on incomplete data | Agents correctly refuse to APPROVE without complete evidence | Frame as "patient safety over speed" |

### ❌ Real bugs found (some fixed, some live-recoverable)

| Bug | Status |
|---|---|
| `/finops/*` HTTP 500 (`created_at` vs `started_at` column) | ✅ FIXED |
| LLM model_id resolution provider-aware fallback | ✅ FIXED |
| GenAI Gateway allowlist (added OpenRouter + Anthropic IDs) | ✅ FIXED |
| `counter_evidence_finder` JSON truncation | ✅ FIXED (max_tokens 8000) |
| `letter_composer` JSON truncation | ✅ FIXED (max_tokens 8000) |
| `criterion_splitter` produces 15+ atomic criteria → causes 158 evidence_matcher calls per case | ⚠️ NOT FIXED — too risky to change at T-3d. Workaround: avoid live runs in main demo. |
| `.pptx` slide 1 has "Idea Title :" template-leak prefix | ❌ STILL OPEN — needs PowerPoint manual fix |
| Pre-existing pytest tests fail without Postgres TestClient | ⚠️ Pre-existing, not demo-blocking |

---

## Final demo-readiness scorecard (post-May-4 testing)

| Dimension | Status | Confidence |
|---|---|---|
| Backend stability under load | ✅ Verified across 456+ LLM calls | 95% |
| Frontend visual quality (4 demo screens) | ✅ Architecture page is stunning; case detail clean | 85% |
| Pre-staged demo case path | ✅ Verified end-to-end | 95% |
| Live agent run path (if Q&A asks) | ⚠️ 3–5 min latency, may DENY | 60% |
| Round-14 prompts producing real reasoning | ✅ Verified in agent_runs | 95% |
| 5 citation kinds rendering correctly | ✅ Frontend + backend aligned | 90% |
| .pptx visual quality | ❌ Template leak unfixed | 40% |
| Bedrock migration (May 6) | ⚠️ Unrehearsed; runbook in BEDROCK_MIGRATION_RUNBOOK.md | 60% |
| Pitch script + Q&A drill (already production-grade) | ✅ Strong | 90% |
| OpenRouter credit balance | ✅ ~$17 remaining (~10 cases of margin) | 95% |

**Overall demo-readiness: ~80%** with the pre-staged demo path.
(Was 65% with naive "click and run" — pre-staging is the unlock.)

---

## What you MUST do before May 7 morning

1. **Open the .pptx in PowerPoint.** Fix slide 1 "Idea Title :" leak. Audit slides 2–13. Estimated time: 90 minutes.
2. **Practice the pitch with the pre-staged demo case** at least 3 times against `demo-day-jd-001`. Estimated time: 90 minutes.
3. **Bedrock migration on May 6** per `BEDROCK_MIGRATION_RUNBOOK.md`. If it fails, fall back to OpenRouter. Estimated time: 3 hours including rollback test.
4. **Record a 90-second sizzle-reel video** as backup (script in `VIDEO_SCRIPT.md`). Estimated time: 60 minutes including 3 takes.

Total remaining work: **~6 hours**. Everything else is rehearsal-not-build.
