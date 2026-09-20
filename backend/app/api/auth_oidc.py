"""OIDC SSO endpoints.

  GET  /api/v1/auth/oidc/login     → redirects browser to IdP authorize_url
  GET  /api/v1/auth/oidc/callback  → exchanges code, mints ClinCase JWT, redirects to UI
  GET  /api/v1/auth/oidc/status    → unauth-readable; reports whether OIDC is configured
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.auth import create_access_token
from app.auth.oidc import build_authorize_url, exchange_code, oidc_snapshot
from app.db import db

router = APIRouter(prefix="/auth/oidc", tags=["auth"])


@router.get("/status")
async def oidc_status() -> dict[str, Any]:
    """Unauthenticated. Frontend uses this to decide whether to show
    'Sign in with SSO' button vs the password form."""
    return oidc_snapshot()


@router.get("/login")
async def oidc_login(return_to: str | None = Query(default="/")) -> RedirectResponse:
    """Step 1 — redirect to the IdP's authorize endpoint."""
    try:
        url, _state = await build_authorize_url(return_to=return_to)
    except RuntimeError as e:
        # OIDC not configured
        raise HTTPException(status_code=503, detail=str(e))
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Step 2 — exchange the code, upsert the user, mint ClinCase JWT."""
    try:
        result = await exchange_code(code=code, state=state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Idempotent upsert into users by email.
    user_id = f"oidc_{result.user_id[:32]}"
    try:
        await db.execute(
            """
            INSERT INTO users (id, email, password_hash, full_name, organization_id, role)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (email) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                organization_id = EXCLUDED.organization_id,
                role = EXCLUDED.role,
                last_login_at = NOW()
            """,
            user_id,
            result.email,
            "OIDC_PROVISIONED",  # placeholder; password login disabled for OIDC users
            result.full_name,
            result.organization_id,
            result.role,
        )
    except Exception:  # noqa: BLE001
        # If users table doesn't exist yet (fresh dev DB), still mint a session;
        # the case-run path doesn't strictly require the row.
        pass

    token = create_access_token(
        user_id=user_id,
        email=result.email,
        organization_id=result.organization_id,
        role=result.role,
    )

    # Redirect to the frontend with the token in the URL fragment so it
    # never hits a server log. Frontend pulls it from window.location.hash.
    return_url = result.return_to or "/"
    redirect = f"{return_url}#access_token={token}&token_type=Bearer"
    return RedirectResponse(url=redirect, status_code=302)
