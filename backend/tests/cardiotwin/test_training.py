"""Training is reproducible and writes verifiable artifacts (small configuration; the full run is in the docs)."""

from __future__ import annotations

import json

import pytest

from app.cardiotwin.model import CardioModel
from app.cardiotwin.training import train

QUICK = {"n_splits": 3, "n_repeats": 1, "n_boot_cv": 3, "n_boot_final": 8, "challengers": False}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("ct")
    return out, train(out, **QUICK)


def test_writes_artifact_report_and_scenarios(run):
    out, res = run
    for name in ("cardiotwin_lr_v1.json", "evaluation.json", "scenarios.json"):
        assert (out / name).exists()
    m = CardioModel(json.loads((out / "cardiotwin_lr_v1.json").read_text()))
    assert m.integrity_verified
    assert set(res["evaluation"]["targets"]) == {"CAD", "LAD", "LCX", "RCA"}


def test_training_is_deterministic(run, tmp_path):
    _, res = run
    again = train(tmp_path, **QUICK)
    assert again["artifact"]["sha256"] == res["artifact"]["sha256"]


def test_report_metrics_come_from_the_run(run):
    _, res = run
    ev = res["evaluation"]
    assert ev["artifact_sha256"] == res["artifact"]["sha256"]
    oof = ev["out_of_fold"]["probabilities"]["CAD"]
    assert len(oof) == 303 and all(0 <= p <= 1 for p in oof)
    for t in ("CAD", "LAD", "LCX", "RCA"):
        s = ev["targets"][t]["cv_summary"]
        assert s["roc_auc_ci95"][0] < s["roc_auc"] < s["roc_auc_ci95"][1]
    assert ev["leakage_audit"]["status"] == "pass"
    assert ev["consistency"]["independent_model_violation_rate"] >= 0
