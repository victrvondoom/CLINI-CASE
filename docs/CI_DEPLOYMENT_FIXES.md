# Deployment CI repairs — October 4, 2026

The GitHub run for `d9367ace` failed in PostgreSQL integration, README validation
and Supabase Preview. The earlier publication report covered offline checks;
it did not establish that these three hosted checks passed.

## Causes and corrections

| Failure | Underlying cause | Correction |
| --- | --- | --- |
| Three PostgreSQL tests | Two exact response assertions omitted new continuation fields; a case-identity test supplied an empty FHIR bundle, now correctly rejected with HTTP 422. | Assert the complete current response and use the existing synthetic oncology fixture. Add negative tests proving empty bundles never persist. |
| Provider-dependent attribution test | A hard-coded Claude model conflicts with a configured NVIDIA tenant allowlist. | Use the configured provider default while retaining the run-attribution assertions and production allowlist. |
| README section check | Legacy body-text grep expected headings removed during the Track 7 rewrite. | Validate the current 13 Markdown sections, substantive content, Mermaid diagrams and balanced fences; regression cases reject missing, empty and fenced headings. |
| Supabase Preview | The database recorded migration `20261004100608`, but GitHub had no corresponding file. Its 22 RLS targets also depended on tables previously created during backend startup. | Restore the same migration version and unchanged recorded RLS statements. Precede them with the existing backend's idempotent table/index definitions so a fresh database can replay the history. |

The database inspection was a read-only transaction against the explicitly
identified linked project. No remote schema, migration history, application data
or credentials were changed. The original RLS statement string has SHA-256
`3e12f0f9e4b1e1c7a754487e47b6c9e41ca39bb3b7177d78b96a9bce97c7d62a`.
Supabase compares migration filenames and remote history by timestamp; an
already recorded version is not a new pending migration. See the
[official migration-list contract](https://supabase.com/docs/reference/cli/supabase-migration-list).

## Verification

- Exact CI PostgreSQL selection against disposable PostgreSQL 16 with pgvector:
  **102 passed, 762 deselected**. Tests used synthetic data and no live models.
- Fresh Supabase replay and a second idempotent replay: **2 migrations,
  34 backend-owned tables, RLS enabled on every table, no public policies**.
- Access proof: the backend owner reads the synthetic organization seed; a
  non-owner role with SELECT grants and no RLS bypass sees zero organization rows.
- Current README contract, four validator regression cases, Ruff and whitespace
  checks passed.

The PostgreSQL CI job now repeats the fresh migration/RLS/access proof before its
API integration tests. The replay tool refuses remote hosts and requires an empty,
dedicated database whose name ends in `_ci`. Existing PDF intake validation,
mandatory human review for DENY, and worker/serverless continuation behavior remain
covered by the retained tests.

Hosted GitHub CI and Supabase Preview results are recorded on the repair commit's
checks; local verification alone does not establish a successful hosted deployment.
