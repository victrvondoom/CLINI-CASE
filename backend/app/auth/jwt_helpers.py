"""Pure-function JWT + password helpers. No FastAPI imports here so this
module is safely usable from scripts / tests.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time check that the plaintext matches the stored hash."""
    try:
        return _pwd_ctx.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    role: str,
    email: str,
    full_name: str | None = None,
    organization_name: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT carrying the user's identity + tenant + role.

    `full_name`/`organization_name` are embedded so DB-less deploys can
    reconstruct a correct display name from the token alone (see
    `get_current_user`'s fallback path) instead of defaulting to the email.
    """
    expires = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES,
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "email": email,
        "full_name": full_name,
        "org_name": organization_name,
        "exp": expires,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode + verify a JWT. Returns the claims dict or None on any error."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
