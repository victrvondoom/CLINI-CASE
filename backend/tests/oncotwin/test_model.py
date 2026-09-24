"""Model artifact integrity, exact explanations, calibration metadata, reproducible training."""
from __future__ import annotations

import numpy as np

from app.oncotwin.engine.features import FEATURE_NAMES
from app.oncotwin.ml.logistic import auroc, average_precision, fit_logistic
from app.oncotwin.ml.model import load_model
from app.oncotwin.ml.train import train


def test_artifact_integrity_and_feature_contract():
    m = load_model()
    assert m.integrity_verified, "artifact sha256 does not match its contents"
    assert tuple(m.artifact["feature_names"]) == FEATURE_NAMES
    assert m.artifact["outcome_id"] == "OT-ACUTE-7" and m.artifact["horizon_days"] == 7
    t = m.thresholds
    assert 0 < t["watch"] < t["early_warning"] < t["high_priority"] < 1


def test_metrics_are_labelled_synthetic_and_complete():
    a = load_model().artifact
    assert "SYNTHETIC" in a["metrics"]["data"]
    dl = a["metrics"]["day_level"]
    assert 0.5 < dl["auroc"] <= 1.0 and 0 <= dl["brier"] < 0.25
    ev = a["metrics"]["event_level"]["early_warning_or_higher"]
    assert ev["events"] > 0 and 0 <= ev["sensitivity"] <= 1
    assert "population_threshold_rule" in a["comparators"]
    assert "same_model_without_personal_baseline" in a["comparators"]
    assert a["limitations"]


def test_contributions_explain_the_logit_exactly():
    m = load_model()
    x = m.lr.mean + np.random.default_rng(0).normal(size=len(FEATURE_NAMES)) * m.lr.std
    logit = m.lr.intercept + m.contributions(x).sum()
    assert abs(1 / (1 + np.exp(-logit)) - float(m.predict(x)[0])) < 1e-12


def test_bootstrap_interval_brackets_the_point_estimate():
    m = load_model()
    X = m.lr.mean + np.random.default_rng(1).normal(size=(50, len(FEATURE_NAMES))) * m.lr.std
    p, lo, hi = m.predict_interval(X)
    assert np.all((p >= 0) & (p <= 1))
    assert np.mean((lo <= p + 1e-9) & (p <= hi + 1e-9)) > 0.9


def test_metric_functions_on_known_values():
    y = np.array([0, 0, 1, 1])
    assert auroc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert auroc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0
    assert abs(average_precision(y, np.array([0.1, 0.2, 0.8, 0.9])) - 1.0) < 1e-12
    X = np.random.default_rng(2).normal(size=(400, 2))
    yy = (X[:, 0] + 0.2 * np.random.default_rng(3).normal(size=400) > 0).astype(float)
    assert fit_logistic(X, yy, 1.0).coef[0] > 1.0


def test_training_pipeline_is_reproducible():
    a = train(60, seed=77, write=False, verbose=False)
    b = train(60, seed=77, write=False, verbose=False)
    assert a["coef"] == b["coef"] and a["thresholds"] == b["thresholds"]
    assert a["sha256"] == b["sha256"]
