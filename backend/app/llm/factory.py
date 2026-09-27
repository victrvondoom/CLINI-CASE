"""LLM client factory. Returns the configured provider, wrapped in the GenAI Gateway."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.llm.base import LLMClient


def llm_unavailable_reason() -> str | None:
    """Why the configured provider cannot be called, or None if it has credentials."""
    provider = settings.LLM_PROVIDER
    if provider in ("anthropic", "openrouter"):
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENROUTER_API_KEY"
        if not getattr(settings, env_var).strip():
            return (
                f"No LLM API key configured: LLM_PROVIDER={provider} but {env_var} is empty. "
                "Add the key to .env in the repo root and restart the backend."
            )
    elif provider == "bedrock":
        import boto3
        if boto3.Session().get_credentials() is None:
            return (
                "No AWS credentials found for LLM_PROVIDER=bedrock. "
                "Configure AWS credentials and restart the backend."
            )
    return None


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return the configured LLM client wrapped by the GenAI Gateway.

    The gateway is composition (it implements LLMClient too), so every
    existing call site keeps working — but every Bedrock invocation now
    flows through one named, audited, quota-gated component.

    Cached — only instantiated once per process. Re-import after changing
    LLM_PROVIDER will not pick up the change unless you also clear the
    cache (which we don't — process restart is the contract).
    """
    underlying: LLMClient
    if settings.LLM_PROVIDER == "anthropic":
        from app.llm.anthropic_client import AnthropicClient
        underlying = AnthropicClient()
    elif settings.LLM_PROVIDER == "openrouter":
        from app.llm.openrouter_client import OpenRouterClient
        underlying = OpenRouterClient()
    elif settings.LLM_PROVIDER == "bedrock":
        from app.llm.bedrock_client import BedrockClient
        underlying = BedrockClient()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")

    if not settings.GENAI_GATEWAY_ENABLED:
        return underlying

    from app.llm.gateway import GenAIGateway
    return GenAIGateway(underlying)
