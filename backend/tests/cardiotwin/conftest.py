from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cardiotwin.data import load_dataset
from app.cardiotwin.model import SCENARIOS_PATH, CardioModel, load_model


@pytest.fixture(scope="session")
def df():
    return load_dataset()


@pytest.fixture(scope="session")
def model() -> CardioModel:
    return load_model()


@pytest.fixture(scope="session")
def scenarios() -> list[dict]:
    return json.loads(Path(SCENARIOS_PATH).read_text())["scenarios"]


def row_patient(df, i: int) -> dict:
    from app.cardiotwin.schema import FEATURE_NAMES

    r = df.iloc[i]
    return {c: (r[c].item() if hasattr(r[c], "item") else r[c]) for c in FEATURE_NAMES}
