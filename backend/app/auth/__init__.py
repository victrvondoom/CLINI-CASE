"""Authentication + authorization for ClinCase.

JWT-based session tokens, bcrypt password hashing, organization-scoped
multi-tenancy, and role-based access control (coordinator/reviewer/admin).

Public surface:
- `get_current_user`        — FastAPI dependency for authenticated routes
- `get_optional_user`       — same but returns None instead of 401
- `require_role(*roles)`    — role-gated dependency factory
- `hash_password`/`verify_password`
- `create_access_token`/`decode_access_token`
"""
from app.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_role,
)
from app.auth.jwt_helpers import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

__all__ = [
    "get_current_user",
    "get_optional_user",
    "require_role",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
]
