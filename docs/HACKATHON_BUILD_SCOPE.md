# Honest build scope and originality timeline

Snapshot inspected 2026-10-01. Repository: https://github.com/victrvondoom/CLINI-CASE.git. Commit dates show when work was recorded here; they do not independently prove when every source line was originally authored.

| Recorded commit | Author timestamp | Scope |
|---|---|---|
| 9a3f48f | 2026-09-20 14:12:26 +05:30 | Earliest visible root: AWS integration / existing platform |
| c8e032a | 2026-09-24 16:39:11 +05:30 | OncoTwin addition |
| 5d24d3e | 2026-09-27 21:33:03 +05:30 | AquaHealth addition |
| 6015337 | 2026-09-30 08:12:00 UTC | CardioTwin addition |
| 55c4e32 | 2026-09-30 22:33:18 +05:30 | Existing One Health evidence/FHIR workflow |
| 5de5768 | 2026-10-01 08:49:25 +05:30 | Case Digital Twin / intelligence ID |
| 0f8be4f | 2026-10-01 09:59:48 +05:30 | Gateway, typed schema mapping, HITL, independent receiver, round-trip, adversarial tests |
| Current hardening change | 2026-10-01 working session; actual commit recorded by Git | Evidence Passport, persistent revision manifests, offline verifier, unified evidence binding, linked retest, computed ceiling, receiver withdrawal/rejection, measured loss, focused UX, cleanup and reproducible runbook |

Reused at the start of gateway development: authentication/roles, tenant database, clinical pipeline, twin models, AquaHealth observation store, existing One Health FHIR/evidence/review logic and UI primitives. New files/diffs for the gateway are exactly `git show --stat 0f8be4f`; the hardening delta is the next commit's diff. Archived duplicate source and operational scripts retain their Git history. No clinical model is represented as newly invented for Track 7.

The [rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules) list original work developed during Sep 16–30. The [updates page](https://oneaquahealth-ieee-hackathon.devpost.com/updates) announces an Oct 4 submission extension; the stated build period has not been rewritten in the rules page checked. Oct 1 work is disclosed explicitly and eligibility of this delta needs organizer clarification. Do not backdate commits, hide the platform history, or infer permission from an extension alone.

Development assistance: Claude and Codex appear in development history; this hardening work used Codex for implementation, documentation and verification. Deterministic reference mappings are rules, not AI inference. Live semantic suggestions use the existing governed LLM abstraction; source fields remain untrusted and human confirmation remains mandatory.

Reproduce timeline: `git log --reverse --format="%h %aI %cI %s"`; inspect files with `git show --name-status <commit>`. No eligibility guarantee or invented hackathon-only authorship claim is made.
