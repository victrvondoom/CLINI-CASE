"""Synthetic cohort dataset for research experiments — cached, versioned, reproducible.

Defaults reproduce EXACTLY the cohort and patient split the deployed OT-ACUTE-7
model was trained on (`ml/train.py`: seed 20260923, 1 000 patients, 60/20/20 by
patient), so every experiment is evaluated on the same untouched test patients.

The dataset version is a SHA-256 over (seed, size, split rule, OncoTwin version
and the source code of the generator + feature pipeline): change any of them and
the version — and the cache key — changes.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import pickle
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin import ONCOTWIN_VERSION
from app.oncotwin.engine.baseline import Baseline, compute_baseline
from app.oncotwin.engine.features import feature_tensor, series_context, signal_matrix
from app.oncotwin.engine.neutrophil import NeutrophilTwin
from app.oncotwin.engine.series import build_series
from app.oncotwin.ml.train import COHORT_SEED, PatientData, labels_from_record
from app.oncotwin.records import SimulationTruth
from app.oncotwin.simulator.cohort import cohort_script
from app.oncotwin.simulator.patients import simulate

CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "oncotwin"
DEFAULT_N = 1000
_SOURCES = ("simulator/patients.py", "simulator/physiology.py", "simulator/cohort.py", "simulator/regimens.py",
            "engine/features.py", "engine/baseline.py", "engine/series.py", "engine/quality.py", "engine/neutrophil.py")


@dataclass
class CohortPatient:
    data: PatientData
    baseline: Baseline
    ctx: dict[str, Any]
    truth: SimulationTruth
    regimen: str
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cohort:
    seed: int
    n: int
    version: str
    patients: list[CohortPatient]
    split: dict[str, list[int]]
    built_seconds: float

    def part(self, name: str) -> list[CohortPatient]:
        return [self.patients[i] for i in self.split[name]]

    def meta(self) -> dict[str, Any]:
        return {"dataset_id": f"synthetic-cohort-{self.seed}-{self.n}", "version": self.version, "seed": self.seed,
                "n_patients": self.n, "split": {k: len(v) for k, v in self.split.items()},
                "split_rule": "by patient, 60/20/20, numpy default_rng(seed).permutation — identical to ml/train.py",
                "n_events": sum(len(p.data.onsets) for p in self.patients),
                "built_seconds": round(self.built_seconds, 1), "synthetic": True}


def dataset_version(n: int, seed: int) -> str:
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256(json.dumps({"n": n, "seed": seed, "oncotwin": ONCOTWIN_VERSION, "split": "60/20/20"}).encode())
    for rel in _SOURCES:
        h.update((root / rel).read_bytes())
    return h.hexdigest()[:16]


def build_patient(index: int, seed: int) -> CohortPatient:
    sim = simulate(cohort_script(index, seed))
    rec = sim.record
    series = build_series(rec, rec.n_days)
    baseline = compute_baseline(series)
    ctx = series_context(series, NeutrophilTwin(series))
    F = feature_tensor(signal_matrix(series), baseline, **ctx)[0]
    y, eligible, onsets = labels_from_record(series, rec.n_days)
    data = PatientData(rec.profile.patient_id, series, F, y, eligible, onsets, series.acute_care_mask(),
                       np.asarray(ctx["nadir"], dtype=float))
    return CohortPatient(data=data, baseline=baseline, ctx=ctx, truth=sim.truth, regimen=rec.profile.regimen_code)


def build_cohort(n: int = DEFAULT_N, seed: int = COHORT_SEED,
                 progress: Callable[[int, int], None] | None = None) -> Cohort:
    t0 = time.time()
    patients = []
    for i in range(n):
        patients.append(build_patient(i, seed))
        if progress and (i % 10 == 0 or i == n - 1):
            progress(i + 1, n)
    order = np.random.default_rng(seed).permutation(n)
    n_tr, n_va = int(0.6 * n), int(0.2 * n)
    split = {"train": order[:n_tr].tolist(), "valid": order[n_tr:n_tr + n_va].tolist(),
             "test": order[n_tr + n_va:].tolist()}
    return Cohort(seed, n, dataset_version(n, seed), patients, split, time.time() - t0)


_MEMO: dict[tuple[int, int], Cohort] = {}


def load_cohort(n: int = DEFAULT_N, seed: int = COHORT_SEED, *, rebuild: bool = False,
                progress: Callable[[int, int], None] | None = None) -> Cohort:
    """In-process memo → on-disk cache (gzip pickle, local only, never committed) → build.

    Security note: pickle is used ONLY for this developer cache of synthetic data that
    this module itself wrote, at a fixed path under backend/.cache (gitignored). No API
    accepts a path, and nothing is ever unpickled from user input or the network. Delete
    the directory (or pass rebuild=True) to regenerate from the deterministic generator.
    """
    key = (n, seed)
    version = dataset_version(n, seed)
    if not rebuild and key in _MEMO and _MEMO[key].version == version:
        return _MEMO[key]
    path = CACHE_DIR / f"cohort_{seed}_{n}_{version}.pkl.gz"
    if not rebuild and path.exists():
        with gzip.open(path, "rb") as f:
            cohort = pickle.load(f)
    else:
        cohort = build_cohort(n, seed, progress)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with gzip.open(tmp, "wb", compresslevel=3) as f:
            pickle.dump(cohort, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)
    _MEMO[key] = cohort
    return cohort
