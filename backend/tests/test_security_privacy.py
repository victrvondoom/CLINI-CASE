"""Offline regression tests for auth revocation and patient-data boundaries."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.auth import dependencies
from app.config import Settings, settings


@pytest.fixture
def auth_context(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")
    monkeypatch.setattr(settings, "AUTH_DBLESS_DEMO_ENABLED", False)
    claims = {
        "sub": "user_demoadmin",
        "email": "admin@clincase.health",
        "org": "org_demo",
        "role": "admin",
    }
    monkeypatch.setattr(dependencies, "decode_access_token", lambda _: claims)
    return Request({"type": "http", "query_string": b""}), HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="token"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("demo_enabled", [False, True])
async def test_deleted_user_is_never_reconstructed(auth_context, monkeypatch, demo_enabled):
    monkeypatch.setattr(settings, "AUTH_DBLESS_DEMO_ENABLED", demo_enabled)
    monkeypatch.setattr(dependencies.db, "fetchrow", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as caught:
        await dependencies.get_current_user(*auth_context)
    assert caught.value.status_code == 401


@pytest.mark.asyncio
async def test_database_outage_fails_closed_by_default(auth_context, monkeypatch):
    monkeypatch.setattr(dependencies.db, "fetchrow", AsyncMock(side_effect=RuntimeError("offline")))
    with pytest.raises(HTTPException) as caught:
        await dependencies.get_current_user(*auth_context)
    assert caught.value.status_code == 503


@pytest.mark.asyncio
async def test_explicit_local_demo_outage_fallback(auth_context, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DBLESS_DEMO_ENABLED", True)
    monkeypatch.setattr(dependencies.db, "fetchrow", AsyncMock(side_effect=RuntimeError("offline")))
    user = await dependencies.get_current_user(*auth_context)
    assert user["id"] == "user_demoadmin"


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [None, {"password_hash": "not-valid"}])
async def test_demo_password_cannot_bypass_healthy_database(monkeypatch, row):
    from app.api import auth

    monkeypatch.setattr(settings, "AUTH_DBLESS_DEMO_ENABLED", True)
    monkeypatch.setattr(auth.db, "fetchrow", AsyncMock(return_value=row))
    monkeypatch.setattr(auth, "verify_password", lambda *_: False)
    with pytest.raises(HTTPException) as caught:
        await auth.login(
            auth.LoginRequest(email="admin@clincase.health", password=settings.DEMO_USER_PASSWORD)
        )
    assert caught.value.status_code == 401


@pytest.mark.parametrize("extra", [{"AUTH_DBLESS_DEMO_ENABLED": True}, {"MCP_AUTH_TOKEN": ""}])
def test_nondev_rejects_unsafe_modes(extra):
    with pytest.raises(RuntimeError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            JWT_SECRET="x" * 40,
            DEMO_USER_PASSWORD="different",
            **extra,
        )


@pytest.mark.asyncio
async def test_cloud_ocr_disabled_before_client_creation(monkeypatch):
    from app.agents.intake.engines import claude_vision
    from app.agents.intake.engines.aws_textract import AWSTextractEngine
    from app.agents.intake.errors import EngineUnavailableError
    from app.models.intake import DocumentClassification

    monkeypatch.setattr(settings, "CLOUD_DOCUMENT_PROCESSING_ENABLED", False)
    client_factory = Mock(side_effect=AssertionError("must not reach network"))
    monkeypatch.setattr(claude_vision, "get_llm_client", client_factory)
    textract = AWSTextractEngine()
    monkeypatch.setattr(textract, "_ensure_client", client_factory)
    classification = DocumentClassification(
        document_type="typed_print", confidence=1, rationale="test"
    )
    for engine in (claude_vision.ClaudeVisionEngine(), textract):
        with pytest.raises(EngineUnavailableError, match="Cloud document processing disabled"):
            await engine.extract(
                image_bytes=b"PHI pixels", image_format="png", classification=classification
            )
    client_factory.assert_not_called()


def test_pdf_cloud_ocr_is_also_blocked(monkeypatch):
    from app.api.intake import _PDFExtractFailureError, _textract_extract

    monkeypatch.setattr(settings, "CLOUD_DOCUMENT_PROCESSING_ENABLED", False)
    with pytest.raises(_PDFExtractFailureError, match="Cloud document processing disabled"):
        _textract_extract(b"PHI pixels")


@pytest.mark.asyncio
async def test_cache_is_tenant_and_policy_scoped(monkeypatch):
    from app.agents.intake.pipeline.base import IntakeContext
    from app.agents.intake.pipeline.deduplicate import (
        DeduplicateStage,
        _store_in_cache,
        clear_cache_for_tests,
    )

    clear_cache_for_tests()
    monkeypatch.setattr(settings, "CLOUD_DOCUMENT_PROCESSING_ENABLED", False)
    data = {"ocr": {"full_text": "private result"}}
    _store_in_cache("same-hash", data, "org-a")
    data["ocr"]["full_text"] = "mutated"

    def context(tenant_id):
        return IntakeContext(
            image_bytes=b"",
            image_format="png",
            filename="",
            mime_type="image/png",
            sha256="same-hash",
            source="upload",
            tenant_id=tenant_id,
        )

    for tenant in ("org-b", None):
        ctx = context(tenant)
        await DeduplicateStage().run(ctx)
        assert not ctx.payload["deduplicate.cache_hit"]
    ctx = context("org-a")
    await DeduplicateStage().run(ctx)
    assert ctx.payload["deduplicate.cached_intake_result"]["ocr"]["full_text"] == "private result"
    monkeypatch.setattr(settings, "CLOUD_DOCUMENT_PROCESSING_ENABLED", True)
    ctx = context("org-a")
    await DeduplicateStage().run(ctx)
    assert not ctx.payload["deduplicate.cache_hit"]
    clear_cache_for_tests()


def test_fhir_minimization_preserves_clinical_evidence_and_local_citations():
    import copy
    import json

    from app.privacy.boundary import prepare_fhir, restore_source_ids

    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "fullUrl": "https://hospital/patients/secret",
                "resource": {
                    "resourceType": "Patient",
                    "id": "MRNsecret",
                    "name": [{"family": "Identifiable", "given": ["Person"]}],
                    "birthDate": "1972-08-14",
                    "identifier": [{"value": "private-123"}],
                    "telecom": [{"value": "private@example.com"}],
                },
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "lab-secret",
                    "subject": {"reference": "Patient/MRNsecret"},
                    "code": {"coding": [{"code": "HER2", "display": "HER2"}]},
                    "valueString": "positive",
                    "text": {"div": "Identifiable Person"},
                }
            },
        ],
    }
    original = copy.deepcopy(bundle)
    safe, mapping = prepare_fhir(bundle)
    serialized = json.dumps(safe)
    for secret in (
        "MRNsecret",
        "lab-secret",
        "Identifiable",
        "private@example.com",
        "1972-08-14",
        "private-123",
    ):
        assert secret not in serialized
    assert "HER2" in serialized and "positive" in serialized and "ageYears" in serialized
    assert bundle == original
    assert restore_source_ids({"source_resource_id": "resource-2"}, mapping) == {
        "source_resource_id": "lab-secret"
    }


def test_text_screening_preserves_clinical_names():
    from app.privacy.boundary import screen_text

    assert (
        screen_text("Breast Cancer and Estrogen Receptor positive")
        == "Breast Cancer and Estrogen Receptor positive"
    )
    assert "Jane Smith" not in screen_text("Patient name: Jane Smith\nDiagnosis: Breast Cancer")


def test_all_fhir_prompt_builders_minimize_identifiers():
    from app.agents.clinical_extractor.orchestrator import ClinicalExtractorAgent
    from app.agents.clinical_extractor.schemas import (
        BiomarkerSpecialistInput,
        ClinicalExtractorInput,
    )
    from app.agents.clinical_extractor.sub_agents.biomarker_specialist import biomarker_specialist

    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "PRIVATE-MRN",
                    "name": [{"family": "PRIVATE-NAME"}],
                }
            }
        ],
    }
    parent = ClinicalExtractorInput(fhir_bundle=bundle, requested_treatment={"name": "Trastuzumab"})
    child = BiomarkerSpecialistInput(fhir_bundle=bundle, requested_treatment_name="Trastuzumab")
    for prompt in (
        ClinicalExtractorAgent._build_extractor_user_message(parent, None),
        biomarker_specialist._build_user_message(child),
    ):
        assert "PRIVATE-MRN" not in prompt and "PRIVATE-NAME" not in prompt
        assert "Trastuzumab" in prompt
