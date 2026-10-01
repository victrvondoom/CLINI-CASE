"""Login throttle, OIDC return_to sanitising, policy mutation admin gate."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.auth_oidc import _safe_return_to
from app.auth import login_throttle as lt
from app.main import app


@pytest.mark.parametrize(
    ("raw", "ok"),
    [
        ("/cases/1", True),
        ("/", True),
        (None, True),
        ("https://evil.example/x", False),
        ("//evil.example", False),
        ("/\\evil.example", False),
        ("javascript:alert(1)", False),
    ],
)
def test_return_to_is_same_origin_only(raw, ok):
    out = _safe_return_to(raw)
    assert out.startswith("/") and not out.startswith("//")
    if ok and raw:
        assert out == raw
    if not ok:
        assert out == "/"


def test_throttle_window():
    lt.clear_all()
    for _ in range(lt.MAX_FAILURES):
        assert lt.retry_after("a@b.c", "1.1.1.1", now=1000.0) == 0
        lt.record_failure("a@b.c", "1.1.1.1", now=1000.0)
    assert lt.retry_after("a@b.c", "1.1.1.1", now=1001.0) > 0
    assert lt.retry_after("a@b.c", "2.2.2.2", now=1001.0) == 0
    assert lt.retry_after("a@b.c", "1.1.1.1", now=1000.0 + lt.WINDOW_SECONDS + 1) == 0
    lt.clear_all()


def test_login_returns_429_after_repeated_failures(monkeypatch):
    from fastapi import HTTPException

    from app.api import auth as auth_api

    async def _bad(_req):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    monkeypatch.setattr(auth_api, "_login_impl", _bad)
    lt.clear_all()
    c = TestClient(app)
    body = {"email": "nobody@example.com", "password": "wrong-password-123"}
    codes = [
        c.post("/api/v1/auth/login", json=body).status_code for _ in range(lt.MAX_FAILURES + 1)
    ]
    assert codes[: lt.MAX_FAILURES] == [401] * lt.MAX_FAILURES and codes[-1] == 429
    lt.clear_all()


@pytest.mark.integration
@pytest.mark.postgres
async def test_policy_mutations_require_platform_admin():
    import httpx

    from tests.runs.helpers import _h, _org

    org = await _org("pol")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        h = _h(org["token"])
        assert (await c.delete("/api/v1/policies/some.pdf", headers=h)).status_code == 403
        assert (
            await c.post("/api/v1/policies/trash/some.pdf/restore", headers=h)
        ).status_code == 403
        assert (
            await c.delete("/api/v1/policies/trash/some.pdf/purge", headers=h)
        ).status_code == 403
        files = {"file": ("x.txt", b"hi", "text/plain")}
        assert (await c.post("/api/v1/policies/upload", headers=h, files=files)).status_code == 403
