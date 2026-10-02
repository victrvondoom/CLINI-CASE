# Honest build scope and originality timeline - CLINI-CASE (One Health Interoperability Gateway)

Snapshot inspected 2026-10-02 on branch `feature/unified-journey`. Repository: https://github.com/victrvondoom/CLINI-CASE (public). Commit dates are author dates recorded in Git; they show when work was recorded here, not when every line was first written.

## Official period used for classification

```
HACKATHON_START=2026-09-16   # official rules, verified 2026-10-02
HACKATHON_END=2026-09-30     # official rules, verified 2026-10-02
SUBMISSION_DEADLINE=2026-10-04 21:00 PDT   # official updates, verified 2026-10-02
```

Sources verified live on 2026-10-02: the [official rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules) explicitly list September 16-30, 2026. The [updates](https://oneaquahealth-ieee-hackathon.devpost.com/updates) extend submission to October 4, 2026 at 9:00 PM PDT and invite prototype refinement, but do not explicitly replace the development-period dates in the rules. An earlier update says September 14-30, so start dates conflict; this table conservatively uses the rules. October changes remain post-period hardening. No commits were altered or backdated.

Classification rule: a commit dated on or before 2026-09-30 is "within period" by date; one dated 2026-10-01 or later is "post-period". The first visible commit is dated 2026-09-20, inside the stated period, but it is a large initial import of an existing platform, so a date alone does not make that platform hackathon-built. It is listed separately as reused.

## Pre-existing platform reused (not claimed as Track 7 work)

| Component | Evidence (commit, date) |
|---|---|
| Oncology 7-agent prior-authorization pipeline, AWS integration, earliest visible root | `9a3f48f` 2026-09-20; `e152654` 2026-09-20 |
| OncoTwin patient digital twin | `c8e032a` 2026-09-24 |
| AquaHealth freshwater module (OneAquaHealth) | `5d24d3e` 2026-09-27 |
| CardioTwin CAD risk model | `6015337` 2026-09-30 |
| Auth/roles, tenant database, clinical pipeline, twin models, observation store, UI primitives | present before gateway work; `9e30eb1`, `dda057d`, `2e94ca7`, `c10ae38` 2026-09-29 |

Whether any of these were first written before Sep 16 or inside the period cannot be established from Git (history begins 2026-09-20). The repository was created on GitHub on 2026-09-24 (API `created_at`).

## Built during the official hackathon period (by commit date, 2026-09-16 to 2026-09-30)

| Work | Evidence (commit, date) |
|---|---|
| One Health Track 7 evidence workflow integrated | `55c4e32` 2026-09-30 |
| Case Digital Twin and Case Intelligence ID with evidence lineage and trace | `4d29bc7` 2026-09-30 |
| Security baseline (platform-admin vs org-admin, tenant-scoped MCP, no plaintext deploy secrets) and CI fix | `1400628`, `56cbde7` 2026-09-30 |
| Proprietary license replaces MIT | `564da4c` 2026-09-30 |
| Dashboard modules made dynamic; fabricated data removed; review fixes | `26f9374`, `76648c7` 2026-09-30 |

## Post-period hardening and later work (commit date 2026-10-01 or later)

| Work | Evidence (commit, date) |
|---|---|
| Case Digital Twin PR #2; run/case/trace identity; real human-review pause/resume; typed Bedrock errors, model registry, independent verifier, agent spans (Phases 2-9) | `5de5768`, `804af86`, `d332316`, `17f5305`, `af26f1f` 2026-10-01 |
| Pending-work / win-plan docs | `0ad2a1d` 2026-10-01 |
| Track 7 gateway: typed schema mapping, HITL, independent receiver, round-trip, adversarial tests | `0f8be4f` 2026-10-01 |
| Evidence Passport, persistent revision manifests, offline verifier, hardening verification | `d019693`, `840739d` 2026-10-01 (PR #3 `2bc681a`, PR #4 `b167e39`) |
| FHIR R4 facade, independent receiver round-trip, deploy showcase; CodeQL-driven fixes | `665426b`, `540525a`, `c1fca93`, `61bc472` 2026-10-01 (PR #5 `45a069d`) |
| Close pending work: security gaps, trace propagation, pricing source, eval harness | `d193861` 2026-10-01 (#6) |
| Unified evidence journey: design doc, API, UI, platform presentation | `ce1c477`, `8a1dd1f`, `3a3b9c1`, `b52eaf0` 2026-10-02 |
| Containerization and local Kubernetes (kind) orchestration | `b261a60`, `5484f44` 2026-10-02 |
| README/runbook pointers and journey, UI and k8s fixes | `5144c58`, `5576dea`, `4f5e1a9`, `d228fcb` 2026-10-02 |

Under the dates above, the main Track 7 gateway (`0f8be4f`, `d019693`, FHIR facade, passport) falls after Sep 30. This is disclosed, not hidden; whether this delta is eligible needs organizer clarification (see [JUDGE_ACCESS.md](JUDGE_ACCESS.md)).

## Development assistance

Claude and Codex assisted development. Author names in Git history include "Claude" and "OpenAI Codex" alongside human accounts (vsrupeshkumar, victrvondoom, internationalhackerrebirth). The earlier hardening work used Codex for implementation, documentation and verification; the later journey/Kubernetes work in this branch was also AI-assisted. Human authors are responsible for review, claims and submission. Deterministic reference mappings are rules, not AI inference. Live semantic suggestions use the existing governed LLM abstraction; source fields remain untrusted and human confirmation remains mandatory. No clinical model is represented as newly invented for Track 7.

## Reproduce

`git log --reverse --format="%h %aI %an %s"`; inspect a commit with `git show --name-status <hash>`. No eligibility guarantee or hackathon-only authorship claim is made.

## Component classification summary

| Component | Pre-existing platform? | Recorded during official period? | Post-period hardening? | Evidence |
|---|---|---|---|---|
| Oncology / Bedrock, auth, clinical cases | Reused; original writing dates not established | Imported / changed within period | Yes | Initial import and commit tables above; import date does not prove original development |
| OncoTwin / CardioTwin | Reused optional context | Commits recorded within period | Yes | `c8e032a`, `6015337`; not claimed as Track 7 inventions |
| AquaHealth | Reused freshwater module | Commit recorded within period | Yes | `5d24d3e` |
| One Health evidence workflow | Track 7 integration | Yes, by commit date | Yes | `55c4e32` and later commits above |
| Unified journey / runtime UI / compact contextual navigation | Existing foundations reused | Final UI not claimed within period | Yes | Current uncommitted working tree, October 2 |
| Passport Ed25519 signature / bulk approval / external FHIR and dataset / official validation evidence | Existing foundations reused | This implementation not claimed within period | Yes | Current uncommitted working tree, October 2; verification report |
