import pytest
from pydantic import BaseModel, ValidationError

from app.agents.framework.agent import _strip_code_fence
from app.agents.framework.json_text import extract_json_text, parse_model


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```\nHope this helps.', '{"a": 1}'),
        ('```json\n{"a": 1}', '{"a": 1}'),  # truncated fence
        ('<think>plan the answer</think>\n{"a": 1}', '{"a": 1}'),
        ('Here is the JSON:\n{"a": {"b": 2}}\nDone.', '{"a": {"b": 2}}'),
        ('{"letter": "use ```code``` here"}', '{"letter": "use ```code``` here"}'),
        ("[1, 2]", "[1, 2]"),
        ("", ""),
    ],
)
def test_extract_json_text(raw, expected):
    assert extract_json_text(raw) == expected
    assert _strip_code_fence(raw) == expected


class _Note(BaseModel):
    score: float
    feedback: str


@pytest.mark.parametrize(
    ("raw", "feedback"),
    [
        ('{"score": 1, "feedback": "ok"}', "ok"),
        ('{"score": 1, "feedback": "line one\nline two"}', "line one\nline two"),  # raw newline
        ('{"score": 1, "feedback": "the agent\\\'s view"}', "the agent's view"),  # \' escape
        ('{"score": 1, "feedback": "C:\\\\path and \\d"}', "C:\\path and \\d"),  # valid + stray
    ],
)
def test_parse_model_repairs_only_malformed_json(raw, feedback):
    assert parse_model(_Note, raw).feedback == feedback


def test_parse_model_keeps_field_validation():
    with pytest.raises(ValidationError):
        parse_model(_Note, '{"score": "high", "feedback": "x\ny"}')
