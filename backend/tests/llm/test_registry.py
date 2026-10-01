import json

import pytest

from app.config import settings
from app.llm.registry import ModelEntry, ModelRoutingError, load_registry, route


def test_defaults_match_settings(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    assert route("standard").model_id == settings.BEDROCK_MODEL_ID
    assert route("lite").model_id == settings.BEDROCK_HAIKU_MODEL_ID


def test_unverified_is_refused_not_substituted():
    reg = {("bedrock", "standard"): ModelEntry("bedrock", "standard", "x", status="unverified")}
    with pytest.raises(ModelRoutingError):
        route("standard", provider="bedrock", registry=reg)


def test_explicit_fallback_is_recorded():
    reg = {
        ("bedrock", "standard"): ModelEntry(
            "bedrock", "standard", "a", status="disabled", fallbacks=("lite",)
        ),
        ("bedrock", "lite"): ModelEntry("bedrock", "lite", "b"),
    }
    d = route("standard", provider="bedrock", registry=reg)
    assert d.model_id == "b" and d.fallback_from == "standard" and "fallback" in d.reason


def test_env_override(monkeypatch):
    monkeypatch.setenv(
        "MODEL_REGISTRY_JSON",
        json.dumps([{"provider": "bedrock", "tier": "standard", "model_id": "zzz"}]),
    )
    assert load_registry()[("bedrock", "standard")].model_id == "zzz"
