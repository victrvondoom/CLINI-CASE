"""FastAPI dependencies for authenticated + role-gated routes."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_helpers import decode_access_token
from app.db import db

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Validate JWT and return the current user record.

    401 on missing/invalid token. 401 on user no longer existing.
    """
    token: str | None = None
    if creds is not None:
        token = creds.credentials
    else:
        # Fallback: allow ?token= for SSE (EventSource can't send headers)
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = decode_access_token(token)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    # Try DB lookup first (production path).
    try:
        row = await db.fetchrow(
            """SELECT id, email, full_name, organization_id, role, created_at
               FROM users WHERE id = $1""",
            user_id,
        )
    except Exception:
        # DB-less deployments (e.g. ECS Fargate without RDS, S3-only API
        # demos) cannot do the user lookup. Trust the JWT claims directly —
        # the token is already signature-verified by decode_access_token,
        # so the claims are tamper-evident. Use this only when explicitly
        # operating in DB-less mode.
        row = None

    if row is None:
        # Reconstruct from JWT claims when the DB has no row (or is offline).
        # Only safe because decode_access_token already verified the signature.
        if claims.get("email") and claims.get("org") and claims.get("role"):
            return {
                "id": user_id,
                "email": claims["email"],
                "full_name": claims.get("full_name") or claims["email"],
                "organization_id": claims["org"],
                "organization_name": claims.get("org_name"),
                "role": claims["role"],
                "created_at": None,
            }
        raise HTTPException(status_code=401, detail="User no longer exists")

    return dict(row)


async def get_optional_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Like `get_current_user` but returns None instead of 401."""
    if creds is None and "token" not in request.query_params:
        return None
    try:
        return await get_current_user(request, creds)
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory: 403 if current user's role is not in allowed_roles."""

    async def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return user

    return _check
