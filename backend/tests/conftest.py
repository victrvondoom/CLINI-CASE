"""Shared pytest fixtures for ClinCase tests.

Most agent tests don't need the DB — they hit the LLM and assert on the
output schema. The integration tests in tests/api/ DO need the DB; those
tests use the `case_row` fixture below.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Iterator

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fhir_bundle_factory():
    """Load a FHIR bundle fixture by filename (without .json)."""
    def _load(name: str) -> dict:
        return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def case_id() -> str:
    """Random unique case_id per test."""
    return f"test-{uuid.uuid4().hex[:8]}"
