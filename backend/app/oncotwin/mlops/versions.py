"""Content-addressed versions for lineage: which features, which data, which model."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.oncotwin.engine.features import FEATURE_NAMES

_ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def feature_version() -> str:
    """SHA-256 over the feature names and the feature / baseline / series code that computes them."""
    h = hashlib.sha256(json.dumps(list(FEATURE_NAMES)).encode())
    for rel in ("engine/features.py", "engine/baseline.py", "engine/series.py", "engine/quality.py", "engine/neutrophil.py"):
        h.update((_ROOT / rel).read_bytes())
    return h.hexdigest()[:16]


@lru_cache(maxsize=1)
def training_dataset_version() -> str:
    """Version of the synthetic cohort the deployed model was trained on (seed/size from its artifact)."""
    from app.oncotwin.ml.model import load_model
    from app.oncotwin.research.dataset import dataset_version

    tr = load_model().artifact["training"]
    return dataset_version(int(tr["n_patients"]), int(tr["cohort_seed"]))
