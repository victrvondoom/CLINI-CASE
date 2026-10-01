# Track 7 verification - 2026-10-01

- Full configured backend regression run: 507 passed, 1 skipped, 104 integration/live tests deselected by repository defaults. After final gateway changes, the focused gateway + existing One Health suite passed 54 cases.
- Frontend: all 22 test files / 105 tests passed, including four new workbench tests. Typecheck and production build passed. Existing three.js chunk-size warning remains.
- New Python gateway code: Ruff and strict mypy (follow-imports=silent) passed.
- Real network demo: main application on port 8000, independent receiver process on port 8091, Vite on port 5173. Existing reviewer login used; synthetic-only memory fallback selected for this run.
- Measured golden path: 13 source fields; 12 mapped source fields; 0 decisions pending after explicit review; 10 generated and acknowledged FHIR resources; 3 validation check groups passed; 13 normalized sample fields preserved; Lab A return acknowledgement delivered.
- Invalid ppm unit: 1 check group failed; later groups skipped; transfer blocked.
- Browser exercised synthetic import, schema analysis, 13 explicit mapping decisions, generation, transfer acknowledgement, FHIR return and failure demo. No browser JavaScript errors reported. Screenshots inspected and stored as local QA artifacts under backend/.cache/interop (not source fixtures).
- Configured model path was requested. Existing gateway quota/audit database requirement prevented a live model invocation in synthetic memory mode. Failure was reported explicitly. Typed model suggestions and model failure handling are covered with deterministic provider fakes, not represented as live AI success.
- PostgreSQL artifact persistence and external clinical deployments were not exercised live. The simulator accepts synthetic data only; return currently forwards the original validated exchange and derives native lab fields rather than making new clinical conclusions.
- Local checkout origin is https://github.com/vsrupeshkumar/CLINICASE.git, differing from the requested victrvondoom/CLINI-CASE URL. No remote changes or pushes were made.
