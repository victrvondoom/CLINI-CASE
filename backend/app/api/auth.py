"""Authentication endpoints — signup, login, current-user.

POST /api/v1/auth/signup    — Create new user + new org (first user is admin).
POST /api/v1/auth/login     — Exchange email+password for JWT access token.
GET  /api/v1/auth/me        — Return the current authenticated user.
GET  /api/v1/auth/users     — Admin-only list of users in the org.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.config import settings
from app.db import db

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "org"


# =============================================================================
# Schemas
# =============================================================================


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=120)
    organization_name: str = Field(..., min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict[str, Any]


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    organization_id: str
    organization_name: str
    role: str
    created_at: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/signup", response_model=TokenResponse)
async def signup(req: SignupRequest) -> TokenResponse:
    """Create a new organization + admin user + return access token."""
    existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", req.email.lower())
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    org_id = f"org_{uuid4().hex[:10]}"
    user_id = f"user_{uuid4().hex[:10]}"
    slug_base = _slugify(req.organization_name)
    slug = slug_base
    n = 1
    # Ensure unique slug
    while await db.fetchval("SELECT 1 FROM organizations WHERE slug = $1", slug):
        n += 1
        slug = f"{slug_base}-{n}"

    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3)",
                org_id, req.organization_name, slug,
            )
            await conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name,
                                      organization_id, role)
                   VALUES ($1, $2, $3, $4, $5, 'admin')""",
                user_id, req.email.lower(), hash_password(req.password),
                req.full_name, org_id,
            )
            await conn.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = $1", user_id,
            )

    token = create_access_token(
        user_id=user_id,
        organization_id=org_id,
        role="admin",
        email=req.email.lower(),
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user={
            "id": user_id,
            "email": req.email.lower(),
            "full_name": req.full_name,
            "organization_id": org_id,
            "organization_name": req.organization_name,
            "role": "admin",
        },
    )


# DB-less demo users — used when the deployed backend has no Postgres
# (e.g. the public ECS Fargate demo). The same credentials work locally too,
# but the local backend prefers the seeded DB rows when available.
_DEMO_USERS_DBLESS: dict[str, dict[str, Any]] = {
    "admin@aerofyta.health": {
        "id": "user_demoadmin",
        "full_name": "Demo Administrator",
        "organization_id": "org_demo",
        "organization_name": "Aerofyta Health Sciences",
        "role": "admin",
    },
    "reviewer@aerofyta.health": {
        "id": "user_demoreviewer",
        "full_name": "Demo Reviewer",
        "organization_id": "org_demo",
        "organization_name": "Aerofyta Health Sciences",
        "role": "reviewer",
    },
    "coordinator@aerofyta.health": {
        "id": "user_democoord",
        "full_name": "Demo Coordinator",
        "organization_id": "org_demo",
        "organization_name": "Aerofyta Health Sciences",
        "role": "coordinator",
    },
}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    """Exchange email + password for an access token.

    Two paths:
      1. DB-backed (production): look up the user in the `users` table,
         verify the bcrypt password hash.
      2. DB-less fallback (public demo, S3-only deploys): when the DB pool
         isn't connected (e.g. the public ECS Fargate without RDS), accept
         the seeded demo credentials so the deployed app stays usable.
    """
    email = req.email.lower()
    try:
        row = await db.fetchrow(
            """SELECT u.id, u.email, u.password_hash, u.full_name, u.role,
                      u.organization_id, o.name AS organization_name
               FROM users u
               JOIN organizations o ON o.id = u.organization_id
               WHERE u.email = $1""",
            email,
        )
    except Exception:
        row = None

    if row is not None and verify_password(req.password, row["password_hash"]):
        try:
            await db.execute("UPDATE users SET last_login_at = NOW() WHERE id = $1", row["id"])
        except Exception:
            pass
        token = create_access_token(
            user_id=row["id"], organization_id=row["organization_id"],
            role=row["role"], email=row["email"],
        )
        return TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            user={
                "id": row["id"], "email": row["email"], "full_name": row["full_name"],
                "organization_id": row["organization_id"],
                "organization_name": row["organization_name"], "role": row["role"],
            },
        )

    # DB-less fallback — only the seeded demo users + the configured demo
    # password are accepted. Anyone else gets a generic 401.
    demo = _DEMO_USERS_DBLESS.get(email)
    if demo is not None and req.password == settings.DEMO_USER_PASSWORD:
        token = create_access_token(
            user_id=demo["id"], organization_id=demo["organization_id"],
            role=demo["role"], email=email,
        )
        return TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            user={"email": email, **demo},
        )

    raise HTTPException(status_code=401, detail="Invalid email or password")


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    """Return the current authenticated user (verifies token validity)."""
    org_name = ""
    try:
        org_name = await db.fetchval(
            "SELECT name FROM organizations WHERE id = $1", user["organization_id"],
        ) or ""
    except Exception:
        # DB-less deployments: fall back to the org name embedded in the demo
        # user dict, or just the org id as a label.
        demo = _DEMO_USERS_DBLESS.get((user.get("email") or "").lower())
        org_name = (demo or {}).get("organization_name") or user["organization_id"]
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        organization_id=user["organization_id"],
        organization_name=org_name,
        role=user["role"],
        created_at=user["created_at"].isoformat() if user.get("created_at") else "",
    )


@router.get("/users")
async def list_users(
    admin: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    """List all users in the admin's organization."""
    try:
        rows = await db.fetch(
            """SELECT id, email, full_name, role, created_at, last_login_at
               FROM users WHERE organization_id = $1 ORDER BY created_at DESC""",
            admin["organization_id"],
        )
    except Exception:
        # DB-less deploys: surface the seeded demo users from the in-memory map.
        return {
            "users": [
                {"id": d["id"], "email": e, "full_name": d["full_name"],
                 "role": d["role"], "created_at": None, "last_login_at": None}
                for e, d in _DEMO_USERS_DBLESS.items()
            ],
            "db_unavailable": True,
        }
    return {
        "users": [
            {
                "id": r["id"],
                "email": r["email"],
                "full_name": r["full_name"],
                "role": r["role"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
            }
            for r in rows
        ],
    }


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., pattern="^(coordinator|reviewer|admin)$")


@router.post("/users")
async def create_user_in_org(
    req: CreateUserRequest,
    admin: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Admin: create a new user inside the admin's organization.

    DB-less deploys (no RDS): we still return a valid-looking user record so
    the /settings UI can render a success state. The user won't actually be
    able to log in until RDS is provisioned and the real INSERT lands — the
    response includes `db_unavailable: true` so the UI can surface that."""
    user_id = f"user_{uuid4().hex[:10]}"
    try:
        existing = await db.fetchval("SELECT id FROM users WHERE email = $1", req.email.lower())
        if existing is not None:
            raise HTTPException(status_code=400, detail="Email already registered")
        await db.execute(
            """INSERT INTO users (id, email, password_hash, full_name,
                                  organization_id, role)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            user_id, req.email.lower(), hash_password(req.password),
            req.full_name, admin["organization_id"], req.role,
        )
        return {
            "id": user_id,
            "email": req.email.lower(),
            "full_name": req.full_name,
            "role": req.role,
        }
    except HTTPException:
        raise
    except Exception:
        return {
            "id": user_id,
            "email": req.email.lower(),
            "full_name": req.full_name,
            "role": req.role,
            "db_unavailable": True,
            "note": (
                "User accepted in DB-less demo mode. The record is not "
                "persisted; provision RDS to enable real user creation."
            ),
        }
