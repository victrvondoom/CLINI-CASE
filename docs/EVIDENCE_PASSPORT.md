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

## Optional Ed25519 demo-system signature

The current exporter can additionally sign the passport's deterministic manifest using an
environment-provided `PASSPORT_SIGNING_KEY` (a base64-encoded 32-byte Ed25519 seed). The signature
binds the record identity, version, chain head and recomputed artifact manifest. Passports carry
the algorithm, key identifier, payload hash and signature. An empty or invalid key produces an
unsigned export; the application never substitutes a fabricated signature.

`GET /api/v1/interop/passport-signing` reports signing availability without returning a key.
`POST /api/v1/interop/passport/verify` recomputes the hash chain and signed manifest using the
trusted local key. Its overall result is `VERIFIED`, `HASH_CHAIN_ONLY` or `FAILED`, with separate
signature states including `SIGNATURE_VALID`, `UNSIGNED`, `UNVERIFIABLE`, `KEY_MISMATCH` and
`SIGNATURE_INVALID`. The offline CLI above checks hashes and revision links; its `VALID PASSPORT`
message alone does **not** establish signature verification or signer identity.

The signer is explicitly **CLINI-CASE demo signer**. This is a demo-system signature, not a
laboratory, clinician, government or third-party attestation. The local Track 7 launcher can
provide a persisted private demo key; deployment signing is enabled only when configured.
Do not publish that seed or treat a key embedded in an untrusted package as an authority.

The hash chain provides tamper detection against an unchanged chain/head. A database administrator
able to rewrite every revision and hash can forge an **unsigned** chain; an independently trusted
signing key provides an additional check on signed content. Neither mechanism proves laboratory
truth, clinical truth, an authenticated timestamp or an externally anchored ledger. Production
would need institutional identity, key custody/rotation and an independently retained trust anchor.
Previously downloaded files cannot be recalled. The receiver acknowledges withdrawal by hiding
future reads and rejecting retransmission while retaining its historical receipt. Notification
failure is audited and never restores local permission.

Current implementation: `backend/app/onehealth/passport.py`; recorded signing and tamper evidence:
[Track 7 final review, 2026-10-02](track7/FINAL_REVIEW.md).
