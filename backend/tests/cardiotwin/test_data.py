"""Dataset loading, schema validation, target validation and encoding."""

from __future__ import annotations

import numpy as np
import pytest

from app.cardiotwin.data import (
    DATASET_CSV,
    DatasetError,
    encode_frame,
    file_sha256,
    label_relationships,
    load_dataset,
    target_vector,
    validate_dataset,
)
from app.cardiotwin.features import ENCODED_NAMES, RecordValidationError, encode_record
from app.cardiotwin.schema import EXPECTED_COLUMNS, FEATURE_NAMES, LABEL_COLUMNS, TARGET_ORDER

from .conftest import row_patient


def test_dataset_loads_and_matches_schema(df):
    assert df.shape == (303, 59)
    assert set(df.columns) == set(EXPECTED_COLUMNS)
    assert "Fmale" not in set(df["Sex"])  # dataset spelling normalised


def test_dataset_is_the_pinned_one(model):
    assert file_sha256(DATASET_CSV) == model.artifact["dataset"]["csv_sha256"]


def test_target_validation_and_prevalence(df):
    for t in TARGET_ORDER:
        y = target_vector(df, t)
        assert set(np.unique(y)) == {0, 1}
    assert target_vector(df, "CAD").sum() == 216
    assert target_vector(df, "LAD").sum() == 177


def test_label_relationships_document_the_leak(df):
    rel = label_relationships(df)
    assert rel["n"] == 303
    assert rel["cad_equals_any_vessel"] == 302  # vessel labels ~determine CAD => must not be inputs
    assert rel["cad_without_stenotic_vessel"] == 0
    assert rel["stenotic_vessel_without_cad"] == 1


def test_missing_column_rejected(df):
    with pytest.raises(DatasetError, match="missing columns"):
        validate_dataset(df.drop(columns=["Age"]))


def test_unexpected_column_rejected(df):
    bad = df.copy()
    bad["Mystery"] = 1
    with pytest.raises(DatasetError, match="unexpected columns"):
        validate_dataset(bad)


def test_missing_values_rejected(df):
    bad = df.copy()
    bad.loc[0, "Age"] = None
    with pytest.raises(DatasetError, match="missing values"):
        validate_dataset(bad)


def test_invalid_target_level_rejected(df):
    bad = df.copy()
    bad.loc[0, "LAD"] = "Maybe"
    with pytest.raises(DatasetError, match="target LAD"):
        validate_dataset(bad)


def test_invalid_feature_value_rejected(df):
    bad = df.copy()
    bad["Age"] = bad["Age"].astype(float)
    bad.loc[0, "Age"] = 400.0
    with pytest.raises(DatasetError, match="Age"):
        validate_dataset(bad)
    bad2 = df.copy()
    bad2.loc[0, "Dyspnea"] = "Perhaps"
    with pytest.raises(DatasetError, match="Dyspnea"):
        validate_dataset(bad2)


def test_load_missing_file_has_actionable_error(tmp_path):
    with pytest.raises(DatasetError, match="--import"):
        load_dataset(tmp_path / "nope.csv")


def test_encoding_shape_and_no_label_columns(df):
    X, names = encode_frame(df)
    assert X.shape == (303, len(ENCODED_NAMES)) and tuple(names) == ENCODED_NAMES
    assert not np.isnan(X).any()
    assert not (set(names) & set(LABEL_COLUMNS))
    assert (X.std(axis=0) > 0).all()  # constant 'Exertional CP' was excluded from the feature set


def test_inference_encoder_matches_training_encoder(df, model):
    """Preprocessing consistency: encoding a dict row == encoding the same row of the frame."""
    X, _ = encode_frame(df)
    for i in (0, 7, 150, 302):
        rec = encode_record(row_patient(df, i), model.impute)
        assert np.allclose(rec.vector, X[i]), i


def test_type_conversion_and_range_checks(model):
    ok = encode_record(
        {"Age": "55", "DM": "Y", "HTN": True, "Sex": "male", "VHD": "Moderate"}, model.impute
    )
    assert set(ok.provided) == {"Age", "DM", "HTN", "Sex", "VHD"}
    with pytest.raises(RecordValidationError) as e:
        encode_record({"Age": 500, "BP": "abc", "Sex": "robot"}, model.impute)
    assert len(e.value.problems) == 3
    with pytest.raises(RecordValidationError, match="unknown features"):
        encode_record({"NotAFeature": 1}, model.impute)
    assert len(FEATURE_NAMES) == 54
