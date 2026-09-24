# ClinCase — k6 load test scenarios

**Status: apply-ready.** Committed scenarios run against staging on every
PR via the `loadtest-on-pr.yml` workflow, with regression detection.

## Why "tests in a doc" wasn't enough

Round-9 had `LOAD_TEST_RESULTS.md` describing what we tested. That's a
report, not a test. Production-grade requires **load tests as code**:
committed in git, runnable on demand, with regression detection on every PR.

## Layout

```
ops/loadtest/
├── README.md                         # this file
├── scenarios/
│   ├── healthz_burst.js              # /healthz/deep at 1000 RPS
│   ├── case_create_steady.js         # POST /cases at 50 RPS sustained
│   ├── case_run_async_burst.js       # POST /cases/{id}/run-async at 100 RPS burst
│   ├── architecture_layers.js        # GET /architecture/layers (the live descriptor)
│   ├── stream_completion.js          # POST /llm/stream (SSE streaming)
│   └── full_journey.js               # end-to-end: login → create → run → poll
└── lib/
    └── auth.js                        # shared JWT minting helper
```

## Run locally

```bash
brew install k6     # or: docker pull grafana/k6

# Quick scenario
k6 run ops/loadtest/scenarios/healthz_burst.js \
  --vus 100 --duration 30s

# Full PR-grade run
k6 run ops/loadtest/scenarios/case_create_steady.js \
  -e API_BASE=https://staging-api.clincase.example.com \
  -e USER=demo@clincase.health \
  -e PASS=clincase2026
```

## Regression budgets per scenario

| Scenario | p95 latency | Error rate | RPS sustainable |
|---|---|---|---|
| `healthz_burst` | < 50ms | < 0.1% | 1000 |
| `case_create_steady` | < 250ms | < 1% | 50 |
| `case_run_async_burst` | < 200ms | < 1% | 100 (burst 30s) |
| `architecture_layers` | < 200ms | < 0.5% | 50 |
| `stream_completion` | first-token < 600ms | < 2% | 20 |
| `full_journey` | end-to-end < 90s | < 1% | 10 concurrent users |

PR check fails when any threshold is breached.

## CI integration

`.github/workflows/loadtest-on-pr.yml`:
- Triggered by PRs labeled `loadtest`
- Spins up the staging environment
- Runs all scenarios
- Comments k6 summary back on the PR

## What this catches that unit tests don't

- Connection pool exhaustion under sustained load (PgBouncer matters)
- Memory leaks in long-running workers
- Bedrock TPM ceiling discovery
- Circuit breaker thrashing
- KEDA scale-up reaction time
- Linkerd proxy CPU under traffic
- Real downstream latency tail percentiles

## Sources

- k6 — https://k6.io/
- k6 thresholds — https://k6.io/docs/using-k6/thresholds/
- Grafana k6 GitHub Action — https://github.com/grafana/k6-action
