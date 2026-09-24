"""Baseline, deviation analytics, data quality, no-look-ahead, confidence."""
from __future__ import annotations

import numpy as np

from app.oncotwin.engine.baseline import (
    adverse_z,
    compute_baseline,
    cusum,
    jumps,
    persistence,
    rolling_slope,
)
from app.oncotwin.engine.features import IDX, series_features
from app.oncotwin.engine.neutrophil import NeutrophilTwin
from app.oncotwin.engine.series import build_series
from app.oncotwin.engine.state import confidence, estimate_latent
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS


def test_baseline_is_robust_and_floored(demo_sims):
    s = build_series(demo_sims["ot-001"].record, 30)
    b = compute_baseline(s)
    assert b.window == (1, 13) and b.kind == "pre-treatment"
    for key in MODEL_SIGNALS:
        sb = b.signals[key]
        assert sb.established and sb.spread_t >= SIGNALS[key].spread_floor
        disp = sb.display()
        assert disp["low"] < disp["median"] < disp["high"]


def test_adverse_z_is_direction_aware(demo_sims):
    s = build_series(demo_sims["ot-001"].record, 20)
    b = compute_baseline(s)
    vals = np.array([[b.signals[k].median_t for k in MODEL_SIGNALS]])[None]
    hr, hrv = MODEL_SIGNALS.index("resting_hr"), MODEL_SIGNALS.index("hrv_sdnn")
    shifted = vals.copy()
    shifted[..., hr] += 3 * b.signals["resting_hr"].spread_t      # HR up  → adverse
    shifted[..., hrv] += 3 * b.signals["hrv_sdnn"].spread_t       # HRV up → favourable
    z = adverse_z(shifted, b)[0, 0]
    assert abs(z[hr] - 3.0) < 1e-9
    assert abs(z[hrv] + 3.0) < 1e-9


def test_temporal_analytics_on_a_known_sequence():
    z = np.array([0, 0, 1, 2, 3, 3.5, 0.2, np.nan, 2.1], dtype=float).reshape(1, -1, 1)
    slope = rolling_slope(z, 3)[0, :, 0]
    assert abs(slope[4] - 1.0) < 1e-9                       # 1 → 2 → 3
    pers = persistence(z, 1.5)[0, :, 0]
    assert list(pers[:7]) == [0, 0, 0, 1, 2, 3, 0] and pers[7] == 0 and pers[8] == 1
    assert cusum(z)[0, 5, 0] > 4.0                          # sustained drift alarm
    assert abs(jumps(z)[0, 3, 0] - 1.0) < 1e-9


def test_quality_engine_detects_injected_problems(demo_sims):
    s = build_series(demo_sims["ot-004"].record, 46)
    kinds = {(f.kind, f.signal) for f in s.flags}
    assert ("stuck", "spo2") in kinds
    assert ("implausible", "resting_hr") in kinds
    assert ("conflict", "weight") in kinds
    assert np.isnan(s.values["resting_hr"][44])             # the 250-bpm artefact is excluded
    assert not any(f.kind == "stuck" and f.signal != "spo2" for f in s.flags)   # no false stuck calls


def test_gap_lowers_completeness_and_confidence(demo_sims):
    rec = demo_sims["ot-004"].record
    during_gap = build_series(rec, 31)                      # watch not worn Day 30–31
    normal = build_series(rec, 28)
    assert during_gap.quality["steps"].completeness_7d < normal.quality["steps"].completeness_7d
    assert not during_gap.quality["steps"].fresh
    c_gap = confidence(during_gap, compute_baseline(during_gap), 0.02, 0.01, 0.03)
    c_ok = confidence(normal, compute_baseline(normal), 0.02, 0.01, 0.03)
    assert c_gap["score"] < c_ok["score"]
    assert c_gap["components"]["input_freshness"] < 1.0


def test_features_have_no_look_ahead(demo_sims):
    """Features for day t must be identical whether or not later data exist."""
    rec = demo_sims["ot-001"].record
    full = build_series(rec, 40)
    F_full = series_features(full, compute_baseline(full), NeutrophilTwin(full))
    for t in (18, 22, 25, 27):
        s = build_series(rec, t)
        F_t = series_features(s, compute_baseline(s), NeutrophilTwin(s))
        assert np.allclose(F_t[t - 1], F_full[t - 1]), f"leakage at day {t}"


def test_latent_estimate_tracks_ground_truth(demo_sims):
    sim = demo_sims["ot-002"]
    s = build_series(sim.record, 27)
    est = estimate_latent(s, compute_baseline(s))["raw"][23:27, 1]     # dehydration load, Days 24–27
    truth = np.array(sim.truth.dehydration[23:27])
    assert abs(float(est.mean()) - float(truth.mean())) < 0.35


def test_neutrophil_twin_fits_labs(demo_sims):
    sim = demo_sims["ot-001"]
    s = build_series(sim.record, 25)
    fit = NeutrophilTwin(s).fit(25)
    est = fit.estimate(25)
    assert est["source"] == "fitted twin"
    assert est["p10"] <= est["mean"] <= est["p90"]
    assert abs(np.log(est["mean"]) - np.log(sim.truth.anc_true[24])) < 0.5
    assert fit.labs_used[-1][0] <= 25


def test_nadir_feature_reflects_treatment_timing(demo_sims):
    s = build_series(demo_sims["ot-001"].record, 30)
    F = series_features(s, compute_baseline(s))
    assert F[10, IDX["nadir_risk"]] == 0.0                   # before cycle 1
    assert F[23, IDX["nadir_risk"]] > F[16, IDX["nadir_risk"]]
