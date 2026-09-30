# AquaHealth — OneAquaHealth freshwater ecosystem module

An **additive** extension to ClinCase for the IEEE OneAquaHealth Global
Hackathon 2026. ClinCase remains what it was — a provider-side
prior-authorisation copilot for oncology — and gains a second, independent
capability for urban freshwater ecosystem monitoring and One Health
intelligence.

```
ClinCase (existing)              AquaHealth (new)
├── Clinical cases               ├── Citizen observations
├── Prior authorisation          ├── Environmental assessment (7 agents)
├── 7 clinical agents            ├── Human-in-the-loop review
├── Da Vinci PAS / FHIR          ├── FHIR R4 environmental export
└── OncoTwin digital twin        └── Map · Trends · One Health · Community
```

Both run in the same process, share the same auth, tenancy and agent
framework, and neither can break the other.

---

## What was added, and what was touched

**New, self-contained:**

| Path | Purpose |
|---|---|
| `app/aquahealth/vocab.py` | Controlled vocabulary — the four-state `Presence`, statuses, sources |
| `app/aquahealth/models.py` | Pydantic domain models |
| `app/aquahealth/assess.py` | Pure assessment engine (no I/O, no LLM) |
| `app/aquahealth/agents/env_agents.py` | The 7 agents, as real `Agent[I, O]` subclasses |
| `app/aquahealth/service.py` | Pipeline, review, dashboard/trend/One Health aggregates |
| `app/aquahealth/store.py` | In-process store + fail-soft Postgres write-through |
| `app/aquahealth/demo.py` | Labelled synthetic dataset |
| `app/aquahealth/fhir/mapping.py` | Prototype + FHIR R4 export |
| `app/aquahealth/evaluation.py` | Versioned synthetic Track 3 benchmark executed against production rules |
| `app/api/aquahealth.py` | 20 routes under `/api/v1/aquahealth` |
| `tests/aquahealth/` | 27 tests |

**Existing files modified — 59 added lines, 0 removed:**

- `app/main.py` (+12) — schema bootstrap, one import, one `include_router`
- `frontend/src/main.tsx` (+28) — 9 route registrations
- `frontend/src/components/Sidenav.tsx` (+19) — one new nav section

No existing route, agent, model, table or component was changed or removed.

---

## Design decisions worth knowing

### 1. `Presence` is four-state, not boolean

Every qualitative field is `observed` / `not_observed` / `unknown` /
`not_available`.

This is the single most important modelling choice in the module. "I looked for
fish and saw none" is ecological evidence. "I did not check for fish" is a data
gap. A boolean would silently merge them and manufacture data that no citizen
reported. The distinction is preserved end-to-end — into the agents, the status
derivation, the FHIR export (`valueCodeableConcept`, not `valueBoolean`) and
the UI.

### 2. The agents are deterministic

All seven are `Agent[I, O]` subclasses running through the real ClinCase agent
lifecycle — traced, budgeted, recorded — but they compute findings in pure
Python rather than calling an LLM.

An environmental triage signal that changes between two identical observations
cannot meaningfully be reviewed by a human. Determinism also means the module
runs with no model credentials configured, and a reviewer disagreeing with a
finding is disagreeing with a rule they can read.

When the traced path is unavailable (no DB for the trace sink), the pipeline
falls back to calling the same functions directly. Both paths call `assess.py`,
so results are identical.

### 3. Sparse data yields `INSUFFICIENT_DATA`, never "healthy"

Below `MIN_INFORMATIVE_FIELDS` (4), the status is `insufficient_data` and
confidence is `low`. Confidence is additionally capped by data quality, so a
two-checkbox observation can never produce a HIGH-confidence claim.

The failure mode this prevents: an empty observation reading as good news.

### 4. Trends refuse to appear before there is history

Below `MIN_TREND_OBSERVATIONS` (4) at one waterbody, both the trend agent and
the `/trends` endpoint say *"Insufficient historical observations to determine
a trend"* and plot nothing.

### 5. The reviewer overrides the AI, everywhere

`Observation.effective_status` prefers the reviewer's corrected status over the
AI's. Dashboard distributions, the map, trends and exports all read it, so a
human correction propagates through every surface while the AI's original call
is preserved for audit.

### 6. Agents live outside `app.agents` on purpose

ClinCase's manifest auto-discovers parents under `app.agents`. Placing these in
`app.aquahealth.agents` keeps the 7-agent / 21-sub-agent ClinCase manifest
unchanged — the same choice `app/oncotwin/agents/` makes. A test asserts the
two agent-name sets stay disjoint.

### 7. The FHIR export does not overclaim

The OneAquaHealth draft IG defines environmental profiles. This legacy export
is a *prototype FHIR-shaped representation carrying AquaHealth-defined codes* —
useful because any FHIR client can parse and route it, while a receiver must
still map the codes. Every payload says exactly that in `meta.tag`. The flat
`aquahealth.prototype.v1` shape is labelled "not a standard".

### 8. Gamification cannot reach the science

Badges are computed in `service.community_stats`, which `assess.py` never
imports or reads. A prolific contributor's observation is assessed by exactly
the same rules as a first-timer's; a test asserts this.

### 9. Demo data is labelled and separable

Every demo row carries `is_demo=True` and `source=demonstration_data`.
`clear_demo_data()` removes exactly those rows and never touches a real
contribution — also covered by a test. The dataset deliberately includes one
sparse site that resolves to `insufficient_data`, because a demo where every
record is confident would misrepresent the system.

---

## Storage

Two new tables, created by an idempotent `ensure_schema()` in the app lifespan:
`aquahealth_waterbodies` and `aquahealth_observations`. Neither the `cases`
table nor any other existing table is read or written.

Following the OncoTwin pattern, the in-process store is authoritative and
Postgres is a fail-soft write-through, so the module stays usable in the
DB-less mode ClinCase already supports.

---

## Hackathon track coverage

| Track | Where |
|---|---|
| 1 — Citizen Science UX | `/aquahealth/observations/new`: four-state answers, nothing mandatory but the waterbody name, plain language, photos, geolocation |
| 2 — Data-to-Insight | Dashboard, map, trends, waterbody rollups |
| 3 — AI-Supported Assessment | 7 agents, evidence-backed findings, confidence, data quality, human review |
| 4 — Awareness & Storytelling | "Why this matters" on the dashboard |
| 5 — Community & Gamification | `/aquahealth/community`, badges, participation counts |
| 6 — Resilience Informatics | Prototype early-warning panel, repeated-signal detection |
| 7 — Digital Health Standards | FHIR R4 Bundle/Observation export, code catalogue, honest labelling |

---

The primary submission is now **Track 7 — Digital Health Standards**, implemented
by the additive `app.onehealth` layer and documented in `docs/ONEHEALTH_TRACK7.md`.
**Track 3 — AI-Supported Assessment** remains the supporting track. The
`/aquahealth/evaluation` surface runs a versioned set of synthetic boundary
cases through the production assessment functions and reports abstention,
concern-detection, validation and false-reassurance metrics. These are software
behaviour checks, not claims of ecological or public-health validation.

## Running it

```bash
# Backend tests (no DB or LLM credentials needed)
cd backend && python -m pytest tests/aquahealth/ -q

# Frontend
cd frontend && npm run build
```

Seed the demonstration dataset from the AquaHealth dashboard ("Load demo
data", reviewer/admin only) or:

```bash
curl -X POST localhost:8000/api/v1/aquahealth/demo/seed -H "Authorization: Bearer $TOKEN"
```
