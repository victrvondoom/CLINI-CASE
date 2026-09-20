"""LLM provider abstraction.

All agent code MUST go through `get_llm_client()` — never import
`anthropic` or `boto3` directly. This lets us swap Anthropic↔Bedrock
with a single env var (LLM_PROVIDER).
"""
from app.llm.base import LLMClient, LLMResponse
from app.llm.factory import get_llm_client

__all__ = ["LLMClient", "LLMResponse", "get_llm_client"]
