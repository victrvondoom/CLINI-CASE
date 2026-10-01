"""Portable hash-chain manifests. Integrity is not a signature or authorship proof."""

import copy
from typing import Any

from fastapi import HTTPException

from app.onehealth.fhir import digest
from app.onehealth.models import now


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
        if item.get("previous_hash") != previous or digest(body) != item.get("current_hash"):
            return {"status": "CHAIN_BROKEN", "valid": False}
        version += 1
        previous = item["current_hash"]
    if version != data.get("version"):
        return {"status": "VERSION_MISMATCH", "valid": False}
    if chain[-1]["artifacts"] != manifest(data):
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


def portable(record: dict[str, Any], **artifacts: Any) -> dict[str, Any]:
    content = {"record": record, **artifacts}
    return {
        "format": "clini-case-evidence-passport-1",
        "exported_at": now().isoformat(),
        "content": content,
        "hash_manifest": {k: digest(v) for k, v in content.items()},
        "limitations": "Hash integrity only; no digital signature or authenticated external anchor. A party able to rewrite all hashes can forge a chain. Previously downloaded data cannot be recalled.",
    }


def verify_portable(package: dict[str, Any]) -> dict[str, Any]:
    try:
        content = package["content"]
        hashes = {k: digest(v) for k, v in content.items()}
        valid = (
            package["format"] == "clini-case-evidence-passport-1"
            and hashes == package["hash_manifest"]
            and verify(content["record"])["valid"]
        )
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        valid = False
    return {"status": "VALID PASSPORT" if valid else "INTEGRITY FAILURE", "valid": valid}
