"""Target-leakage guarantees: labels can never be model inputs, for any target."""

from __future__ import annotations

import numpy as np
import pytest

from app.cardiotwin import training
from app.cardiotwin.data import encode_frame
from app.cardiotwin.features import (
    ENCODED_NAMES,
    LeakageError,
    assert_no_leakage,
    encode_record,
    forbidden_inputs,
)
from app.cardiotwin.schema import LABEL_COLUMNS, TARGET_ORDER


@pytest.mark.parametrize("target", TARGET_ORDER)
def test_real_input_set_is_clean_for_every_target(target):
    assert_no_leakage(list(ENCODED_NAMES), target)


@pytest.mark.parametrize("target", TARGET_ORDER)
@pytest.mark.parametrize("label", ["LAD", "LCX", "RCA", "Cath", "CAD"])
def test_each_label_is_rejected_for_each_target(target, label):
    # the overall label is the `Cath` column; the challenge's name "CAD" must be rejected as well
    with pytest.raises(LeakageError, match=label):
        assert_no_leakage([*ENCODED_NAMES, label], target)


def test_encoded_label_forms_are_rejected():
    for bad in ("LAD=Stenotic", "Cath_CAD", "RCA_stenotic", "CAD_flag"):
        with pytest.raises(LeakageError):
            assert_no_leakage([*ENCODED_NAMES, bad], "CAD")


def test_vessel_models_cannot_see_cad_or_sibling_vessels():
    for target in ("LAD", "LCX", "RCA"):
        forb = forbidden_inputs(target)
        assert {"Cath", "CAD", "LAD", "LCX", "RCA"} <= forb  # CAD and all siblings are excluded


def test_inference_rejects_label_columns():
    zeros = np.zeros(len(ENCODED_NAMES))
    for label in LABEL_COLUMNS:
        with pytest.raises(LeakageError):
            encode_record({label: "Stenotic"}, zeros)


def test_trained_artifact_has_no_label_inputs(model):
    assert not (set(model.artifact["encoded_names"]) & set(LABEL_COLUMNS))
    assert model.artifact["leakage_audit"]["status"] == "pass"
    assert set(model.artifact["leakage_audit"]["excluded_label_columns"]) == set(LABEL_COLUMNS)


def test_training_pipeline_fails_if_a_label_reaches_inputs(monkeypatch, df, tmp_path):
    """The guard sits inside train(): a poisoned encoder must abort training, not silently train."""

    def poisoned(frame):
        X, names = encode_frame(frame)
        return np.column_stack([X, np.zeros(len(frame))]), [*names, "LAD"]

    monkeypatch.setattr(training, "encode_frame", poisoned)
    with pytest.raises(LeakageError):
        training.train(
            tmp_path, n_repeats=1, n_splits=3, n_boot_cv=2, n_boot_final=5, challengers=False
        )


def test_leakage_matters_diagnostic(model):
    """Evidence that the guard is load-bearing: bypassing it would make CAD look near-perfect."""
    import json

    from app.cardiotwin.model import EVALUATION_PATH

    ev = json.loads(EVALUATION_PATH.read_text())
    assert ev["leakage_audit"]["bypass_demonstration"]["cad_auc_with_vessel_labels"] > 0.97
    for t in TARGET_ORDER:
        assert 0.4 < ev["leakage_audit"]["per_target"][t]["shuffled_label_auc"] < 0.6
