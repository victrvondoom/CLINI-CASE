# Historical material

Classification inspected before moving tracked files on 2026-10-01:

| Candidate | Decision | Reason |
|---|---|---|
| `frontend/` | KEEP | Sole active frontend; build/CI/deployment input |
| `frontend_BACKUP/` tracked files | ARCHIVE to `legacy/frontend_BACKUP/` | Historical snapshot; no runtime/CI references found |
| `ClinCase/frontend/` tracked files | ARCHIVE to `legacy/ClinCase/frontend/` | Duplicate older UI; originality evidence preserved |
| Root `_*.py` deployment/PDF scripts | ARCHIVE to `legacy/` | Historical machine-specific/cloud scripts, hardcoded paths; not used by current CI/demo |
| `baseline-npm-audit.json` | ARCHIVE to `legacy/` | Historical audit snapshot; not a current security result |
| Local node_modules/dist/caches/recovered folders | KEEP locally / ignored | Machine state, not judge-facing tracked source; never deleted blindly |
| Active `ops/`, CI, tests and synthetic fixtures | KEEP | Required platform workflows and verification |

No source functionality or originality evidence was deleted. `git log --follow` retains file history. Archived scripts are historical references with their original paths/credentials assumptions, not recommended deployment commands. Use active `ops/` and the documented demo launcher. No cloud deployments were run during cleanup.
