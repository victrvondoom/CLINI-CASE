# CLINI-CASE Track 7: third-party FHIR R4 server check

**Status: RUN on 2026-10-02 against the public HAPI FHIR R4 test server.** This is an additional external FHIR R4
interoperability path. A generic FHIR server does **not** validate OAH profiles, so this result is **not** evidence of
OAH conformance and is **not** certification. OAH conformance evidence is the official validator run in
[VALIDATION.md](VALIDATION.md). The local demo never depends on this server: the check is optional and fails closed.

Machine-readable record: [`third-party-result.json`](third-party-result.json).

## What was done

| Item | Value |
|---|---|
| Endpoint | `https://hapi.fhir.org/baseR4` (public HAPI FHIR R4 test server, not written by this project) |
| Sent | a freshly generated **synthetic** `collection` Bundle, one POST to the base URL |
| Result of POST | HTTP 201, stored as `Bundle/76658` (742 ms) |
| Read back | `GET Bundle/76658`, HTTP 200 (179 ms) |
| Compared after read-back | sample, history, waterbody name, source observation id, provenance |
| Outcome | **passed**, 5 of 5 compared evidence fields preserved |
| Recorded | 2026-10-02T05:55:14.843156+00:00 |

The comparison reads meaning, not raw JSON: the server assigns its own resource ids and metadata, so byte equality is
not expected and is not used.

## What this does and does not show

- It shows an unmodified third-party FHIR R4 implementation accepted the Bundle and returned the evidence fields intact.
- It does **not** show the Bundle conforms to the OneAquaHealth guide (the server does not load or apply OAH profiles).
- A public test server is shared, may be reset at any time and may be unreachable. A failed or unavailable result is
  recorded as such and never turned into a pass.

## Safety properties (enforced in code and tests)

- Synthetic data only: the check refuses to send anything not flagged synthetic.
- The endpoint comes from server configuration (`EXTERNAL_FHIR_BASE_URL`), never from a request, so a caller cannot point
  the gateway at an arbitrary host.
- The POST is never retried (no duplicate resources); only the read-back is retried.
- Failures map to fixed categories (`unavailable`, `rejected`, `failed`) without echoing server text.
- The test suite exercises all of this with a mocked transport; `pytest` needs no internet.

## Reproduce

```powershell
cd backend
python scripts/third_party_fhir_check.py --out ../docs/track7/third-party-result.json
```

Behind an HTTPS-inspecting proxy or antivirus, add `--system-trust` (or set `EXTERNAL_FHIR_SYSTEM_TRUST=true`) so Python
uses the operating system certificate store. Certificate verification is never disabled.

In the application, the same check is the optional **Run third-party FHIR check** action on the Verify stage of
`/journey`.
