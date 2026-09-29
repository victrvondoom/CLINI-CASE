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
| C01 | Dropped criteria -> approval / P1 | Incomplete model output silently truncated by min(lengths) | Necessity schema, verdict, graph | Pad missing values vs reject incomplete output; select fail-closed validation and conservative review | Investigating; malformed-output regression; verdict compatibility; pending independent review |
| C02 | Raw scan sent before redaction / P1 | Metadata removal mistaken for visual PHI removal | Intake, OCR engines, cloud clients | Local pixel redaction vs explicit governed cloud opt-in with local fallback; select honest boundary and safe default | Investigating; outbound-call denial tests; OCR fallback compatibility; pending review |
| C03 | Limited text/FHIR PHI protection / P1 | Regex incomplete and structured input may bypass sanitizer | Privacy, extractor, receipts | Claim universal de-identification vs structural minimization and qualified receipts; select minimization and honest guarantees | Investigating; synthetic identifier tests; clinical field preservation; pending review |
| C04 | Deleted-user token fallback / P1 | Signed token treated as current authorization when record absent | Auth, config | Remove demo support vs explicitly isolate outage demo mode; select fail-closed normal auth | Investigating; missing user/outage/wrong password tests; demo compatibility; pending review |
| C05 | Synthetic-only OncoTwin validation / P1 | Synthetic benchmark cannot establish clinical validity | Model artifacts, research API/UI | Fabricate performance vs explicit machine-readable evidence limits; select visible evidence provenance | External real-patient validation blocked; strengthen repository guardrails; pending review |
| C06 | Demo guideline/policy data / P1 | Emulated corpus may be mistaken for licensed current evidence | Guideline APIs, policy retrieval, UI | Replace with unavailable licensed feed vs expose provenance and fail-safe limitations; select provenance | Licensed/current corpus external; repository mitigation pending |
| C07 | Partial FHIR/payer integration / P1 | PAS shape overstates conformance; submission may claim queued without queue job | FHIR API, jobs, DB, tests | Implement full external standard vs repair supported async contract and label remaining gaps; select tested local contract | Investigating; API/queue transaction tests; preserve route contracts; pending review |
| C08 | Broad maintenance surface / P2 | Many domains and infrastructure paths exceed verification | Architecture, docs, CI | Rewrite/remove domains vs isolate change scope and strengthen quality gates; select incremental boundaries | Investigating; cross-domain regression; no feature removals |
| C09 | Incomplete CI and advisory lint / P2 | Green CI can miss core backend failures | Workflows, test fixtures, dependencies | Skip external tests silently vs explicitly separate offline/DB/live suites; select explicit tiers and blocking lint | Investigating; offline suite and DB contracts; external tests preserved |
| C10 | Unmeasured model latency/cost / P2 | Multiple provider calls and retries lack realistic workload evidence | Agent budgets, traces, docs | Claim speed vs report measured local behavior and external benchmark requirements | Investigating; budget failure tests; real provider benchmarks externally blocked |
| C11 | Large frontend bundles / P2 | High initial download/parse cost | Router, route imports, build | Raise warning threshold vs lazy route chunks with recovery; select code splitting | Investigating; measured production build and runtime checks; preserve routes |
| C12 | Test environment setup failures / P2 | DB and credentials assumed by default tests | pytest markers, CI services, dev setup | Mocks replacing integrations vs deterministic contract tests plus opt-in integrations; select both without removing tests | Investigating; documented explicit commands and fixture teardown |
| C13 | Lint failure / P3 | One import ordering issue | main.py | Focused import fix | Pending; ruff check app |

## Additional findings

Tracked as discovered; independent reviewers may reopen any item. Completion requires evidence, not a status label.

## Strength amplification and novelty selection

Candidates (utility/fit/feasibility, 1-5): evidence-readiness manifest 5/5/5; criterion completeness gate 5/5/5; decision replay 4/5/3; policy freshness tracker 5/5/3; clinical validation importer 4/4/2; streaming recovery 4/5/3; cost dashboard expansion 3/4/3; model comparison UI 3/3/2; more agents 1/2/2; new disease workflows 2/2/2.

Select criterion completeness and an evidence-readiness manifest using current metadata. These deepen existing auditability and distinguish runnable functionality from externally validated capability. Do not add unrelated agents or domains. External validation cannot be invented in code.

## Verification and final audit

Pending implementation. Record exact commands, results, reviewer findings and unresolved external dependencies here before closing the work.
