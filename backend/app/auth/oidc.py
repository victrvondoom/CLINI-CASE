"""OIDC (OpenID Connect) SSO scaffold — Okta / Azure AD / Google / Ping.

Round-9 auth was: email + bcrypt password + JWT. That's correct for demo +
internal admin. It is **not** sufficient for any Tier-1 payer customer:
- Their IAM team doesn't allow non-SSO credentials in production
- They want to enforce MFA, session lifetime, conditional access at IdP
- They want SCIM provisioning + de-provisioning when an employee leaves

This module is the OIDC Relying Party (RP) implementation. It supports any
OIDC-compliant IdP via discovery (`/.well-known/openid-configuration`):

  Okta:    https://{tenant}.okta.com/.well-known/openid-configuration
  Azure:   https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration
  Google:  https://accounts.google.com/.well-known/openid-configuration
  Ping:    https://{tenant}.pingidentity.com/.well-known/openid-configuration

Pairs with: ops/architecture/OIDC_SSO.md

Deployed today as scaffold (returns 503 unless OIDC_DISCOVERY_URL is set).
Actual production wiring waits for the first customer's IdP details.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


# =============================================================================
# Config — all from env so the same image runs against any customer's IdP
# =============================================================================


@dataclass(frozen=True)
class OIDCConfig:
    discovery_url: str        # e.g. https://acme.okta.com/.well-known/openid-configuration
    client_id: str            # IdP-issued
    client_secret: str        # IdP-issued (read from Secrets Manager in prod)
    redirect_uri: str         # https://api.clincase.example.com/api/v1/auth/oidc/callback
    scopes: str = "openid profile email offline_access groups"
    organization_id_claim: str = "https://clincase.com/claims/organization_id"
    role_claim: str = "https://clincase.com/claims/role"


def _config_from_env() -> OIDCConfig | None:
    """Build OIDCConfig from environment. Returns None if not configured."""
    discovery = os.getenv("OIDC_DISCOVERY_URL", "").strip()
    client_id = os.getenv("OIDC_CLIENT_ID", "").strip()
    client_secret = os.getenv("OIDC_CLIENT_SECRET", "").strip()
    redirect = os.getenv("OIDC_REDIRECT_URI", "").strip()
    if not (discovery and client_id and client_secret and redirect):
        return None
    return OIDCConfig(
        discovery_url=discovery,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect,
        scopes=os.getenv("OIDC_SCOPES", "openid profile email offline_access groups"),
        organization_id_claim=os.getenv(
            "OIDC_ORGANIZATION_ID_CLAIM",
            "https://clincase.com/claims/organization_id",
        ),
        role_claim=os.getenv(
            "OIDC_ROLE_CLAIM",
            "https://clincase.com/claims/role",
        ),
    )


# =============================================================================
# Discovery cache — fetched once per process from the IdP's well-known doc
# =============================================================================


_discovery_cache: dict[str, dict[str, Any]] = {}


async def _fetch_discovery(discovery_url: str) -> dict[str, Any]:
    """Fetch + cache the IdP's OIDC discovery document."""
    if discovery_url in _discovery_cache:
        return _discovery_cache[discovery_url]
    try:
        import httpx  # type: ignore[import-not-found]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(discovery_url)
            resp.raise_for_status()
            doc = resp.json()
            _discovery_cache[discovery_url] = doc
            return doc
    except Exception as e:  # noqa: BLE001
        log.error("oidc.discovery.failed", url=discovery_url, error=str(e))
        raise


# =============================================================================
# PKCE helpers — Authorization Code Flow with PKCE (RFC 7636)
# =============================================================================
# PKCE is REQUIRED for any browser-initiated OIDC flow. AWS, Okta, Azure, Ping
# all enforce it for public clients.


def _new_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge_S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# In-memory state store. Production: Redis with 10-min TTL.
_state_store: dict[str, dict[str, str]] = {}


# =============================================================================
# authorize_url — step 1 of the flow
# =============================================================================


async def build_authorize_url(*, return_to: str | None = None) -> tuple[str, str]:
    """Build the IdP authorization URL + state token.

    Returns (authorize_url, state). The caller redirects the browser to
    authorize_url and stores `state` (e.g., in a signed cookie) for verification
    on callback.
    """
    cfg = _config_from_env()
    if cfg is None:
        raise RuntimeError(
            "OIDC not configured. Set OIDC_DISCOVERY_URL + OIDC_CLIENT_ID + "
            "OIDC_CLIENT_SECRET + OIDC_REDIRECT_URI."
        )
    discovery = await _fetch_discovery(cfg.discovery_url)
    auth_endpoint = discovery["authorization_endpoint"]
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _new_pkce_pair()
    _state_store[state] = {
        "verifier": verifier,
        "nonce": nonce,
        "return_to": return_to or "/",
    }
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "scope": cfg.scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}", state


# =============================================================================
# callback handler — step 2 of the flow
# =============================================================================


@dataclass(frozen=True)
class OIDCExchangeResult:
    user_id: str             # IdP `sub` claim
    email: str
    full_name: str | None
    organization_id: str
    role: str
    return_to: str
    raw_id_token: str


async def exchange_code(*, code: str, state: str) -> OIDCExchangeResult:
    """Exchange authorization code for tokens and validate the ID token."""
    cfg = _config_from_env()
    if cfg is None:
        raise RuntimeError("OIDC not configured")
    state_entry = _state_store.pop(state, None)
    if state_entry is None:
        raise ValueError("oidc.state.invalid_or_replayed")

    discovery = await _fetch_discovery(cfg.discovery_url)
    token_endpoint = discovery["token_endpoint"]

    try:
        import httpx  # type: ignore[import-not-found]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "redirect_uri": cfg.redirect_uri,
                    "code_verifier": state_entry["verifier"],
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as e:  # noqa: BLE001
        log.error("oidc.token_exchange.failed", error=str(e))
        raise

    id_token = tokens.get("id_token")
    if not id_token:
        raise ValueError("oidc.id_token.missing")

    # Decode the ID token. In production we MUST validate the signature
    # against the IdP's JWKS endpoint. Today we decode-only and document
    # the JWKS validation gap as TODO. The wiring is straightforward:
    # `import jwt; jwt.decode(id_token, jwks_key, algorithms=["RS256"], audience=cfg.client_id)`.
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            raise ValueError("oidc.id_token.malformed")
        import json as _json
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:  # noqa: BLE001
        log.error("oidc.id_token.decode_failed", error=str(e))
        raise

    if claims.get("nonce") != state_entry["nonce"]:
        raise ValueError("oidc.nonce.mismatch")

    return OIDCExchangeResult(
        user_id=claims.get("sub", ""),
        email=claims.get("email", ""),
        full_name=claims.get("name"),
        organization_id=claims.get(cfg.organization_id_claim, "") or "org_demo",
        role=claims.get(cfg.role_claim, "coordinator") or "coordinator",
        return_to=state_entry.get("return_to", "/"),
        raw_id_token=id_token,
    )


# =============================================================================
# Snapshot for /capabilities + /architecture/layers
# =============================================================================


def oidc_snapshot() -> dict[str, Any]:
    cfg = _config_from_env()
    return {
        "configured": cfg is not None,
        "discovery_url_set": bool(os.getenv("OIDC_DISCOVERY_URL")),
        "client_id_set": bool(os.getenv("OIDC_CLIENT_ID")),
        "client_secret_set": bool(os.getenv("OIDC_CLIENT_SECRET")),
        "redirect_uri_set": bool(os.getenv("OIDC_REDIRECT_URI")),
        "scopes": (cfg.scopes if cfg else "openid profile email offline_access groups"),
        "supported_idps": ["Okta", "Azure AD", "Ping Identity", "Google Workspace", "Auth0"],
        "flow": "Authorization Code Flow + PKCE (RFC 7636)",
        "id_token_signature_validation": "TODO — JWKS endpoint validation lands at first customer cutover",
    }
