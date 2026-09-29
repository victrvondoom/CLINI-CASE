# Testing ClinCase

ClinCase separates deterministic checks from tests that depend on external
infrastructure. A plain `pytest` run is safe offline and is the default backend
gate in CI.

## Test groups

| Group | Pytest selection | External requirement | Runs in CI |
|---|---|---|---|
| Core | `not integration and not live` | None | Every pull request and push to `main` |
| Integration | `integration and not live` | PostgreSQL with the pgvector extension and `backend/db/schema.sql` | Every pull request and push to `main` |
| Live model contracts | `live and not integration` | Configured model-provider credentials; calls may be metered | Explicit local run only |
| All | no marker filter | All requirements above | Explicit local run only |

Tests must carry `@pytest.mark.integration` when they require a networked
service. Add the more specific marker, such as `@pytest.mark.postgres`, as
well. Tests that call a real model provider must carry `@pytest.mark.live`.
Pure unit tests and in-process ASGI tests need no marker.

## Commands

From the repository root:

```bash
make backend.install
make backend.test
make backend.lint
make frontend.install
make frontend.build
```

To exercise PostgreSQL-backed API contracts locally, initialize the schema and
point the process at the database before running the integration target:

```bash
docker compose up -d postgres
make db.init
export DATABASE_URL=postgresql://clincase:clincase@localhost:15432/clincase
make backend.test.integration
```

PowerShell uses this environment-variable form:

```powershell
docker compose up -d postgres
make db.init
$env:DATABASE_URL = "postgresql://clincase:clincase@localhost:15432/clincase"
make backend.test.integration
```

Live model contract tests intentionally fail fast when credentials are absent.
Configure the provider selected by `LLM_PROVIDER` (for example,
`OPENROUTER_API_KEY`) and then run:

```bash
make backend.test.live
```

Use `make backend.test.all` only when both PostgreSQL and the selected model
provider are available. The default test command never substitutes mocks for
these boundaries; it excludes them explicitly and reports deselected tests.

## CI behavior

The backend CI job installs the same `dev` extra used locally, runs Ruff as a
blocking check, and executes the offline core suite. A separate integration
job starts `pgvector/pgvector:pg16`, applies `backend/db/schema.sql` with
`ON_ERROR_STOP`, and runs the PostgreSQL marker group. The dedicated OncoTwin
job additionally runs its deterministic journey and stress scenarios.

Direct dependencies and development tools are pinned in
`backend/pyproject.toml`. Transitive dependencies are still resolved by pip at
install time; changes to the dependency graph therefore require a full CI run.
