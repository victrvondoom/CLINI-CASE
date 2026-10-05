# Service integration setup

These integrations are organized around the existing workflow: observations and context → governed FHIR exchange → optional clinical launch and follow-up. No commercial API keys are needed for the listed open services, but SMART launch needs EHR registration and Web Push needs server keys and user permission.

| Service | Workflow use | Application entry | Setup and boundary |
|---|---|---|---|
| Open-Meteo | Timestamped weather and rainfall context | `/oah-bridge` | Backend fetch, cached/degraded response and attribution; no API key. Weather remains context and is not joined to the separate `/interop` job. |
| MapLibre GL JS + OpenFreeMap | Street basemap with observation markers | `/aquahealth/map` | No map API key. Tile/style requests go to OpenFreeMap and attribution is shown. Existing 3D globe and offline relative plot remain alternate views. |
| HAPI FHIR R4 | External FHIR create/read-back proof | `/interop` → optional HAPI check | Synthetic Bundle only. `docker-compose.track7.yml` includes a loopback-only HAPI instance at `http://localhost:18080/fhir`; the default backend config can also target the public HAPI test server, which may retain submitted resources. HAPI acceptance is not OAH profile validation. |
| OneAquaHealth FHIR IG | Profile/code-system references and local contract validation | OAH Bridge and Track 7 validator | Pinned package artifacts and checks are local. The IG is not an API service and has no API key. Current checks are not official HL7/OAH certification. |
| MCP | Exposes existing CLINI-CASE tools to MCP clients | `/mcp` | Existing JSON-RPC endpoint. Configure client URL and existing authentication/network policy; no separate MCP API key is created here. |
| SMART on FHIR | Optional EHR launch and narrowly scoped FHIR access | `/smart-on-fhir` | Configure build-time `VITE_SMART_FHIR_BASE`, public `VITE_SMART_CLIENT_ID`, and exact registered redirect URI. Requires a real EHR/sandbox app registration. Uses authorization code + PKCE S256, no client secret, minimal read scope, and keeps access tokens in page memory. Token refresh is not implemented. |
| VAPID / Web Push | Explicit, generic follow-up notification check | `/notifications` | Run `python backend/scripts/generate_web_push_keys.py` once. Set all values in backend secrets. Public key is served to the signed-in browser; private key and AES-GCM encryption key remain backend-only. Requires HTTPS (except localhost), browser permission, and an explicit user test action. No automatic clinical alerts are sent. |

## Local Track 7 stack

Set the existing `TRACK7_POSTGRES_PASSWORD` and `INTEROP_RECEIVER_TOKEN`, then run:

```powershell
docker compose -f docker-compose.track7.yml up --build
```

The stack binds CLINI-CASE, the independent receiver, and HAPI to loopback. HAPI uses its demonstration storage configuration; submit synthetic data only. The external check creates a Bundle on the HAPI server and reads it back, so resources remain on that server until its storage is reset.

## Browser and deployment setup

- OpenFreeMap tiles need network access in the browser. The bundled globe works without tile access.
- For SMART, register the exact production redirect URI with the EHR authorization server. Client IDs are public identifiers; never put a client secret in a `VITE_` variable.
- For push, use a stable VAPID keypair and encryption key. Rotating `WEB_PUSH_ENCRYPTION_KEY` makes stored subscriptions unreadable, so users must subscribe again.
- Configure VAPID secrets on the backend and SMART `VITE_` values in the frontend build environment. Neither feature is production-connected until the corresponding service registration and deployment values exist.
