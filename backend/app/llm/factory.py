"""LLM client factory. Returns the configured provider, wrapped in the GenAI Gateway."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.llm.base import LLMClient


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
