"""Shared OncoTwin fixtures — simulated once per session (deterministic, synthetic)."""
from __future__ import annotations

import pytest

from app.oncotwin.simulator.archetypes import DEMO_SCRIPTS
from app.oncotwin.simulator.patients import simulate


@pytest.fixture(scope="session")
def demo_sims():
    return {pid: simulate(script) for pid, script in DEMO_SCRIPTS.items()}
