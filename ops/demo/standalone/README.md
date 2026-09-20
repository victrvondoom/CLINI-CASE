# ClinCase Standalone Demo Showcase

**Purpose:** Self-contained, zero-backend HTML demo of the entire ClinCase UI. Runs from any browser by opening `ClinCase.html`. Built by Claude Design across 4 days, integrated into the repo on 2026-05-05.

**This is the demo-day backup asset.** If the live backend (Postgres / OpenRouter / Bedrock / FastAPI worker) hiccups on stage, you flip to this file in another browser tab and the demo continues. No environment setup, no login, no LLM calls — every verdict / citation / appeal letter is mocked from `fixtures.jsx` + `data.jsx`.

---

## How to run

```bash
# Option 1 — double-click in Explorer
# Open: D:\xzashr.ai Files\clincase-workspace\ClinCase\ops\demo\standalone\ClinCase.html

# Option 2 — file:// URL (paste into address bar)
file:///D:/xzashr.ai%20Files/clincase-workspace/ClinCase/ops/demo/standalone/ClinCase.html

# Option 3 — local server (if browser blocks file:// modules)
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/ops/demo/standalone"
python -m http.server 8765
# then open http://localhost:8765/ClinCase.html
```

**No npm install. No Node. No backend. No internet (after first load — Tailwind/React/Babel are CDN-loaded once, then cached).**

---

## What's in it (12 routes)

| Route | Page | Source files |
|---|---|---|
| `#/` | Dashboard (hero + 4 KPI tiles + 3 demo cases + LiveAgentLoop) | `dashboard.jsx` |
| `#/cases/:id` | Case Detail (full agent pipeline + decision + citations + appeal + audit) | `app.jsx` + `result-panels.jsx` + `trace-panel.jsx` |
| `#/cases` | Cases table | `cases-page.jsx` |
| `#/cases/bulk-import` | FHIR Bulk Data $export drop-zone with parallel queue runner | `bulk-import-page.jsx` + `bulk-import-data.jsx` |
| `#/compare` | Multi-payer arbitration (Novelty #1) | `compare-page.jsx` |
| `#/policies` | Policy library (Aetna, UHC, NCCN, ASCO/CAP) | `policies-page.jsx` + `policies-data.jsx` |
| `#/policies/:id/diff` | Policy Diff Viewer (Novelty #2) | `policies-page.jsx` |
| `#/agents` | 5-agent LangGraph DAG topology + per-agent stats | `agents-page.jsx` + `agents-data.jsx` |
| `#/cohorts` | Approval rate analytics by payer × drug | `cohorts-page.jsx` + `cohorts-data.jsx` |
| `#/reviewer` | HITL queue (REFER cases) | `reviewer-page.jsx` + `reviewer-data.jsx` |
| `#/compliance` | CMS-0057-F § IV scorecard with PHI redaction sparkline | `compliance-page.jsx` + `compliance-data.jsx` |

Plus shared infra: `components.jsx` (atoms + 50 icons), `effects.jsx` (visual effects), `tweaks-panel.jsx` (live demo controls), `onboarding-tour.jsx` (interactive tour).

---

## Tweaks panel (live demo controls)

The floating Tweaks panel (bottom-right) lets you change demo state on stage without code:

- **Demo path:** APPROVE — HER2+ all met / REFER — missing LVEF / DENY — HER2− mismatch
- **Streaming speed:** 200ms – 3000ms per agent (slow it down for narration)
- **Density:** Comfortable / Compact (compact for projector at 10 ft)
- **Brand hue:** 0° – 360° (only touch this if light mode looks wrong)
- **Show PHI guardrail banner on run:** toggle the redaction animation
- **Audit trail expanded after run:** start with the audit drawer open
- **Trigger PHI banner now:** instant flash — for the "we redacted X PHI fields" moment

---

## Pre-demo verification checklist

Before May 7, run through this once:

- [ ] Open `ClinCase.html` in Chrome → Dashboard renders without console errors
- [ ] Click "Run ClinCase" on the APPROVE fixture → animated agent loop completes → citation chain shows 7 citations
- [ ] Navigate to `#/cases/case_d710c4be` (DENY) → appeal letter appears in editor
- [ ] Navigate to `#/agents` → 5-agent DAG renders, click each node → details panel updates
- [ ] Navigate to `#/policies/aetna-0123/diff` → side-by-side diff renders
- [ ] Navigate to `#/compliance` → 8-clause scorecard donut renders
- [ ] Toggle dark mode (button in top bar) → all pages remain credible
- [ ] Press ⌘K → command palette opens, search filters work
- [ ] Open in 1280×800 (judge laptop) AND 1920×1080 (projector) → no layout breaks
- [ ] Open Tweaks panel → switch between APPROVE / REFER / DENY → fixtures swap

If all 10 checks pass, this is your guaranteed-works demo asset. Ship it on a USB stick + put it in OneDrive as a 2nd copy.

### Route map (verified 2026-05-05 via Claude Preview — 13/13 pass)

| URL hash | Page |
|---|---|
| `#/` | Dashboard |
| `#/cases` | Cases list |
| `#/cases/case_8f4ad9c2` | Case Detail (APPROVE — HER2+ all met) |
| `#/cases/case_3b21e0fa` | Case Detail (REFER — missing LVEF) |
| `#/cases/case_d710c4be` | Case Detail (DENY — HER2− mismatch + appeal letter) |
| `#/cases/bulk-import` | FHIR Bulk Data $export |
| `#/compare` | Multi-payer arbitration |
| `#/policies` | Policy library |
| `#/policies/aetna-0123/diff` | Policy Diff Viewer (Novelty #2) |
| `#/agents` | 5-agent LangGraph DAG topology |
| `#/cohorts` | Cohort analytics |
| `#/reviewer` | Reviewer queue (HITL) |
| `#/compliance` | CMS-0057-F § IV scorecard |

### Two known fixes applied during integration (2026-05-05)

1. **`I.Menu` icon was missing** in `components.jsx` — TopBar's mobile-hamburger button referenced `<I.Menu>` but no such entry existed in the icon namespace. Added a 3-bar lucide-style menu icon to the I-namespace dictionary. Without this fix the entire React tree threw `type is invalid` and rendered as a white page.
2. **Case-detail route regex was too narrow** in `app.jsx` — original `/^#\/cases\/(AUTH-.+)$/` only matched `AUTH-`-prefixed IDs and silently fell back to Dashboard for fixture IDs like `case_8f4ad9c2`. Broadened to `/^#\/cases\/(.+)$/` (with explicit exclusion of `/cases/bulk-import`).

Both fixes are in the canonical files in this directory. If Claude Design rebuilds these files in a future wave, re-apply the same two patches.

---

## When to use the standalone vs the live React app

| Demo moment | Use the live React app | Use this standalone |
|---|---|---|
| Pre-stage rehearsal | ✅ tests the real pipeline | ❌ only mocked |
| Live stage demo (default plan) | ✅ shows real agent calls | — |
| **Live stage demo (if backend hiccups)** | ❌ | ✅ **flip to this tab** |
| Q&A "show me an X scenario" | ⚠️ depends on case prep | ✅ change in Tweaks → instant |
| Pre-recorded video backup | ✅ record from this | ✅ also viable |
| Booth/floor walking demo | ⚠️ needs WiFi + backend up | ✅ runs from a tablet |

---

## Why this exists separately from the React app

The **production frontend** at `ClinCase/frontend/` (Vite + React + TypeScript) is wired to the real backend — it makes real `/api/v1/cases/run-async` calls, streams real SSE events, persists to real Postgres. That's the canonical product.

This **standalone** is a parallel polish layer Claude Design built for hackathon-judge optics. It doesn't replace the React app. It's a fallback that ALWAYS works and is **demo-aesthetically perfect** — every animation, color token, micro-interaction was tuned for projector visibility and judge "wow" reaction.

For the May 7 finals, both exist. The React app is plan A. This is plan B.

---

## Integration history

- **2026-05-01** — Wave 1: Claude Design built initial 11 files, hit credit limit mid-build with gradient-text invisibility bug in dashboard.
- **2026-05-04** — Wave 2: Claude Design built all 6 priority pages (agents/policies/compliance/bulk-import/reviewer/cohorts) + effects + onboarding tour.
- **2026-05-05** — User extracted Claude-Design_UI.zip into this directory. Standalone now lives at `ops/demo/standalone/`.

---

## Files at a glance

```
standalone/
├── ClinCase.html                    ← entry point, double-click this
├── app.jsx                         ← top-level routing + CommandPalette + TweaksUI
├── components.jsx                  ← AppShell, Sidenav, KPITile, 50+ icons
├── effects.jsx                     ← visual flourishes
├── onboarding-tour.jsx             ← first-run guided tour
├── tweaks-panel.jsx                ← floating control panel
├── trace-panel.jsx                 ← LiveAgentLoop + ReasoningTrace + AuditLog
├── result-panels.jsx               ← DecisionBadge + CitationChain + AppealLetter
├── dashboard.jsx                   ← Dashboard route
├── cases-page.jsx                  ← /cases
├── compare-page.jsx                ← /compare (Novelty #1)
├── agents-page.jsx                 ← /agents (5-agent DAG)
├── agents-data.jsx                 ← agent stats mock
├── policies-page.jsx               ← /policies + /policies/:id/diff (Novelty #2)
├── policies-data.jsx               ← policy excerpts + diffs
├── compliance-page.jsx             ← /compliance (CMS-0057-F)
├── compliance-data.jsx             ← 8 clauses + PHI activity
├── bulk-import-page.jsx            ← /cases/bulk-import (FHIR Bulk $export)
├── bulk-import-data.jsx            ← 12-case parallel queue mock
├── reviewer-page.jsx               ← /reviewer (HITL queue)
├── reviewer-data.jsx               ← REFER case backlog
├── cohorts-page.jsx                ← /cohorts (analytics)
├── cohorts-data.jsx                ← payer × drug rollups
├── fixtures.jsx                    ← 3 oncology cases (APPROVE/REFER/DENY)
├── data.jsx                        ← KPIs, agent specs, audit events
├── screenshots/                    ← 11 PNGs of each route
└── uploads/                        ← reference images Claude Design used
```

7,240 lines total. 1.2 MB. Zero runtime dependencies beyond CDN-loaded React 18.3 + Tailwind + Babel-standalone.
