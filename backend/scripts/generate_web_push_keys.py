"""Generate one-time Web Push environment values; keep the two private values server-side."""

import base64
import secrets

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


private = ec.generate_private_key(ec.SECP256R1())
private_scalar = private.private_numbers().private_value.to_bytes(32, "big")
public_point = private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
print("# Store VAPID_PRIVATE_KEY and WEB_PUSH_ENCRYPTION_KEY only in backend secrets.")
print("VAPID_PUBLIC_KEY=" + b64url(public_point))
print("VAPID_PRIVATE_KEY=" + b64url(private_scalar))
print("VAPID_SUBJECT=mailto:security@clincase.health")
print("WEB_PUSH_ENCRYPTION_KEY=" + b64url(secrets.token_bytes(32)))
