"""The five demo scenarios are reproducible and demonstrate what they claim."""

from __future__ import annotations

from app.cardiotwin.schema import VESSELS


def _by_id(scenarios):
    return {s["id"]: s for s in scenarios}


def test_five_scenarios_exist(scenarios):
    assert sorted(_by_id(scenarios)) == ["A", "B", "C", "D", "E"]
    assert _by_id(scenarios)["D"]["source"] == "synthetic"


def test_low_high_and_mixed_patterns(model, scenarios):
    s = _by_id(scenarios)
    a = model.predict(s["A"]["patient"])
    assert (
        a["cad"]["probability"] < 0.3 and max(a["vessels"][v]["probability"] for v in VESSELS) < 0.3
    )
    b = model.predict(s["B"]["patient"])
    assert b["cad"]["probability"] > 0.8 and b["vessels"]["LAD"]["probability"] > 0.6
    c = model.predict(s["C"]["patient"])
    probs = sorted(c["vessels"][v]["probability"] for v in VESSELS)
    assert probs[-1] - probs[0] > 0.4  # genuinely vessel-specific
    assert c["vessels"]["LAD"]["probability"] == max(
        c["vessels"][v]["probability"] for v in VESSELS
    )


def test_ood_scenario_warns_but_still_predicts(model, scenarios):
    p = model.predict(_by_id(scenarios)["D"]["patient"])
    assert p["representativeness"]["status"] == "outside"
    assert p["warnings"][0]["code"] == "OUT_OF_DISTRIBUTION"


def test_counterfactual_scenario_produces_a_measurable_change(model, scenarios):
    e = _by_id(scenarios)["E"]
    cf = model.counterfactual(e["patient"], e["perturbation"])
    assert abs(cf["targets"]["LAD"]["delta"]) > 0.05
    assert cf["targets"]["LAD"]["within_model_uncertainty"] is False


def test_dataset_samples_carry_reference_labels_for_honesty(scenarios):
    for s in scenarios:
        if s["source"] == "dataset_sample":
            assert set(s["reference_labels"]) == {"Cath", "LAD", "LCX", "RCA"}
