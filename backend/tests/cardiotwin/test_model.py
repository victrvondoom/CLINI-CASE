"""Inference: determinism, probability sanity, exact attribution, consistency, OOD, counterfactuals, integrity."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.cardiotwin.features import LeakageError, RecordValidationError
from app.cardiotwin.model import (
    ARTIFACT_PATH,
    CardioModel,
    ModelArtifactError,
    canonical_sha256,
    load_model,
)
from app.cardiotwin.schema import TARGET_ORDER, VESSELS

from .conftest import row_patient

ROWS = (0, 3, 40, 111, 202, 299)


def _all_probs(p):
    return [p["cad"], *(p["vessels"][v] for v in VESSELS)]


def test_artifact_loads_and_is_integrity_verified(model):
    info = model.version_info()
    assert info["integrity_verified"] is True
    assert len(info["artifact_sha256"]) == 64
    assert info["model_id"] == "cardiotwin-lr-multivessel"


def test_inference_is_deterministic(model, df):
    pt = row_patient(df, 5)
    a, b = model.predict(pt), model.predict(pt)
    for key in ("cad", "vessels", "explanations", "representativeness", "warnings"):
        assert a[key] == b[key]
    assert a["provenance"]["input_sha256"] == b["provenance"]["input_sha256"]


def test_probabilities_are_valid_and_intervals_ordered(model, df):
    for i in ROWS:
        for t in _all_probs(model.predict(row_patient(df, i))):
            assert 0.0 <= t["probability"] <= 1.0 and 0.0 <= t["model_probability"] <= 1.0
            lo, hi = t["interval_80"]
            assert 0.0 <= lo <= hi <= 1.0
            assert t["confidence"] in ("low", "moderate", "high")
            assert t["band"] in ("low", "intermediate", "elevated")


def test_hierarchical_consistency_cad_never_below_any_vessel(model, df):
    for i in range(0, 303, 7):
        p = model.predict(row_patient(df, i))
        assert (
            p["cad"]["probability"] >= max(p["vessels"][v]["probability"] for v in VESSELS) - 1e-9
        )


def test_attribution_is_exact_and_additive(model, df):
    """baseline + Σ contributions reproduces the calibrated logit → the reported probability (before CAD projection)."""
    for i in ROWS:
        p = model.predict(row_patient(df, i))
        for t in TARGET_ORDER:
            ex = p["explanations"][t]
            block = p["cad"] if t == "CAD" else p["vessels"][t]
            implied = 1 / (1 + np.exp(-ex["sum_check_logit"]))
            expected = block.get("unadjusted_probability", block["probability"])
            assert implied == pytest.approx(expected, abs=2e-4), (i, t)
            assert sum(f["contribution"] for f in ex["features"]) + ex[
                "baseline_logit"
            ] == pytest.approx(ex["sum_check_logit"], abs=5e-4 * len(ex["features"]))


def test_vessel_explanations_differ_between_vessels(model, df):
    p = model.predict(row_patient(df, 111))
    tops = {
        t: tuple(f["feature"] for f in p["explanations"][t]["features"][:4]) for t in TARGET_ORDER
    }
    assert len(set(tops.values())) > 1  # LAD / LCX / RCA / CAD do not share one generic explanation


def test_missing_features_are_imputed_and_flagged(model):
    p = model.predict({})
    assert p["feature_completeness"]["provided"] == 0
    assert any(w["code"] == "LOW_FEATURE_COMPLETENESS" for w in p["warnings"])
    assert p["cad"]["confidence"] == "low"
    part = model.predict({"Age": 60, "Sex": "Male", "BP": 140})
    assert part["feature_completeness"]["provided"] == 3
    assert "Age" not in part["feature_completeness"]["imputed"]


def test_bad_input_is_rejected_not_guessed(model):
    with pytest.raises(RecordValidationError):
        model.predict({"Age": -3})
    with pytest.raises(RecordValidationError):
        model.predict({"Dyspnea": "sometimes"})
    with pytest.raises(LeakageError):
        model.predict({"LAD": "Stenotic"})


def test_representativeness_flags_unlike_patients(model, df, scenarios):
    typical = model.predict(row_patient(df, 40))["representativeness"]
    assert typical["status"] == "representative"
    weird = next(s for s in scenarios if s["id"] == "D")
    p = model.predict(weird["patient"])
    assert p["representativeness"]["status"] == "outside"
    assert p["cad"]["confidence"] == "low"
    assert any(w["code"] == "OUT_OF_DISTRIBUTION" for w in p["warnings"])
    assert p["representativeness"]["out_of_range_features"]
    # ...but a prediction is still returned, together with the warning
    assert 0 <= p["cad"]["probability"] <= 1


def test_counterfactual_matches_direct_evaluation(model, df):
    pt = row_patient(df, 111)
    cf = model.counterfactual(pt, {"LDL": 90})
    direct = model.predict({**pt, "LDL": 90})
    assert (
        cf["perturbed"]["vessels"]["LAD"]["probability"] == direct["vessels"]["LAD"]["probability"]
    )
    for t in TARGET_ORDER:
        r = cf["targets"][t]
        assert r["delta"] == pytest.approx(r["after"] - r["before"], abs=1e-4)
    assert (
        cf["changes"][0]["feature"] == "LDL"
        and "not a treatment recommendation" in cf["label"].lower()
    )
    with pytest.raises(RecordValidationError):
        model.counterfactual(pt, {"Nope": 1})


def test_counterfactual_direction_follows_the_model(model, df):
    """A change that the linear model says lowers LAD must lower it (no sign errors in the simulator)."""
    pt = row_patient(df, 111)
    base = model.predict(pt)
    coef = {f["feature"]: f["contribution"] for f in base["explanations"]["LAD"]["features"]}
    assert coef["EF-TTE"] > 0  # low EF raises LAD here
    cf = model.counterfactual(pt, {"EF-TTE": 60})
    assert cf["targets"]["LAD"]["delta"] < 0


def test_sensitivity_curve(model, df):
    r = model.sensitivity(row_patient(df, 111), "Age", points=9)
    assert len(r["curve"]) == 9
    assert all(0 <= c["LAD"] <= 1 for c in r["curve"])
    assert r["curve"][0]["value"] < r["curve"][-1]["value"]
    assert len(model.sensitivity(row_patient(df, 111), "DM")["curve"]) == 2
    with pytest.raises(RecordValidationError):
        model.sensitivity({}, "Nope")


def test_provenance_and_safety_fields(model, df):
    p = model.predict(row_patient(df, 3), scenario_id="X")
    prov = p["provenance"]
    assert (
        prov["scenario_id"] == "X"
        and prov["integrity_verified"]
        and prov["leakage_audit"] == "pass"
    )
    assert prov["prediction_timestamp"].endswith("+00:00")
    assert "not a substitute" in p["safety_notice"]
    assert "lesion" in p["claims"]["is_not"].lower()
    assert set(p["visualization"]["vessels"]) == set(VESSELS)


def test_tampered_artifact_is_refused(tmp_path):
    a = json.loads(ARTIFACT_PATH.read_text())
    a["targets"]["LAD"]["coef"][0] += 0.5
    assert canonical_sha256(a) != a["sha256"]
    assert CardioModel(a).integrity_verified is False
    p = tmp_path / "tampered.json"
    p.write_text(json.dumps(a))
    load_model.cache_clear()
    with pytest.raises(ModelArtifactError, match="integrity"):
        load_model(str(p))
    load_model.cache_clear()


def test_missing_or_corrupt_artifact_is_a_clear_error(tmp_path):
    load_model.cache_clear()
    with pytest.raises(ModelArtifactError, match="missing"):
        load_model(str(tmp_path / "absent.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ModelArtifactError, match="valid JSON"):
        load_model(str(bad))
    load_model.cache_clear()


def test_encoder_layout_mismatch_is_detected():
    a = json.loads(ARTIFACT_PATH.read_text())
    a["encoded_names"] = a["encoded_names"][:-1]
    with pytest.raises(ModelArtifactError, match="layout"):
        CardioModel(a)


def test_reported_performance_is_real_and_sane(model):
    m = model.artifact["targets"]
    assert m["CAD"]["cv_summary"]["roc_auc"] > 0.85
    for t in TARGET_ORDER:
        s = m[t]["cv_summary"]
        lo, hi = s["roc_auc_ci95"]
        assert lo < s["roc_auc"] < hi and lo > 0.5  # better than chance, CI is reported
        assert m[t]["calibration"]["method"] in ("none", "platt")


def test_serving_path_does_not_need_training_dependencies():
    """The API imports only numpy: sklearn / pandas / scipy are training-time dependencies."""
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        for m in ("sklearn", "pandas", "scipy", "openpyxl"):
            sys.modules[m] = None
        import app.api.cardiotwin
        from app.cardiotwin.model import load_model
        p = load_model().predict({"Age": 60})
        assert 0 <= p["cad"]["probability"] <= 1
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
