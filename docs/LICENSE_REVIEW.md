# License review - CLINI-CASE (One Health Interoperability Gateway)

Review date: 2026-10-02. Scope: `LICENSE`, `README.md` (License and Track 7 sections), `docs/JUDGE_ACCESS.md`, GitHub repository metadata. This is an engineering review, not legal advice. **No legal term in `LICENSE` was changed by this review.**

## Verified facts

| Item | Finding | Source |
|---|---|---|
| Repository | `https://github.com/victrvondoom/CLINI-CASE` | `git remote -v` |
| Visibility | **Public** (`"private": false`, `"visibility": "public"`, not archived, not a fork) | GitHub API, queried 2026-10-02 |
| GitHub-detected license | `key: other`, `spdx_id: NOASSERTION` (GitHub does not recognise it as an OSI license) | GitHub API |
| License in force | `LICENSE` = "PROPRIETARY SOFTWARE LICENSE", Copyright (c) 2026 vsrupeshkumar, all rights reserved. Introduced by commit `564da4c` (2026-09-30), "Replace MIT license with proprietary terms" | `LICENSE`, git log |
| README consistency | README "License" section restates the same proprietary terms and links `LICENSE` | `README.md` |

## What the LICENSE says (summary, not a replacement for the text)

- No permission is granted to use, copy, modify, distribute, host, **deploy**, publicly display, make available, or create derivative works.
- Public availability grants no license.
- Use requires prior, express written authorization in an agreement **signed by vsrupeshkumar and the authorized person/entity**, limited to that agreement's scope, purpose and duration; not transferable or sublicensable unless that agreement says so.
- Third-party libraries, datasets, models and trademarks stay under their own licenses.

## What the LICENSE does not say

- It does not mention hackathons, Devpost, judges, evaluation, or inspection-for-judging.
- It does not grant any right to run (execute) the Software locally. It lists "use" and "deploy" among the reserved acts.
- It does not point to any separate evaluation grant, and no such grant file exists in the repository.

## Consequence

The repository is public, but the license on its face grants judges (or anyone) no right to run, copy or evaluate it beyond what applicable law and the hosting platform's terms independently allow (for example, viewing). `docs/JUDGE_ACCESS.md` states that authorization was reported to exist (2026-10-01) but that no signed agreement or judge-specific grant has been inspected. Documents in this repository must not claim judge rights that the LICENSE does not grant.

## Decisions reserved for the owner (not made here)

The copyright holder (vsrupeshkumar) must choose. Options, without recommendation:

1. **Add an explicit evaluation permission** either as a clearly labelled addendum inside `LICENSE` or as a separate file (for example `EVALUATION_LICENSE.md`) stating who may do what (inspect, run locally, for judging purposes, for what period, no redistribution). Because `LICENSE` requires a written agreement signed by the owner and the authorized party, decide whether a published grant to "hackathon judges" satisfies or amends that requirement.
2. **Provide the signed written authorization** referred to in `LICENSE` to the organizers/judges, and reference it from `docs/JUDGE_ACCESS.md`.
3. **Relicense** (for example to a source-available or open-source license). This is a change of legal terms that only the copyright holder can make, and it must account for any contributor/co-author rights and for third-party materials. Note that history includes commits authored under several identities (vsrupeshkumar, victrvondoom, internationalhackerrebirth, "Claude", "OpenAI Codex"); the owner should confirm that all of those are covered by the owner's rights.
4. **Leave as is** and rely on organizer confirmation that inspection of a public repository suffices for judging.

Also confirm: whether the hackathon rules require a particular license or run permission (`docs/JUDGE_ACCESS.md` records that the rules text checked on 2026-10-01 did not specify one); and whether the earlier MIT license (replaced in `564da4c`) was ever relied on by third parties for versions published before 2026-09-30. This review makes no claim about the legal effect of that replacement.

## Third-party materials

See the table in `docs/JUDGE_ACCESS.md` and, once present, `docs/track7/DATA_SOURCES.md`. Licenses there are marked "verify" unless the repository itself states them. The one stated in the repository is the CardioTwin dataset README, which says the UCI Z-Alizadeh Sani extension is CC BY 4.0 (`backend/data/cardiotwin/README.md`); that statement was read here but not independently re-checked against UCI.
