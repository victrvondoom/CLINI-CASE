"""FastAPI dependencies for authenticated + role-gated routes."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_helpers import decode_access_token
from app.config import settings
from app.db import db

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Validate JWT and return the current user record.

    401 on missing/invalid token. 401 on user no longer existing.
    """
    token: str | None = creds.credentials if creds is not None else None

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
    except Exception as exc:
        if settings.ENVIRONMENT == "dev" and settings.AUTH_DBLESS_DEMO_ENABLED:
            # Only known demo identities may survive an actual database outage.
            # A successful lookup returning no row MUST revoke an old token.
            from app.api.auth import _DEMO_USERS_DBLESS

            demo = _DEMO_USERS_DBLESS.get(claims.get("email", ""))
            if demo and all(
                (
                    user_id == demo["id"],
                    claims.get("org") == demo["organization_id"],
                    claims.get("role") == demo["role"],
                )
            ):
                return {**demo, "email": claims["email"], "created_at": None}
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

    if row is None:
        raise HTTPException(status_code=401, detail="User no longer exists")

    return dict(row)


async def get_optional_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Like `get_current_user` but returns None instead of 401."""
    if creds is None:
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


_DEV_PLATFORM_ADMIN_ID = "user_demoadmin"  # the seeded demo administrator (dev only)


def platform_admin_user_ids() -> set[str]:
    """Platform operators, identified by server-generated user id.

    Deliberately NOT by e-mail: anyone can register an unclaimed address, whereas a user id is minted by the
    server and cannot be chosen by a caller."""
    ids = {i.strip() for i in settings.PLATFORM_ADMIN_USER_IDS.split(",") if i.strip()}
    if settings.ENVIRONMENT == "dev":
        ids.add(_DEV_PLATFORM_ADMIN_ID)
    return ids


def is_platform_admin(user: dict[str, Any]) -> bool:
    """Organisation admin AND on the operator allow-list. `admin` alone never crosses tenants."""
    return user.get("role") == "admin" and str(user.get("id", "")) in platform_admin_user_ids()


async def require_platform_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """403 unless the caller is a platform operator (cross-tenant surface)."""
    if not is_platform_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires platform administrator"
        )
    return user
