# ClinCase — Demo Day Checklist

**For:** the 2026 hackathon finals · May 7, 2026 · Pune
**Use:** Print this. Bring it to stage. Walk it line-by-line.

---

## T-24h preflight (May 6 evening, after Bedrock migration)

- [ ] Backend boots: `cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000`
- [ ] Frontend boots: `cd frontend && npm run dev`
- [ ] All 56 routes register (`curl localhost:8000/api/v1/architecture/layers | jq '.layers | length'` = 6)
- [ ] DB connected (lifespan log shows `db.connected`)
- [ ] Bedrock provider live: `LLM_PROVIDER=bedrock` env set
- [ ] Bedrock region: `AWS_REGION=ap-south-1` (Mumbai — closest to Pune)
- [ ] At least one demo fixture loaded: `GET /api/v1/demo-fixtures | jq '.fixtures | length'`
- [ ] One smoke run end-to-end against the **clean APPROVE** fixture
- [ ] One smoke run against the **DENY-with-appeal** fixture
- [ ] One smoke run against the **HITL-pause** fixture (low-confidence)
- [ ] Verify `/api/v1/compliance/case/{id}` returns 8 clauses for the smoke-run case
- [ ] Verify `/api/v1/business-value/case/{id}` returns `savings_usd >= 1499`
- [ ] Verify `/api/v1/cases/{id}/evidence-pack` returns a JSON with `bundle_sha256`
- [ ] Verify TriZetto mock submit: `POST /api/v1/integrations/trizetto/submit` returns `accepted: true`
- [ ] Verify `/_mock/inbox` shows the submitted envelope
- [ ] Verify `/api/v1/llm-gateway/usage` returns non-zero token counts

## T-2h pre-stage

- [ ] Browser open at `/dashboard` with the live KPI tiles populating from `/api/v1/business-value/org`
- [ ] Browser tabs (in order, ready to switch):
  1. `/dashboard`
  2. `/cases` (with the 3 demo cases visible)
  3. `/cases/{first_demo_case}` (the case-detail view ready)
  4. `/roi` (with member_count slider preset to 6,000,000 — Humana scale)
  5. `/compliance` (live org scorecard)
  6. `/architecture` (5-layer descriptor live)
  7. `/industrialize` (Foundry manifest + model card live)
- [ ] **Backup browser window** with `ops/demo/standalone/ClinCase.html` already loaded —
      this is the zero-backend Claude Design showcase. If the live React app or Postgres
      hiccups on stage, switch to this window. Tweaks panel (bottom-right) lets you
      flip APPROVE/REFER/DENY paths live without touching code.
      See `ops/demo/standalone/README.md` for full route map + verification checklist.
- [ ] `cat ops/demo/GO_TO_MARKET.md | head -60` printed and ready
- [ ] Backup: `kubectl logs deploy/clincase-worker -n clincase --tail=100` ready in case Q&A goes there
- [ ] Verify `.kiro/specs/` is on disk (proves Kiro IDE story without leaving the IDE)

## T-0 — the 5-minute demo path

The judges have ~5 minutes of demo + 8-12 minutes of Q&A. Total stage time ~17 min. The demo path is intentionally tight and intentionally the partner-shaped.

### Minute 0:00 — open

> *"This is ClinCase — an oncology prior-auth copilot built on Bedrock + Claude Sonnet 4.6 + MCP. The same stack the industry standardized on for the Anthropic partnership announced November 4 last year."*

Tab: `/dashboard`. Point at the 4 KPI tiles + the 7-AGENT LANGGRAPH DAG footer band.

### Minute 0:30 — the case

Tab: `/cases`. Click the first demo case — trastuzumab APPROVE.

Tab: `/cases/{case_id}` opens. Click **Run ClinCase**.

> *"Watch the right panel. Each agent reports as it runs."*

(7-agent SSE stream renders. ~52 seconds elapsed time. Coffee-cup test passes.)

### Minute 1:30 — the result

When the run completes, point at:

1. **DecisionBadge** — "APPROVE, confidence 0.92"
2. **CitationChips** — "5 citations to Aetna oncology policy § 4.2"
3. **BusinessValuePanel** — "**$1,499.75 saved** vs $1,500 manual baseline. **17.1 minutes returned** to clinic. **20.8× speedup**."
4. **ComplianceScorecardCard** — "**6 of 6 in-force CMS-0057-F clauses** ✓"
5. **TrizettoSubmitPanel** — click **Submit to TriZetto AI Gateway**.

### Minute 2:30 — the industry-alignment moment

> *"This decision is now in TriZetto Facets and QNXT. Same Bedrock + MCP + Anthropic stack the partner runs."*

Show the round-trip: `gateway_id`, fanout targets, expandable Facets v3 + QNXT v2 envelopes with SHA-256 tamper hash.

### Minute 3:30 — the proof

Click **Download Evidence Pack**. JSON file downloads. Open it.

> *"This is what a CMS auditor gets. Case + decision + every agent_run + reviewer actions + live compliance + business value + the TriZetto envelope. SHA-256 over the whole bundle. **Reproducible in 12 seconds.**"*

### Minute 4:00 — the scale story

Tab: `/architecture`. Scroll past the 6 layer cards.

> *"5 layers. Live introspectable. AWS Foundation block names every service. the partner alignment block: AI velocity gap addressed True, AI adaptation gap addressed True, Foundry stage Build, Flowsource UX shape compatible."*

### Minute 4:30 — the ROI close

Tab: `/roi`. Slider already set to **Humana 6M MA**.

> *"At Humana scale, half a star is **$1.26 billion**. ClinCase's projected lift band is plus-0.2 to plus-0.4 stars. That's the Star Ratings revenue lift line in our pilot ROI."*

### Minute 5:00 — close

> *"ClinCase is the first oncology specialty agent bundle for TriZetto AI Gateway. Drop-in. Bedrock-native. CMS-0057-F-evidenced. Ready Monday."*

---

## Q&A talking points — mapped to the two rubric criteria

### Criterion 1: "Fully functional end-to-end MVP, demonstrable core user journey, handled edge cases, demo readiness"

| Question | Where the answer lives |
|---|---|
| "Show me a case end-to-end." | The 5-minute demo above. |
| "What happens when the agent isn't sure?" | `/cases/{id}` → run a low-confidence fixture → DAG pauses at `review_gate`; show `POST /resume` flow. **Edge case #6 in `ops/demo/EDGE_CASES.md`**. |
| "What if Bedrock goes down?" | `ops/sre/RUNBOOK.md` § INC-002 — Bedrock regional brownout. ModelRouter Haiku→Sonnet escalation; multi-region failover apply-ready. **Edge case #17, #18**. |
| "What about cost runaway?" | Per-case BudgetTracker $5 ceiling; per-tenant Gateway 24h rolling cap; live at `/api/v1/llm-gateway/usage`. **Edge case #5, #15**. |
| "Show me an edge case." | `ops/demo/EDGE_CASES.md` — 28 named cases, where handled, where tested. |
| "Is this really demo-ready?" | This checklist — every preflight checked. Last smoke test result in `ops/demo/SMOKE_TEST_RESULTS.md`. |

### Criterion 2: "Clean, modular, scalable architecture with documented design decisions and demonstrated scalability"

| Question | Where the answer lives |
|---|---|
| "Show me the architecture." | `/architecture` page. Live 5-layer descriptor. **Doc: `ops/architecture/TARGET_ARCHITECTURE.md`**. |
| "Why LangGraph?" | **ADR-0001**. Conditional edges + checkpointing + framework-agnostic for Bedrock AgentCore. |
| "Why Postgres SKIP LOCKED for the queue?" | **ADR-0002**. One fewer dependency than Redis Streams; same RPO/RTO as primary DB. |
| "How is each design decision documented?" | `ops/adr/` — 8 canonical Architecture Decision Records. |
| "How does this scale?" | `ops/SCALING.md` capacity model: 1K → 10K → 100K cases/day. Multi-region + provisioned-throughput + S3 Vectors Terraform apply-ready. |
| "Have you load-tested?" | `ops/sre/LOAD_TEST_RESULTS.md`. |
| "What about multi-tenancy?" | `ops/multi-tenant/ONBOARDING.md`. Per-tenant Bedrock Guardrail · per-tenant KMS · per-tenant Gateway policy · 7-15-day customer onboarding. |
| "What's your CI/CD?" | `.github/workflows/ci.yml` + `deploy-prod.yml`. OIDC, Inspector, Semgrep, SBOM, canary deploy with auto-promote on error budget. |

---

## If a step fails on stage

| Step | Fallback |
|---|---|
| Backend won't boot | Switch to **`ops/demo/standalone/ClinCase.html`** (already loaded in backup browser window) — full UI, mocked data, runs from disk. Then optionally fall back to slide-only walkthrough using screenshots in `ops/demo/screenshots/`. |
| Bedrock 402/throttle | Switch `LLM_PROVIDER=anthropic` (direct, with backup credits). If still failing, **switch to `ops/demo/standalone/ClinCase.html`** — zero LLM dependency. |
| Live agent run takes >2 min | Stop. Refresh. Switch to **`ops/demo/standalone/ClinCase.html`** Tweaks panel — flip the demo path, the agent loop animates instantly. |
| Frontend white-screens | Switch to **`ops/demo/standalone/ClinCase.html`** — separate code path, no shared state with the React app. |
| Evidence Pack download fails | Show the JSON in the browser via `curl localhost:8000/api/v1/cases/{id}/evidence-pack | jq` in a side terminal. |
| TriZetto submit fails | Show `/_mock/inbox` directly — proves the round-trip happened on the previous case. |
| Q&A goes deeper than checklist covers | Open `ops/architecture/AI_ADAPTATION_GAP.md` or the relevant ADR; read aloud. Better to read aloud than to bluff. |

---

## After the demo

- [ ] Save the SHA-256 of the Evidence Pack downloaded on stage — proof we live-ran.
- [ ] Capture `/api/v1/llm-gateway/usage` snapshot — shows real Bedrock spend.
- [ ] Note any judge questions we didn't have a crisp answer to → next iteration of `QA_DRILL.md` § Section 7.

---

*Drill twice. Demo once.*
