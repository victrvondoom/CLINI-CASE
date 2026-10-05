"""Opt-in, user-scoped Web Push subscriptions for non-sensitive workflow reminders."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app import db
from app.auth.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/notifications/push", tags=["web-push"])
_SCHEMA_LOCK = asyncio.Lock()
_schema_ready = False
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_ALLOWED_PUSH_HOSTS = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
}


class SubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=40, max_length=200, pattern=_B64URL.pattern)
    auth: str = Field(min_length=16, max_length=100, pattern=_B64URL.pattern)


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: HttpUrl
    expiration_time: int | None = Field(default=None, alias="expirationTime")
    keys: SubscriptionKeys


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription: Subscription


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: HttpUrl


def _decode_key(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _push_settings() -> dict[str, Any] | None:
    public = settings.VAPID_PUBLIC_KEY.strip()
    private = settings.VAPID_PRIVATE_KEY.strip()
    subject = settings.VAPID_SUBJECT.strip()
    encryption = settings.WEB_PUSH_ENCRYPTION_KEY.strip()
    if not (public and private and subject and encryption):
        return None
    try:
        private_bytes = _decode_key(private)
        public_bytes = _decode_key(public)
        encryption_bytes = _decode_key(encryption)
        if len(private_bytes) != 32 or len(public_bytes) != 65 or len(encryption_bytes) != 32:
            return None
        private_key = ec.derive_private_key(int.from_bytes(private_bytes, "big"), ec.SECP256R1())
        derived_public = private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        if not secrets.compare_digest(derived_public, public_bytes):
            return None
        if not subject.startswith("mailto:") and not subject.startswith("https://"):
            return None
        return {"public": public, "private": private, "subject": subject, "encryption": encryption_bytes}
    except (ValueError, TypeError):
        return None


async def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    async with _SCHEMA_LOCK:
        if _schema_ready:
            return
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_subscriptions (
                organization_id TEXT NOT NULL,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                endpoint_hash TEXT NOT NULL,
                encrypted_payload BYTEA NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, endpoint_hash)
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_push_subscriptions_org_user "
            "ON web_push_subscriptions (organization_id, user_id)"
        )
        _schema_ready = True


def _endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = host in _ALLOWED_PUSH_HOSTS or host.endswith(".notify.windows.com") or host.endswith(".push.services.mozilla.com")
    if parsed.scheme != "https" or not allowed or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise HTTPException(422, "Push endpoint must be an HTTPS endpoint from a supported browser push service")


def _encrypt(payload: dict[str, Any], key: bytes, aad: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(payload, separators=(",", ":")).encode(), aad)
    return nonce + ciphertext


def _decrypt(payload: bytes, key: bytes, aad: bytes) -> dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = AESGCM(key).decrypt(payload[:12], payload[12:], aad)
    return json.loads(plaintext)


def _aad(org: str, user: str, endpoint_hash: str) -> bytes:
    return f"{org}:{user}:{endpoint_hash}".encode()


@router.get("/config")
async def push_config(_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    config = _push_settings()
    return {"enabled": config is not None, "public_key": config["public"] if config else None}


@router.post("/subscribe", status_code=201)
async def subscribe(body: SubscribeRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    config = _push_settings()
    if config is None:
        raise HTTPException(503, "Web Push is not configured on this server")
    endpoint = str(body.subscription.endpoint)
    _validate_endpoint(endpoint)
    await _ensure_schema()
    endpoint_hash = _endpoint_hash(endpoint)
    org, user_id = str(user["organization_id"]), str(user["id"])
    serialized = body.subscription.model_dump(mode="json", by_alias=True)
    encrypted = _encrypt(serialized, config["encryption"], _aad(org, user_id, endpoint_hash))
    result = await db.fetchrow(
        """INSERT INTO web_push_subscriptions (organization_id, user_id, endpoint_hash, encrypted_payload)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (user_id, endpoint_hash) DO UPDATE SET
             organization_id = EXCLUDED.organization_id,
             encrypted_payload = EXCLUDED.encrypted_payload,
             updated_at = NOW()
           RETURNING endpoint_hash""",
        org,
        user_id,
        endpoint_hash,
        encrypted,
    )
    return {"subscribed": result is not None}


@router.delete("/subscribe")
async def unsubscribe(body: UnsubscribeRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    endpoint = str(body.endpoint)
    await _ensure_schema()
    status = await db.execute(
        "DELETE FROM web_push_subscriptions WHERE organization_id = $1 AND user_id = $2 AND endpoint_hash = $3",
        str(user["organization_id"]),
        str(user["id"]),
        _endpoint_hash(endpoint),
    )
    return {"removed": status.endswith(" 1")}


@router.post("/test")
async def send_test(_body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    config = _push_settings()
    if config is None:
        raise HTTPException(503, "Web Push is not configured on this server")
    await _ensure_schema()
    org, user_id = str(user["organization_id"]), str(user["id"])
    rows = await db.fetch(
        "SELECT endpoint_hash, encrypted_payload FROM web_push_subscriptions WHERE organization_id = $1 AND user_id = $2",
        org,
        user_id,
    )
    if not rows:
        raise HTTPException(404, "This account has no registered push device")

    from pywebpush import WebPushException, webpush

    message = json.dumps({"title": "CLINI-CASE notification check", "body": "Your opt-in notification channel is connected. Open CLINI-CASE to review your work.", "url": "/onehealth"})
    sent = 0
    expired: list[str] = []
    for row in rows:
        endpoint_hash = str(row["endpoint_hash"])
        try:
            subscription = _decrypt(bytes(row["encrypted_payload"]), config["encryption"], _aad(org, user_id, endpoint_hash))
            _validate_endpoint(subscription["endpoint"])
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription,
                data=message,
                vapid_private_key=config["private"],
                vapid_claims={"sub": config["subject"]},
                ttl=60,
                timeout=8,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                expired.append(endpoint_hash)
        except Exception:
            # Never return provider URLs, subscription material, or transport exception text.
            continue
    for endpoint_hash in expired:
        await db.execute(
            "DELETE FROM web_push_subscriptions WHERE organization_id = $1 AND user_id = $2 AND endpoint_hash = $3",
            org,
            user_id,
            endpoint_hash,
        )
    if sent == 0:
        raise HTTPException(502, "The browser push service did not accept a notification")
    return {"sent": sent, "expired_removed": len(expired)}
