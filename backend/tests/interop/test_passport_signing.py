"""Evidence Passport signing: a CLINI-CASE demo-system Ed25519 signature that survives hash recomputation."""

import base64
import copy
import json
import secrets

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from app.api import interop as interop_api
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import repository
from app.onehealth import passport
from app.onehealth.fhir import digest

SEED = base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture
async def session(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "")
    monkeypatch.setattr(settings, "PASSPORT_SIGNING_KEY", SEED)
    repository._memory.clear()
    app = FastAPI()
    app.include_router(interop_api.router, prefix="/api/v1")
    user = {"id": "signer-reviewer", "role": "reviewer", "organization_id": "signing-org"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, user
    repository._memory.clear()


async def exported_passport(client):
    """Run the real gateway to a generated bundle and export its Evidence Passport."""
    base = "/api/v1/interop"
    job = (await client.post(base + "/demo?variant=dissolved", json={})).json()

    async def step(path, **extra):
        nonlocal job
        response = await client.post(
            base + path, json={"job_id": job["id"], "expected_version": job["version"], **extra}
        )
        assert response.is_success, response.text
        job = response.json()

    await step("/map")
    for mapping in [m for m in job["mappings"] if m["decision"] == "pending"]:
        verb = "approve" if mapping["target"] else "reject"
        await step(
            f"/mappings/{job['id']}/{verb}", source_field=mapping["source_field"], target=mapping["target"]
        )
    await step("/generate-fhir")
    response = await client.get(f"{base}/passport/{job['id']}/export")
    assert response.status_code == 200, response.text
    return job, response.json()


def forge(package):
    """The attack the unsigned chain could not stop: change a value, then recompute every hash."""
    forged = copy.deepcopy(package)
    record = forged["content"]["record"]
    record["normalized"]["value"] = 999.0
    chain = record["passport"]
    chain[-1]["artifacts"] = passport.manifest(record)
    chain[-1]["current_hash"] = digest({k: v for k, v in chain[-1].items() if k != "current_hash"})
    forged["hash_manifest"] = {k: digest(v) for k, v in forged["content"].items()}
    return forged


async def test_signed_export_verifies_and_is_labelled_as_a_demo_system_signature(session):
    client, _ = session
    _, package = await exported_passport(client)
    signature = package["signature"]
    assert signature["algorithm"] == "Ed25519" and signature["signer"] == "CLINI-CASE demo signer"
    assert signature["key_id"] == passport.signing_status()["key_id"]
    assert "Not a laboratory, clinician, government or third-party attestation" in signature["scope"]
    verdict = passport.verify_package(package)
    assert verdict["overall"] == "VERIFIED"
    assert verdict["signature"]["status"] == "SIGNATURE_VALID" and verdict["changed_artifacts"] == []


async def test_an_untouched_passport_still_verifies_after_a_javascript_round_trip(session):
    """A browser parses 1.0 as 1; the verifier must not read that as tampering."""
    client, _ = session
    _, package = await exported_passport(client)

    def as_javascript(text: str):
        number = float(text)
        return int(number) if number.is_integer() else number

    assert '"confidence": 1.0' in json.dumps(package), "the fixture must contain an integral float"
    roundtripped = json.loads(json.dumps(package), parse_float=as_javascript)
    verdict = passport.verify_package(roundtripped)
    assert verdict["overall"] == "VERIFIED" and verdict["changed_artifacts"] == []


async def test_modifying_one_value_fails_verification_and_names_what_changed(session):
    client, _ = session
    _, package = await exported_passport(client)
    tampered = copy.deepcopy(package)
    tampered["content"]["record"]["normalized"]["value"] = 999.0
    verdict = passport.verify_package(tampered)
    assert verdict["overall"] == "FAILED" and not verdict["hash_chain"]["valid"]
    assert verdict["signature"]["status"] == "SIGNATURE_INVALID"
    assert "content.record" in verdict["changed_artifacts"]
    assert "record.normalized" in verdict["changed_artifacts"]


async def test_recomputing_every_hash_still_cannot_forge_the_signature(session):
    client, _ = session
    _, package = await exported_passport(client)
    forged = forge(package)
    assert passport.verify_portable(forged)["valid"], "the attack must defeat the hash chain alone"
    verdict = passport.verify_package(forged)
    assert verdict["signature"]["status"] == "SIGNATURE_INVALID" and verdict["overall"] == "FAILED"


async def test_wrong_key_is_rejected(session):
    client, _ = session
    _, package = await exported_passport(client)
    other = Ed25519PrivateKey.generate()
    assert passport.verify_signature(package, other.public_key())["status"] == "KEY_MISMATCH"
    # A signature made by another key but claiming this key id must fail the cryptographic check.
    impostor = copy.deepcopy(package)
    impostor["signature"]["value"] = base64.b64encode(
        other.sign(impostor["signature"]["payload_sha256"].encode())
    ).decode()
    assert passport.verify_signature(impostor)["status"] == "SIGNATURE_INVALID"


async def test_unsigned_when_no_key_and_export_still_works(session, monkeypatch):
    client, _ = session
    monkeypatch.setattr(settings, "PASSPORT_SIGNING_KEY", "")
    _, package = await exported_passport(client)
    assert "signature" not in package
    verdict = passport.verify_package(package)
    assert verdict["signature"]["status"] == "UNSIGNED" and verdict["overall"] == "HASH_CHAIN_ONLY"
    assert passport.signing_status()["enabled"] is False


async def test_malformed_key_degrades_to_unsigned_without_failing_export(session, monkeypatch):
    client, _ = session
    monkeypatch.setattr(settings, "PASSPORT_SIGNING_KEY", "not-base64!")
    _, package = await exported_passport(client)
    assert "signature" not in package and passport.signing_status()["enabled"] is False


async def test_verify_endpoint_is_stateless_size_capped_and_reviewer_only(session):
    client, user = session
    job, package = await exported_passport(client)
    before = (await client.get(f"/api/v1/interop/jobs/{job['id']}")).json()["version"]
    ok = await client.post("/api/v1/interop/passport/verify", json={"package": package})
    assert ok.status_code == 200 and ok.json()["overall"] == "VERIFIED"
    tampered = copy.deepcopy(package)
    tampered["content"]["record"]["normalized"]["value"] = 1
    bad = await client.post("/api/v1/interop/passport/verify", json={"package": tampered})
    assert bad.status_code == 200 and bad.json()["overall"] == "FAILED"
    assert (await client.get(f"/api/v1/interop/jobs/{job['id']}")).json()["version"] == before
    huge = {"package": {"blob": "x" * 1_100_000}}
    assert (await client.post("/api/v1/interop/passport/verify", json=huge)).status_code == 413
    user["role"] = "coordinator"
    assert (await client.post("/api/v1/interop/passport/verify", json={"package": package})).status_code == 403
