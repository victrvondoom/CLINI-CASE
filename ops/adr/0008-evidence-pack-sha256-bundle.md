# ADR-0008 — Evidence Pack as a single tamper-evident SHA-256 JSON bundle

## Status
Accepted · 2026-04-28

## Context

CMS-0057-F § IV.D requires every adverse-determination decision to be reproducible for 7 years. A CMS auditor (or state AI-denial-law auditor) may request a single case's full evidence and expects to receive it within 12 seconds.

What "full evidence" means for a single case:

- The case row (FHIR bundle, physician note, treatment, payer).
- The persisted decision row (verdict, rationale, citations, confidence).
- The drafted appeal letter (if DENY path).
- Every `agent_runs` row (input, output, model_id, tokens, latency, error) — one per agent invocation.
- Every `reviewer_actions` row (HITL signoff trail).
- Live CMS-0057-F + state-AI-law clause-by-clause scorecard.
- Live business-value computation (per-case ROI vs $1,500 manual baseline).
- The most recent TriZetto AI Gateway envelope (Facets + QNXT events).
- Pointers to the model card + Foundry manifest in effect at decision time.

## Decision

**Single tamper-evident SHA-256 JSON bundle**, served at `GET /api/v1/cases/{id}/evidence-pack`.

Implementation in `backend/app/api/evidence_pack.py`:

1. The endpoint walks the per-case data model (case + decision + appeal + agent_runs + reviewer_actions + compliance + business_value + trizetto_envelope + version-pointers).
2. Computes a deterministic SHA-256 over the canonical-JSON serialization of the bundle (sorted keys, UTF-8).
3. Adds the hash as `bundle_sha256` and returns the JSON.
4. Frontend `EvidencePackButton` triggers a JSON file download with the timestamp in the filename.

A third party can rehash any bundle (excluding the `bundle_sha256` field itself) and verify integrity.

## Consequences

**Positive**
- **One artifact.** Auditor saves one file; reproduces a decision without manual table joins.
- **Tamper-evident.** Any post-hoc edit to the bundle invalidates `bundle_sha256` — exposes forgery.
- **Off-the-shelf verifiable.** No proprietary verification tool; any auditor can `python -c "import hashlib, json; ..."`.
- **Live, not snapshot.** Compliance scorecard + business value + Foundry manifest are computed at request time — the bundle reflects the system's *current* posture, not a stale precomputed dump.
- **Closes the audit-readiness loop.** Round-trip "regulator request → bundle download → verifier rehash" is fully documented in `ops/sre/RUNBOOK.md` § INC-004.

**Negative**
- **Endpoint is read-heavy.** Each call hits 4-5 tables + computes 2 live scorecards. At rare audit-request volume (a handful per quarter) this is fine; if a customer wanted to bulk-export the bundle for every case daily, we'd add an async S3 batch path.
- **JSON size scales with `agent_runs` rows** (up to ~50 KB / case). Acceptable for download; would be too large for inline DB storage.

**Neutral**
- The bundle does not include raw `streaming.publish` events. Reviewer-visible trace events are derived from `agent_runs` rows, so the bundle is sufficient for reproduction.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Database query on demand | Auditor doesn't want SQL access. They want a file. |
| PDF report | Tamper-evidence is unclear for PDF without a PKI signing infrastructure (out of scope for hackathon). JSON + SHA-256 is verifiable with one python one-liner. |
| Cryptographic signing (PKCS#7) | Worth doing post-pilot. SHA-256 is the right starting bar; signing is additive. |
| External audit vendor's tooling | Many customers already have internal compliance tooling; they want raw evidence they can ingest. Vendor-specific format would lock them out. |

## References

- CMS-0057-F § IV.D retention requirement: https://www.cms.gov/newsroom/fact-sheets/cms-interoperability-prior-authorization-final-rule-cms-0057-f
- Implementation: `backend/app/api/evidence_pack.py`
- Verification one-liner published in `ops/sre/RUNBOOK.md` § INC-004
- Live endpoint: `GET /api/v1/cases/{case_id}/evidence-pack`
