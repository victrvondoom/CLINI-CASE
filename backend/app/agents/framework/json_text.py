"""Recover the JSON object from a model reply.

Claude replies are bare JSON or one ``` fence. Other models (e.g. reasoning models on
OpenAI-compatible endpoints) may add <think> blocks, a fence with trailing prose, or a short
preamble. Validation still happens in the caller's Pydantic model; this only trims wrapping.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```[a-zA-Z0-9_-]*[ \t]*\n?(.*?)```", re.DOTALL)
_ESCAPE = re.compile(r"\\(.)", re.DOTALL)


def _fix_escape(m: re.Match[str]) -> str:
    """Keep valid JSON escapes; turn \\' into ' and any other stray backslash into a literal one."""
    c = m.group(1)
    if c in '"\\/bfnrtu':
        return m.group(0)
    return "'" if c == "'" else "\\\\" + c


def extract_json_text(text: str) -> str:
    text = _THINK.sub("", text or "").strip()
    if text[:1] in ("{", "["):  # already bare JSON: never cut inside it
        return text
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):  # unterminated fence (truncated reply)
        text = text.split("\n", 1)[1].strip() if "\n" in text else ""
    if text[:1] not in ("{", "["):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text.strip()


def parse_model(model: type[M], text: str) -> M:
    """Validate a model reply. Strict JSON first; only if the JSON itself is malformed by raw
    control characters inside strings (e.g. a literal newline), re-read it leniently. Field
    validation is identical either way."""
    cleaned = extract_json_text(text)
    try:
        return model.model_validate_json(cleaned)
    except ValidationError as exc:
        if not any(e.get("type") == "json_invalid" for e in exc.errors()):
            raise
        # Also repair invalid escapes some models emit (\' and stray backslashes).
        repaired = _ESCAPE.sub(_fix_escape, cleaned)
        try:
            data = json.loads(repaired, strict=False)
        except ValueError:
            raise exc from None
        return model.model_validate(data)
