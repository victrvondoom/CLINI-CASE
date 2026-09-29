# Engineering remediation ledger

Scope: preserve ClinCase and OncoTwin features while correcting the issues from the September 29 review. This is an engineering evidence record, not a clinical certification. No live payer or clinical validation claim follows from local tests.

## Baseline

- Clean tracked working tree at start; no AGENTS.md found in this checkout.
- Previous-turn baseline: frontend build passed; main JS 957.91 kB (249.30 kB gzip), 3D chunk 862.08 kB (232.75 kB gzip).
- Previous-turn backend suite: 184 collected; six live-model failures (missing OpenRouter credential), four PAS database setup errors (connection refused). Baseline rerun is recorded in `baseline-tests.log` locally.
- Ruff: one unsorted import in app/main.py. Full mypy baseline being collected separately.
- Reproduction: two criteria (MET, NOT_MET) plus one confidence produced one retained criterion and APPROVE.

## Architecture and ownership

React/Vite routes -> authenticated FastAPI -> intake and typed clinical snapshot -> policy retrieval -> seven-agent LangGraph workflow -> deterministic verdict, review, appeals and communications. PostgreSQL stores cases, traces and worker jobs; Redis optionally distributes SSE. OncoTwin has deterministic simulation, synthetic-trained model artifacts, research and monitoring APIs. External boundaries include LLM providers, OCR, guideline feeds and payer adapters.

Workstreams: decision correctness (architect/QA); security/privacy (security/full-stack); frontend (performance/UX); integration, CI, reproducibility and evidence (root/reliability/product). Subsequent cross-review assigns reviewers outside their implementation ownership.

## Original issues (split into independently verifiable items)

| ID | Con / severity | User and engineering impact / root cause | Affected components / dependencies | Alternatives and selected approach | Status / test / regression risk / reviewer |
|---|---|---|---|---|---|
| C01 | Dropped criteria -> approval / P1 | Incomplete model output silently truncated by min(lengths) | Necessity schema, verdict, graph | Pad missing values vs reject incomplete output; selected exact-cardinality validation and conservative review | **RESOLVED**; malformed output and missing citations fail closed; focused and full suites passed; adversarial backend review accepted |
| C02 | Raw scan sent before redaction / P1 | Metadata removal mistaken for visual PHI removal | Intake, OCR engines, cloud clients | Local pixel redaction vs explicit governed cloud opt-in with local fallback; selected safe default plus honest boundary | **MITIGATED**; cloud document processing is disabled by default and outbound denial/fallback tests pass; deployers still own visual review when enabling cloud OCR |
| C03 | Limited text/FHIR PHI protection / P1 | Regex incomplete and structured input may bypass sanitizer | Privacy, extractor, receipts | Claim universal de-identification vs structural minimization and qualified receipts; selected minimization and honest guarantees | **MITIGATED**; structured identifiers are aliased, text screening expanded, receipts/UI qualify the limit, regression tests pass; not certified de-identification |
| C04 | Deleted-user token fallback / P1 | Signed token treated as current authorization when record absent | Auth, config | Remove demo support vs explicitly isolate outage demo mode; selected fail-closed normal auth | **RESOLVED**; missing/deleted users and healthy-database misses fail closed; explicit development-only outage mode is tested |
| C05 | Synthetic-only OncoTwin validation / P1 | Synthetic benchmark cannot establish clinical validity | Model artifacts, research API/UI | Fabricate performance vs explicit machine-readable evidence limits; selected visible evidence provenance | **BLOCKED** for clinical validation by absence of governed real-patient data and an external validation study; repository now reports the limitation and keeps autonomous-clinical-use false |
| C06 | Demo guideline/policy data / P1 | Emulated corpus may be mistaken for licensed current evidence | Guideline APIs, policy retrieval, UI | Replace with unavailable licensed feed vs expose provenance and fail-safe limitations; selected provenance | **BLOCKED** for current licensed content by missing publisher/payer feeds; repository claims and evidence-readiness output now distinguish demo corpus from production evidence |
| C07 | Partial FHIR/payer integration / P1 | PAS shape overstates conformance; submission may claim queued without queue job | FHIR API, jobs, DB, tests | Implement full external standard vs repair supported async contract and label remaining gaps; selected tested local contract | **MITIGATED**; case and job are now created transactionally and four PostgreSQL PAS contracts pass; full PAS IG/X12 certification and live payer submission remain external |
| C08 | Broad maintenance surface / P2 | Many domains and infrastructure paths exceed verification | Architecture, docs, CI | Rewrite/remove domains vs isolate change scope and strengthen quality gates; selected incremental boundaries | **MITIGATED**; no product domain was removed, core/integration/live test tiers and capability boundaries now make the surface auditable |
| C09 | Incomplete CI and advisory lint / P2 | Green CI can miss core backend failures | Workflows, test fixtures, dependencies | Skip external tests silently vs explicitly separate offline/DB/live suites; selected explicit tiers and blocking lint | **RESOLVED**; Ruff is blocking, core tests run offline, and a pgvector PostgreSQL job applies the schema and runs marked contracts |
| C10 | Unmeasured model latency/cost / P2 | Multiple provider calls and retries lack realistic workload evidence | Agent budgets, traces, docs | Claim speed vs report measured local behavior and external benchmark requirements | **MITIGATED**; invalid/negative/NaN budgets fail closed and tests pass; representative provider latency and spend remain dependent on production traffic and credentials |
| C11 | Large frontend bundles / P2 | High initial download/parse cost | Router, route imports, build | Raise warning threshold vs lazy route chunks with recovery; selected code splitting | **MITIGATED**; main JS fell from 957.91 kB/249.30 kB gzip to 262.68 kB/81.81 kB gzip and browser smoke passed; optional 3D chunk remains 863.07 kB/233.03 kB gzip |
| C12 | Test environment setup failures / P2 | DB and credentials assumed by default tests | pytest markers, CI services, dev setup | Mocks replacing integrations vs deterministic contract tests plus opt-in integrations; selected both without removing tests | **RESOLVED**; default run passes offline with 263 passed/10 explicitly deselected; PostgreSQL and live-model commands are documented separately |
| C13 | Lint failure / P3 | One import ordering issue | main.py | Focused import fix | **RESOLVED**; `python -m ruff check app tests` passes |

## Additional findings

The final acquisition-style red team reopened the project after the first green run and found the following material issues. All repository-fixable P1 items were remediated and retested:

- **RESOLVED:** PHI-bearing SSE traces now require a current user and case ownership; cross-tenant identifiers return 404. Tests cover 401, 404, and owner streaming.
- **RESOLVED:** localStorage demo hints can no longer replace a real API snapshot, assessment, or verdict. Synthetic overrides require both an explicit build flag and a response-level synthetic marker; a DENY-preservation regression passes.
- **RESOLVED:** review audit identity always comes from authenticated user data. Review/resume case locking, status, decision, and audit writes are transactional; spoof and rollback regressions pass.
- **RESOLVED:** synchronous decision/status/appeal/outbox persistence now uses one transaction. Worker lease loss cancels ongoing model execution and fencing still prevents stale commits.
- **RESOLVED:** metered `/llm/ping` and global queue-depth endpoints require admin authorization; provider failures are sanitized.
- **RESOLVED:** frontend tests are enforced in CI and manual Semgrep no longer suppresses findings.
- **RESOLVED:** the browser trace client now uses fetch streaming with a bearer header; query-parameter authentication was removed, while bounded retry and terminal-event handling remain.
- **RESOLVED:** unsupported uptime, customer, and decision-time claims were replaced or explicitly labeled as planning scenarios; PAS documentation now describes an asynchronous partial contract.
- **RESOLVED:** remaining executable-code comments no longer claim nonexistent PostgreSQL RLS enforcement.

## Strength amplification and novelty selection

Candidates (utility/fit/feasibility, 1-5): evidence-readiness manifest 5/5/5; criterion completeness gate 5/5/5; decision replay 4/5/3; policy freshness tracker 5/5/3; clinical validation importer 4/4/2; streaming recovery 4/5/3; cost dashboard expansion 3/4/3; model comparison UI 3/3/2; more agents 1/2/2; new disease workflows 2/2/2.

Select criterion completeness and an evidence-readiness manifest using current metadata. These deepen existing auditability and distinguish runnable functionality from externally validated capability. Do not add unrelated agents or domains. External validation cannot be invented in code.

## Verification and final audit

- `python -m pytest` -> 263 passed, 10 deselected (offline core).
- PostgreSQL marker run against an initialized local database -> 4 passed, 261 deselected.
- `python -m ruff check app tests` -> passed; `python -m compileall -q app` -> passed.
- `npm test -- --run` -> 5 files, 9 tests passed; `npm run build` -> passed.
- `npm audit --audit-level=moderate` -> 0 vulnerabilities.
- OncoTwin one-command journey -> all eight checks passed; stress suite -> 9/9 scenarios failed safe.
- Playwright runtime smoke -> landing rendered, health and capabilities loaded, accessible navigation present, no browser console errors with the API running. Shared probing produced one health and one capability request.
- Independent backend review found and corrected missing citation attestation, unauthenticated idempotency handling, liveness/readiness coupling, and false RLS claims. Post-fix focused review: 83 tests and seven HTTP resilience tests passed.
- Strict mypy remains a repository limitation: the scoped `app/models app/graph` run exposes 150 pre-existing errors across legacy generic annotations and package re-export declarations (the independent broader review reported 157). It was not hidden or added as a false-green CI gate.
- Backend dependency audit is externally blocked in this environment by PyPI TLS certificate verification. `pip check` also reflects conflicts in the shared global Python installation, so CI installs the pinned project into an isolated runner.
