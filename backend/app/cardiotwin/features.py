"""Raw record -> numeric feature vector, plus the target-leakage guard.

Encoding (deterministic, no learned state):
  binary       Y/N or 0/1                    -> 0/1
  numeric      float                         -> float
  ordinal      index of the level in options -> float   (e.g. VHD: N=0 ... Severe=3)
  categorical  one-hot against the first level (Sex -> Sex=Male, BBB -> LBBB, RBBB)

The encoder is shared by training and inference so the two cannot drift.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.cardiotwin.schema import (
    FEATURE_INDEX,
    FEATURES,
    LABEL_COLUMNS,
    TARGETS,
    EncodedRecord,
    FeatureSpec,
)


class LeakageError(ValueError):
    """Raised when a label column (or anything derived from one) reaches a model input."""


class RecordValidationError(ValueError):
    """Raised for unknown features or values that are not physiologically valid."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


# ---------------------------------------------------------------------------
# Encoded column layout
# ---------------------------------------------------------------------------


def _encoded_columns(spec: FeatureSpec) -> list[str]:
    if spec.kind == "categorical":
        return [f"{spec.name}={o}" for o in spec.options[1:]]
    return [spec.name]


ENCODED_NAMES: tuple[str, ...] = tuple(c for f in FEATURES for c in _encoded_columns(f))
#: encoded column -> raw feature name (used to aggregate attributions back to a clinical feature)
ENCODED_TO_RAW: dict[str, str] = {c: f.name for f in FEATURES for c in _encoded_columns(f)}
RAW_TO_ENCODED_IDX: dict[str, list[int]] = {}
for _i, _c in enumerate(ENCODED_NAMES):
    RAW_TO_ENCODED_IDX.setdefault(ENCODED_TO_RAW[_c], []).append(_i)


# ---------------------------------------------------------------------------
# Leakage guard
# ---------------------------------------------------------------------------


def forbidden_inputs(target: str) -> frozenset[str]:
    """Columns that must never be model inputs when predicting `target`.

    All four label columns are forbidden for every target: the vessel labels
    determine the overall label almost exactly (302 / 303 rows), so a CAD model
    that saw LAD/LCX/RCA — or a vessel model that saw CAD (`Cath`) or a sibling
    vessel — would be reading the answer, not predicting it.
    """
    if target not in TARGETS:
        raise KeyError(f"unknown target {target!r}; expected one of {sorted(TARGETS)}")
    # "CAD" is the challenge's name for the overall label (dataset column `Cath`); reject both spellings.
    return frozenset(LABEL_COLUMNS) | {"CAD"}


def assert_no_leakage(input_columns: list[str] | tuple[str, ...], target: str) -> None:
    """Fail loudly if any forbidden (label-derived) column is among the inputs."""
    forbidden = forbidden_inputs(target)
    lowered = {c.lower() for c in forbidden}
    bad = []
    for col in input_columns:
        raw = ENCODED_TO_RAW.get(col, col)
        # exact label names, and encoded forms like 'LAD=Stenotic' / 'Cath_CAD'
        base = raw.split("=")[0].split("_")[0].strip()
        if raw in forbidden or base.lower() in lowered or raw.lower() in lowered:
            bad.append(col)
    if bad:
        raise LeakageError(
            f"target-leakage: forbidden columns in {target} model inputs: {sorted(bad)}"
        )


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------

_TRUE = {"y", "yes", "true", "1", "t"}
_FALSE = {"n", "no", "false", "0", "f"}


def _coerce(spec: FeatureSpec, value: Any) -> float | tuple[float, ...]:
    """Return the encoded value(s) for one raw feature. Raises ValueError on bad input."""
    if spec.kind == "binary":
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        s = str(value).strip().lower()
        if s in _TRUE:
            return 1.0
        if s in _FALSE:
            return 0.0
        try:
            f = float(s)
        except ValueError as e:
            raise ValueError(f"{spec.name}: expected Y/N or 0/1, got {value!r}") from e
        if f in (0.0, 1.0):
            return f
        raise ValueError(f"{spec.name}: expected Y/N or 0/1, got {value!r}")

    if spec.kind == "numeric":
        try:
            f = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{spec.name}: expected a number, got {value!r}") from e
        if not math.isfinite(f):
            raise ValueError(f"{spec.name}: value must be finite")
        if spec.lo is not None and f < spec.lo or spec.hi is not None and f > spec.hi:
            raise ValueError(
                f"{spec.name}: {f:g} outside the valid range [{spec.lo:g}, {spec.hi:g}]"
            )
        return f

    # ordinal / categorical: match an option (case-insensitive); ordinal also accepts its index
    text = str(value).strip()
    if text.lower() == "fmale":  # dataset spelling
        text = "Female"
    lookup = {o.lower(): i for i, o in enumerate(spec.options)}
    if text.lower() in lookup:
        idx = lookup[text.lower()]
    elif spec.kind == "ordinal":
        try:
            idx = int(float(text))
        except ValueError as e:
            raise ValueError(
                f"{spec.name}: expected one of {list(spec.options)}, got {value!r}"
            ) from e
        if not 0 <= idx < len(spec.options):
            raise ValueError(f"{spec.name}: expected one of {list(spec.options)}, got {value!r}")
    else:
        raise ValueError(f"{spec.name}: expected one of {list(spec.options)}, got {value!r}")
    if spec.kind == "ordinal":
        return float(idx)
    return tuple(1.0 if idx == k else 0.0 for k in range(1, len(spec.options)))


# ---------------------------------------------------------------------------
# Record encoding (inference + tests)
# ---------------------------------------------------------------------------


def encode_record(values: dict[str, Any], impute: np.ndarray) -> EncodedRecord:
    """Validate + encode one patient. Missing/None features take `impute` (training medians)."""
    problems: list[str] = []
    unknown = sorted(set(values) - set(FEATURE_INDEX))
    if unknown:
        forbidden = sorted(set(unknown) & set(LABEL_COLUMNS))
        if forbidden:
            raise LeakageError(
                f"label columns are not accepted as inputs: {forbidden} (they are the prediction targets)"
            )
        problems.append(f"unknown features: {unknown}")

    vec = np.array(impute, dtype=float).copy()
    provided: list[str] = []
    imputed: list[str] = []
    for spec in FEATURES:
        v = values.get(spec.name)
        idxs = RAW_TO_ENCODED_IDX[spec.name]
        if v is None or (isinstance(v, str) and v.strip() == ""):
            imputed.append(spec.name)
            continue
        try:
            enc = _coerce(spec, v)
        except ValueError as e:
            problems.append(str(e))
            continue
        enc_t = enc if isinstance(enc, tuple) else (enc,)
        for i, e in zip(idxs, enc_t, strict=True):
            vec[i] = e
        provided.append(spec.name)
    if problems:
        raise RecordValidationError(problems)
    return EncodedRecord(raw=dict(values), vector=vec.tolist(), provided=provided, imputed=imputed)
