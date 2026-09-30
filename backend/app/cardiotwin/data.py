"""Dataset loading, schema validation and reproducible import.

The dataset (UCI id 411, CC BY 4.0, 303 rows) is small enough to be committed
as CSV with attribution — see `backend/data/cardiotwin/README.md`. The import
script re-derives that CSV from the official UCI download and verifies hashes.
"""

from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from app.cardiotwin.features import (
    ENCODED_NAMES,
    RAW_TO_ENCODED_IDX,
    _coerce,
)
from app.cardiotwin.schema import (
    EXPECTED_COLUMNS,
    FEATURES,
    SOURCE_DATASET,
    TARGETS,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cardiotwin"
DATASET_CSV = DATA_DIR / "z_alizadeh_sani_extension.csv"
#: SHA-256 of the official UCI zip the CSV was derived from (checked by the import script).
SOURCE_ZIP_SHA256 = "e97af1a18733d64fa88caa0628e5fe7ce6b2e26ec4c7ee03baade92a6f1470e8"


class DatasetError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    content = Path(path).read_bytes()
    # Git may check text files out with CRLF on Windows. Hash CSVs by their
    # canonical LF representation so the pinned dataset identity is stable
    # across platforms while still detecting any data/content change.
    if Path(path).suffix.lower() == ".csv":
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def load_dataset(path: Path | None = None) -> Any:
    """Load + validate the raw dataset. Returns a pandas DataFrame with original column names."""
    import pandas as pd

    p = Path(path) if path else DATASET_CSV
    if not p.exists():
        raise DatasetError(
            f"dataset not found at {p}. Run `python -m app.cardiotwin.data --import` (see data/cardiotwin/README.md)."
        )
    df = pd.read_csv(p, keep_default_na=False, na_values=[""])
    validate_dataset(df)
    df = df.copy()
    df["Sex"] = df["Sex"].replace({"Fmale": "Female"})
    return df


def validate_dataset(df: Any) -> None:
    """Schema, value and target validation. Raises DatasetError listing every problem."""
    problems: list[str] = []
    cols = set(df.columns)
    missing = sorted(EXPECTED_COLUMNS - cols)
    extra = sorted(cols - EXPECTED_COLUMNS)
    if missing:
        problems.append(f"missing columns: {missing}")
    if extra:
        problems.append(f"unexpected columns: {extra}")
    if problems:
        raise DatasetError("; ".join(problems))
    if len(df) == 0:
        raise DatasetError("dataset has no rows")
    if df[list(EXPECTED_COLUMNS)].isna().any().any():
        bad = df[list(EXPECTED_COLUMNS)].isna().sum()
        raise DatasetError(f"missing values: {bad[bad > 0].to_dict()}")

    for target, (col, positive) in TARGETS.items():
        levels = set(df[col].astype(str).unique())
        if positive not in levels or len(levels) != 2:
            problems.append(
                f"target {target} ({col}): expected two levels incl. {positive!r}, got {sorted(levels)}"
            )
        elif df[col].astype(str).eq(positive).nunique() < 2:
            problems.append(f"target {target} has a single class")

    for spec in FEATURES:
        for v in df[spec.name].astype(object).unique():
            vv = "Female" if spec.name == "Sex" and str(v) == "Fmale" else v
            try:
                _coerce(spec, vv)
            except ValueError as e:
                problems.append(str(e))
                break
    if problems:
        raise DatasetError("; ".join(problems))


def encode_frame(df: Any) -> tuple[np.ndarray, list[str]]:
    """Encode a validated DataFrame with the same encoder used at inference."""
    X = np.zeros((len(df), len(ENCODED_NAMES)))
    for spec in FEATURES:
        idxs = RAW_TO_ENCODED_IDX[spec.name]
        for r, v in enumerate(df[spec.name].tolist()):
            vv = "Female" if spec.name == "Sex" and str(v) == "Fmale" else v
            enc = _coerce(spec, vv)
            enc_t = enc if isinstance(enc, tuple) else (enc,)
            for i, e in zip(idxs, enc_t, strict=True):
                X[r, i] = e
    return X, list(ENCODED_NAMES)


def target_vector(df: Any, target: str) -> np.ndarray:
    col, positive = TARGETS[target]
    return (df[col].astype(str) == positive).to_numpy().astype(int)


def label_relationships(df: Any) -> dict[str, Any]:
    """Empirical relationships between the four labels (documented + used to justify the consistency constraint)."""
    y = {t: target_vector(df, t) for t in TARGETS}
    vessels = np.stack([y["LAD"], y["LCX"], y["RCA"]], axis=1)
    any_vessel = vessels.max(axis=1)
    cad = y["CAD"]
    n = len(df)
    corr = np.corrcoef(vessels.T)
    return {
        "n": int(n),
        "prevalence": {t: round(float(v.mean()), 4) for t, v in y.items()},
        "vessel_count_distribution": {
            str(k): int((vessels.sum(axis=1) == k).sum()) for k in range(4)
        },
        "cad_equals_any_vessel": int((cad == any_vessel).sum()),
        "cad_without_stenotic_vessel": int(((cad == 1) & (any_vessel == 0)).sum()),
        "stenotic_vessel_without_cad": int(((cad == 0) & (any_vessel == 1)).sum()),
        "vessel_correlation": {
            "LAD-LCX": round(float(corr[0, 1]), 3),
            "LAD-RCA": round(float(corr[0, 2]), 3),
            "LCX-RCA": round(float(corr[1, 2]), 3),
        },
        "note": (
            "The overall CAD label (`Cath`) equals 'any target vessel stenotic' in all but "
            f"{int(((cad == 0) & (any_vessel == 1)).sum())} row(s). Vessel labels therefore nearly "
            "determine the CAD label and MUST be excluded from CAD inputs."
        ),
    }


# ---------------------------------------------------------------------------
# Reproducible import from the official UCI download
# ---------------------------------------------------------------------------


def import_dataset(zip_path: Path | None = None, out: Path | None = None) -> dict[str, str]:
    """xlsx (UCI download) -> verbatim CSV. Requires pandas + openpyxl (training-time deps)."""
    import pandas as pd

    if zip_path:
        raw = Path(zip_path).read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_DATASET["download"], timeout=60) as r:  # noqa: S310
            raw = r.read()
    if hashlib.sha256(raw).hexdigest() != SOURCE_ZIP_SHA256:
        raise DatasetError(
            "downloaded UCI archive does not match the pinned SHA-256; refusing to import a changed dataset"
        )
    z = zipfile.ZipFile(io.BytesIO(raw))
    name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
    df = pd.read_excel(io.BytesIO(z.read(name)), sheet_name=0)
    validate_dataset(df)
    out_path = Path(out) if out else DATASET_CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return {
        "source_zip_sha256": hashlib.sha256(raw).hexdigest(),
        "source_file": name,
        "csv": str(out_path),
        "csv_sha256": file_sha256(out_path),
        "rows": str(len(df)),
    }


if __name__ == "__main__":  # python -m app.cardiotwin.data --import [--zip path]
    if "--import" in sys.argv:
        zp = Path(sys.argv[sys.argv.index("--zip") + 1]) if "--zip" in sys.argv else None
        for k, v in import_dataset(zp).items():
            print(f"{k}: {v}")
    else:
        d = load_dataset()
        print(f"OK: {len(d)} rows x {d.shape[1]} columns; sha256={file_sha256(DATASET_CSV)}")
