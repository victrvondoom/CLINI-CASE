"""Health check endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from app.db import db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness + DB readiness."""
    db_status = "ok"
    try:
        await db.fetchval("SELECT 1")
    except Exception as e:  # noqa: BLE001
        db_status = f"error: {e}"
    return {"status": "ok", "db": db_status}
