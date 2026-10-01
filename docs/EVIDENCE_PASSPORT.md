# Evidence Passport

A passport is a portable evidence package, not a clinical verdict. It contains scoped source payload/identifier, mapping version and reviewer, generated Bundle, validation report, evidence state, loss report, transfer acknowledgements and the record's revision manifest. Exposure passports include sample, citizen observation ID, consent/history, review, environmental task and retest links. A gateway passport carries the bound exposure ID/version; export the exposure passport to include current local consent/review rather than foreign claims.

Each repository save appends `previous_hash`, `current_hash`, `record_version`, timestamp, actor, action, object ID, reason and artifact SHA-256 hashes inside the same CAS transaction. PostgreSQL persists gateway artifacts separately and exposure records atomically. Optional `TRACK7_DEMO_DB` enables durable **synthetic-only** SQLite development storage. The default memory fallback is still explicitly volatile. Historical records without a chain start at their next recorded revision; earlier history is not retrospectively certified.

`POST /api/v1/interop/passport/{id}/verify-integrity` reports CHAIN_VALID, CHAIN_BROKEN, RECORD_MISSING or VERSION_MISMATCH. `GET /api/v1/interop/passport/{id}/export` exports the exchange passport. `GET /api/v1/onehealth/exposures/{id}/passport` exports the locally reviewed evidence passport. Authenticated reviewer/admin and organization scoping apply. Withdrawn consent blocks new exports and transfers; audit integrity remains inspectable.

Offline verification, without a server or network:

```sh
cd backend
python scripts/verify_passport.py evidence-passport.json
```

Exit 0 prints `VALID PASSPORT`; exit 1 prints `INTEGRITY FAILURE`. The package includes its Bundle, provenance, evidence/validation state and hash manifest; the verifier recomputes every hash and revision link. Canonical JSON sorts keys, uses compact separators and ASCII escaping, matching the existing FHIR digest utility.

This is tamper detection against an unchanged chain/head, **not** blockchain, a digital signature, an authenticated timestamp or proof of clinical truth. A database administrator able to rewrite every revision and hash can forge a chain. Exported heads should be retained independently; production needs signing and external anchoring. Previously downloaded files cannot be recalled. The receiver acknowledges withdrawal by hiding future reads and rejecting retransmission while retaining its historical receipt. Notification failure is audited and never restores local permission.
