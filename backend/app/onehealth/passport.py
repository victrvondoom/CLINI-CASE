"""Portable hash-chain manifests. Integrity is not a signature or authorship proof."""

import base64
import binascii
import copy
import hashlib
from typing import Any

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException

from app.config import settings
from app.onehealth.fhir import digest as _raw_digest
from app.onehealth.models import now

log = structlog.get_logger()

SIGNER = "CLINI-CASE demo signer"
SIGNATURE_SCOPE = (
    "CLINI-CASE demo-system signature over the passport manifest. "
    "Not a laboratory, clinician, government or third-party attestation, and not legal authenticity."
)


def _stable(value: Any) -> Any:
    """Integral floats become ints: JSON round-trips through JavaScript turn 1.0 into 1."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def digest(value: Any) -> str:
    return _raw_digest(_stable(value))


def _matches(value: Any, recorded: Any) -> bool:
    """Current digest, or the legacy digest of the unnormalised value (passports sealed before normalising)."""
    return recorded in (digest(value), _raw_digest(value))


def _manifest_matches(recorded: Any, data: dict[str, Any]) -> bool:
    expected = {k: v for k, v in data.items() if k != "passport"}
    return isinstance(recorded, dict) and set(recorded) == set(expected) and all(
        _matches(v, recorded[k]) for k, v in expected.items()
    )


def manifest(data: dict[str, Any]) -> dict[str, str]:
    return {k: digest(v) for k, v in sorted(data.items()) if k != "passport"}


def verify(data: dict[str, Any]) -> dict[str, Any]:
    try:
        return _verify(data)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return {"status": "CHAIN_BROKEN", "valid": False}


def _verify(data: dict[str, Any]) -> dict[str, Any]:
    chain = data.get("passport", [])
    if not chain:
        return {"status": "RECORD_MISSING", "valid": False, "revision_count": 0}
    previous = None
    version = chain[0].get("record_version", 0) - 1
    for item in chain:
        body = {k: v for k, v in item.items() if k != "current_hash"}
        if item.get("record_version") != version + 1:
            return {"status": "VERSION_MISMATCH", "valid": False}
        if item.get("previous_hash") != previous or not _matches(body, item.get("current_hash")):
            return {"status": "CHAIN_BROKEN", "valid": False}
        version += 1
        previous = item["current_hash"]
    if version != data.get("version"):
        return {"status": "VERSION_MISMATCH", "valid": False}
    if not _manifest_matches(chain[-1]["artifacts"], data):
        return {"status": "CHAIN_BROKEN", "valid": False}
    return {"status": "CHAIN_VALID", "valid": True, "revision_count": len(chain), "head": previous}


def seal(data: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Called inside the store's CAS transaction; callers cannot rewrite prior manifests."""
    result = copy.deepcopy(data)
    if previous and previous.get("passport") and not verify(previous)["valid"]:
        raise HTTPException(
            409, "Stored passport integrity failed; correction requires investigation"
        )
    chain = copy.deepcopy((previous or {}).get("passport", []))
    events = result.get("events", []) or result.get("audit", [])
    last = events[-1] if events else {}
    body = {
        "previous_hash": chain[-1]["current_hash"] if chain else None,
        "record_version": result["version"],
        "timestamp": now().isoformat(),
        "actor": last.get("actor", last.get("actor_id", "repository")),
        "action": last.get("event_type", last.get("action", "record_saved")),
        "object_id": result["id"],
        "reason": last.get("provenance", last.get("note", "Versioned evidence persistence")),
        "artifacts": manifest(result),
    }
    if "source" in result:
        from app.interop.models import Job
        from app.interop.service import trust_states

        body["trust_states"] = trust_states(Job.model_validate(result))
    else:
        from app.onehealth.evidence import trust_states as exposure_states
        from app.onehealth.models import ExposureRecord

        body["trust_states"] = exposure_states(ExposureRecord.model_validate(result))
    chain.append({**body, "current_hash": digest(body)})
    result["passport"] = chain
    return result


def _private_key() -> Ed25519PrivateKey | None:
    raw = settings.PASSPORT_SIGNING_KEY.strip()
    if not raw:
        return None
    try:
        seed = base64.b64decode(raw, validate=True)
        if len(seed) != 32:
            raise ValueError("Ed25519 seed must be 32 bytes")
        return Ed25519PrivateKey.from_private_bytes(seed)
    except (ValueError, binascii.Error):
        log.warning("passport.signing_key_invalid")  # never log the value
        return None


def key_id(public: Ed25519PublicKey) -> str:
    raw = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def signing_status() -> dict[str, Any]:
    key = _private_key()
    return {
        "enabled": key is not None,
        "algorithm": "Ed25519",
        "key_id": key_id(key.public_key()) if key else None,
        "signer": SIGNER,
        "scope": SIGNATURE_SCOPE,
    }


def _signed_payload(package: dict[str, Any]) -> dict[str, Any]:
    """The exact, canonical message that is signed: identity, version, chain head and the manifest."""
    record = package["content"]["record"]
    chain = record["passport"]
    return {
        "format": package["format"],
        "object_id": record["id"],
        "record_version": record["version"],
        "head": chain[-1]["current_hash"],
        # Recompute from the submitted content. Verifying only the claimed hashes
        # would leave the raw signature verdict valid after a content-only edit.
        "hash_manifest": {name: digest(value) for name, value in package["content"].items()},
    }


def _sign(package: dict[str, Any]) -> dict[str, Any] | None:
    key = _private_key()
    if key is None:
        return None
    try:
        payload_sha256 = digest(_signed_payload(package))
    except (KeyError, TypeError, IndexError):
        return None  # a record without a sealed chain has nothing to sign
    return {
        "algorithm": "Ed25519",
        "key_id": key_id(key.public_key()),
        "signer": SIGNER,
        "payload_sha256": payload_sha256,
        "value": base64.b64encode(key.sign(payload_sha256.encode())).decode(),
        "scope": SIGNATURE_SCOPE,
    }


def portable(record: dict[str, Any], **artifacts: Any) -> dict[str, Any]:
    content = {"record": record, **artifacts}
    package: dict[str, Any] = {
        "format": "clini-case-evidence-passport-1",
        "exported_at": now().isoformat(),
        "content": content,
        "hash_manifest": {k: digest(v) for k, v in content.items()},
        "limitations": "Integrity is a hash chain; when signed, the signature is a CLINI-CASE demo-system signature, not a laboratory, clinician or third-party attestation. Previously downloaded data cannot be recalled.",
    }
    signature = _sign(package)
    if signature:
        package["signature"] = signature
    return package


def verify_portable(package: dict[str, Any]) -> dict[str, Any]:
    try:
        content = package["content"]
        recorded = package["hash_manifest"]
        valid = (
            package["format"] == "clini-case-evidence-passport-1"
            and set(recorded) == set(content)
            and all(_matches(v, recorded[k]) for k, v in content.items())
            and verify(content["record"])["valid"]
        )
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        valid = False
    return {"status": "VALID PASSPORT" if valid else "INTEGRITY FAILURE", "valid": valid}


def verify_signature(
    package: dict[str, Any], public_key: Ed25519PublicKey | None = None
) -> dict[str, Any]:
    """Statuses: SIGNATURE_VALID, UNSIGNED, UNVERIFIABLE (no key here), KEY_MISMATCH, SIGNATURE_INVALID."""
    base = {"algorithm": "Ed25519", "signer": SIGNER, "scope": SIGNATURE_SCOPE}
    signature = package.get("signature") if isinstance(package, dict) else None
    if not signature:
        return {**base, "status": "UNSIGNED", "valid": False, "key_id": None}
    verifier = public_key
    if verifier is None:
        private = _private_key()
        verifier = private.public_key() if private else None
    claimed = signature.get("key_id") if isinstance(signature, dict) else None
    if verifier is None:
        return {**base, "status": "UNVERIFIABLE", "valid": False, "key_id": claimed}
    if claimed != key_id(verifier):
        return {**base, "status": "KEY_MISMATCH", "valid": False, "key_id": claimed}
    try:
        payload_sha256 = digest(_signed_payload(package))
        if payload_sha256 != signature["payload_sha256"]:
            raise InvalidSignature
        verifier.verify(base64.b64decode(signature["value"], validate=True), payload_sha256.encode())
    except (InvalidSignature, KeyError, TypeError, ValueError, IndexError, binascii.Error):
        return {**base, "status": "SIGNATURE_INVALID", "valid": False, "key_id": claimed}
    return {**base, "status": "SIGNATURE_VALID", "valid": True, "key_id": claimed}


def changed_artifacts(package: dict[str, Any]) -> list[str]:
    """Name what no longer matches its recorded hash (empty when nothing was altered)."""
    changed: list[str] = []
    try:
        content, recorded = package["content"], package["hash_manifest"]
        changed += [f"content.{k}" for k, v in content.items() if not _matches(v, recorded.get(k))]
        record = content["record"]
        sealed = record["passport"][-1]["artifacts"]
        changed += [
            f"record.{k}" for k, v in record.items() if k != "passport" and not _matches(v, sealed.get(k))
        ]
    except (KeyError, TypeError, IndexError, AttributeError):
        changed.append("package structure")
    return changed


def verify_package(package: dict[str, Any], public_key: Ed25519PublicKey | None = None) -> dict[str, Any]:
    """Hash chain, signature and what changed, in one verdict."""
    chain = verify_portable(package)
    signature = verify_signature(package, public_key)
    if not chain["valid"] or signature["status"] in ("SIGNATURE_INVALID", "KEY_MISMATCH"):
        overall = "FAILED"
    elif signature["status"] == "SIGNATURE_VALID":
        overall = "VERIFIED"
    else:
        overall = "HASH_CHAIN_ONLY"  # unsigned, or no key available to check the signature
    return {
        "overall": overall,
        "hash_chain": chain,
        "signature": signature,
        "changed_artifacts": changed_artifacts(package),
    }
