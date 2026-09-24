"""Load the trained deterioration model artifact and serve explainable predictions."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin.engine.features import FEATURE_NAMES
from app.oncotwin.ml.logistic import LogisticModel

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "deterioration_lr_v1.json"


class ModelArtifactError(RuntimeError):
    pass


class DeteriorationModel:
    def __init__(self, artifact: dict[str, Any]):
        if tuple(artifact["feature_names"]) != FEATURE_NAMES:
            raise ModelArtifactError(
                "Model artifact feature set does not match the running feature code — retrain with "
                "`python -m app.oncotwin.ml.train`."
            )
        self.artifact = artifact
        self.lr = LogisticModel(
            intercept=float(artifact["intercept"]), coef=np.array(artifact["coef"]),
            mean=np.array(artifact["mean"]), std=np.array(artifact["std"]), l2=float(artifact["l2"]),
        )
        boots = np.array(artifact.get("bootstrap") or [[artifact["intercept"], *artifact["coef"]]])
        self.boot_intercepts = boots[:, 0]
        self.boot_coefs = boots[:, 1:]
        self.thresholds = {k: float(v) for k, v in artifact["thresholds"].items() if k != "derivation"}
        payload = json.dumps({k: v for k, v in artifact.items() if k not in ("training", "sha256")}, sort_keys=True).encode()
        self.integrity_verified = hashlib.sha256(payload).hexdigest() == artifact.get("sha256")

    @property
    def model_id(self) -> str:
        return self.artifact["model_id"]

    @property
    def version(self) -> str:
        return self.artifact["version"]

    @property
    def sha256(self) -> str:
        return self.artifact.get("sha256", "")

    def version_info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "version": self.version, "artifact_sha256": self.sha256,
                "integrity_verified": self.integrity_verified, "outcome_id": self.artifact["outcome_id"],
                "horizon_days": self.artifact["horizon_days"]}

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.lr.predict_proba(np.atleast_2d(X))

    def predict_interval(self, X: np.ndarray, lo: float = 10, hi: float = 90) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        X = np.atleast_2d(X)
        Z = self.lr.standardise(X)
        logits = self.boot_intercepts[None, :] + Z @ self.boot_coefs.T      # (N, B)
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -35, 35)))
        return self.predict(X), np.percentile(probs, lo, axis=1), np.percentile(probs, hi, axis=1)

    def contributions(self, x: np.ndarray) -> np.ndarray:
        return self.lr.contributions(np.asarray(x))

    def card(self) -> dict[str, Any]:
        a = self.artifact
        coefs = sorted(zip(a["feature_names"], a["coef"], strict=True), key=lambda kv: -abs(kv[1]))
        return {
            **self.version_info(),
            "algorithm": a["algorithm"],
            "outcome": a["outcome"],
            "features": [{"name": n, "coef_standardised": round(c, 4)} for n, c in coefs],
            "intercept": a["intercept"],
            "l2": a["l2"],
            "thresholds": a["thresholds"],
            "metrics": a["metrics"],
            "comparators": a["comparators"],
            "training": a["training"],
            "limitations": a["limitations"],
            "n_bootstrap": int(len(self.boot_intercepts)),
        }


@lru_cache(maxsize=1)
def load_model(path: str | None = None) -> DeteriorationModel:
    p = Path(path) if path else ARTIFACT_PATH
    if not p.exists():
        raise ModelArtifactError(
            f"OncoTwin model artifact not found at {p}. Train it with `python -m app.oncotwin.ml.train`."
        )
    return DeteriorationModel(json.loads(p.read_text(encoding="utf-8")))
