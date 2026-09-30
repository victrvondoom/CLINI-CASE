"""CardioTwin inference — numpy only (no sklearn / pickle at serve time).

The shipped model family is L2-regularised logistic regression, one model per
target (CAD, LAD, LCX, RCA), stored as a JSON artifact with a SHA-256, the same
convention as OncoTwin's registry. Because the model is linear in the
standardised features:

  * attribution is EXACT and additive:  calibrated_logit = baseline + Σ contribution_j
    (identical to interventional SHAP for a linear model with independent
    features; no sampling, no approximation),
  * counterfactual / sensitivity simulation is exact re-evaluation of the model.

Uncertainty = spread of a bootstrap ensemble; representativeness = shrinkage
Mahalanobis distance to the training cohort + per-feature range checks.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.cardiotwin import CARDIOTWIN_VERSION
from app.cardiotwin.features import (
    ENCODED_NAMES,
    RAW_TO_ENCODED_IDX,
    RecordValidationError,
    encode_record,
)
from app.cardiotwin.schema import (
    FEATURE_INDEX,
    FEATURES,
    SOURCE_DATASET,
    TARGET_ORDER,
    VESSEL_NAMES,
    VESSELS,
)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "cardiotwin_lr_v1.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation.json"
SCENARIOS_PATH = ARTIFACT_DIR / "scenarios.json"

#: Display bands for the 3D view / cards. These are VISUAL bands over an
#: estimated probability — they are not clinical thresholds.
BANDS = ((0.33, "low"), (0.66, "intermediate"), (1.01, "elevated"))

SAFETY_NOTICE = (
    "Decision support / educational use only. CardioTwin estimates probabilities from tabular clinical "
    "features; it is not a diagnosis, not a substitute for coronary angiography or other diagnostic "
    "imaging, and not a medical device. It does not locate, size or characterise any lesion."
)


class ModelArtifactError(RuntimeError):
    pass


def _sigmoid(z: np.ndarray | float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def canonical_sha256(artifact: dict[str, Any]) -> str:
    """Hash of everything except volatile bookkeeping (`training`, `sha256`)."""
    payload = json.dumps(
        {k: v for k, v in artifact.items() if k not in ("training", "sha256")}, sort_keys=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def band_for(p: float) -> str:
    for hi, name in BANDS:
        if p < hi:
            return name
    return "elevated"


class CardioModel:
    def __init__(self, artifact: dict[str, Any]):
        if tuple(artifact["encoded_names"]) != ENCODED_NAMES:
            raise ModelArtifactError(
                "CardioTwin artifact feature layout does not match the running encoder — retrain with "
                "`python -m app.cardiotwin.training`."
            )
        self.artifact = artifact
        self.impute = np.array(artifact["impute"], dtype=float)
        self.mean = np.array(artifact["mean"], dtype=float)
        self.std = np.array(artifact["std"], dtype=float)
        self.targets: dict[str, dict[str, Any]] = artifact["targets"]
        self.coef = {t: np.array(m["coef"]) for t, m in self.targets.items()}
        self.boot = {t: np.array(m["bootstrap"]) for t, m in self.targets.items()}  # (B, 1+P)
        ood = artifact["ood"]
        self.ood_mean = np.array(ood["mean"], dtype=float)
        self.ood_prec = np.array(ood["precision"], dtype=float)
        self.integrity_verified = canonical_sha256(artifact) == artifact.get("sha256")

    # ---- identity ---------------------------------------------------------
    @property
    def model_id(self) -> str:
        return self.artifact["model_id"]

    @property
    def version(self) -> str:
        return self.artifact["version"]

    @property
    def sha256(self) -> str:
        return self.artifact.get("sha256", "")

    def version_info(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "artifact_sha256": self.sha256,
            "integrity_verified": self.integrity_verified,
            "dataset_sha256": self.artifact["dataset"]["csv_sha256"],
            "trained_on": self.artifact["dataset"]["name"],
            "cardiotwin_version": CARDIOTWIN_VERSION,
        }

    # ---- core math --------------------------------------------------------
    def _z(self, vec: np.ndarray) -> np.ndarray:
        return (vec - self.mean) / self.std

    def _target_outputs(self, t: str, z: np.ndarray) -> dict[str, Any]:
        m = self.targets[t]
        w = self.coef[t]
        cal = m["calibration"]
        logit = float(m["intercept"] + z @ w)
        cal_logit = cal["a"] * logit + cal["b"]
        B = self.boot[t]
        b_logit = B[:, 0] + z @ B[:, 1:].T
        b_prob = _sigmoid(cal["a"] * b_logit + cal["b"])
        return {
            "raw_probability": float(_sigmoid(logit)),
            "probability": float(_sigmoid(cal_logit)),
            "cal_logit": cal_logit,
            "interval_low": float(np.percentile(b_prob, 10)),
            "interval_high": float(np.percentile(b_prob, 90)),
            "ensemble_sd": float(b_prob.std()),
            "threshold": float(m["threshold"]),
        }

    def _probabilities(self, vec: np.ndarray) -> dict[str, float]:
        """Fast path used by counterfactual / sensitivity sweeps (calibrated + consistent)."""
        z = self._z(vec)
        p = {t: self._target_outputs(t, z)["probability"] for t in TARGET_ORDER}
        p["CAD"] = max(p["CAD"], *(p[v] for v in VESSELS))
        return p

    # ---- representativeness (out-of-distribution) --------------------------
    def representativeness(self, vec: np.ndarray, raw: dict[str, Any]) -> dict[str, Any]:
        ood = self.artifact["ood"]
        zc = self._z(vec) - self._z(self.ood_mean)
        d2 = float(zc @ self.ood_prec @ zc)
        p95, p99 = ood["d2_p95"], ood["d2_p99"]
        out_of_range: list[dict[str, Any]] = []
        for name, rng in ood["feature_ranges"].items():
            v = raw.get(name)
            if v is None or (isinstance(v, str) and v == ""):
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            span = max(rng["max"] - rng["min"], 1e-9)
            lo, hi = rng["min"] - 0.10 * span, rng["max"] + 0.10 * span
            if f < lo or f > hi:
                out_of_range.append(
                    {
                        "feature": name,
                        "value": f,
                        "training_min": rng["min"],
                        "training_max": rng["max"],
                    }
                )
        if d2 > p99 or len(out_of_range) >= 2:
            status = "outside"
        elif d2 > p95 or out_of_range:
            status = "borderline"
        else:
            status = "representative"
        return {
            "status": status,
            "distance_squared": round(d2, 2),
            "percentile_of_training": round(
                float(np.interp(d2, ood["d2_quantile_grid"], ood["d2_quantile_levels"])), 1
            ),
            "borderline_above": round(p95, 2),
            "outside_above": round(p99, 2),
            "out_of_range_features": out_of_range,
        }

    # ---- attribution ------------------------------------------------------
    def contributions(self, t: str, vec: np.ndarray, rec: Any) -> dict[str, Any]:
        m = self.targets[t]
        a = m["calibration"]["a"]
        z = self._z(vec)
        enc = a * self.coef[t] * z
        baseline = a * m["intercept"] + m["calibration"]["b"]
        ranges = self.artifact["ood"]["feature_ranges"]
        rows: list[dict[str, Any]] = []
        for spec in FEATURES:
            idx = RAW_TO_ENCODED_IDX[spec.name]
            c = float(enc[idx].sum())
            raw_val = self._display_value(spec, vec, idx)
            imputed = spec.name in rec.imputed
            row: dict[str, Any] = {
                "feature": spec.name,
                "label": spec.label,
                "group": spec.group,
                "value": raw_val,
                "unit": spec.unit,
                "imputed": imputed,
                "contribution": round(c, 5),
                "direction": "raises" if c > 0 else "lowers" if c < 0 else "neutral",
            }
            if spec.kind == "numeric" and spec.name in ranges:
                r = ranges[spec.name]
                row["cohort_percentile"] = round(
                    float(np.interp(float(raw_val), r["quantile_values"], r["quantile_levels"])), 0
                )
                row["cohort_median"] = r["p50"]
                if spec.ref_lo is not None or spec.ref_hi is not None:
                    v = float(raw_val)
                    if spec.ref_lo is not None and v < spec.ref_lo:
                        row["reference_status"] = "below"
                    elif spec.ref_hi is not None and v > spec.ref_hi:
                        row["reference_status"] = "above"
                    else:
                        row["reference_status"] = "within"
                    row["reference_range"] = [spec.ref_lo, spec.ref_hi]
            rows.append(row)
        total = sum(abs(r["contribution"]) for r in rows) or 1.0
        for r in rows:
            r["share"] = round(abs(r["contribution"]) / total, 4)
        rows.sort(key=lambda r: abs(r["contribution"]), reverse=True)
        return {
            "baseline_logit": round(float(baseline), 5),
            "sum_check_logit": round(float(baseline + enc.sum()), 5),
            "features": rows,
        }

    @staticmethod
    def _display_value(spec: Any, vec: np.ndarray, idx: list[int]) -> float | str:
        if spec.kind == "categorical":
            hot = [k for k, i in enumerate(idx) if vec[i] >= 0.5]
            return spec.options[hot[0] + 1] if hot else spec.options[0]
        if spec.kind == "ordinal":
            return spec.options[int(round(float(vec[idx[0]])))]
        if spec.kind == "binary":
            return "Yes" if vec[idx[0]] >= 0.5 else "No"
        return round(float(vec[idx[0]]), 3)

    # ---- public API -------------------------------------------------------
    def predict(self, values: dict[str, Any], scenario_id: str | None = None) -> dict[str, Any]:
        rec = encode_record(values, self.impute)
        vec = np.array(rec.vector)
        z = self._z(vec)
        out = {t: self._target_outputs(t, z) for t in TARGET_ORDER}
        rep = self.representativeness(vec, values)

        # Logical constraint: overall CAD ⊇ any target-vessel stenosis (302/303 rows in the data),
        # so P(CAD) may not be lower than the largest vessel probability.
        vessel_max = max(out[v]["probability"] for v in VESSELS)
        cad_model_p = out["CAD"]["probability"]
        consistency_adjusted = vessel_max > cad_model_p
        if consistency_adjusted:
            out["CAD"]["probability"] = vessel_max
            out["CAD"]["interval_high"] = max(out["CAD"]["interval_high"], vessel_max)

        completeness = len(rec.provided) / len(FEATURES)
        warnings = self._warnings(rec, rep, completeness, consistency_adjusted)

        def target_block(t: str) -> dict[str, Any]:
            o = out[t]
            p = o["probability"]
            width = o["interval_high"] - o["interval_low"]
            conf = self._confidence(width, rep["status"], completeness)
            cal = self.targets[t]["calibration"]
            block: dict[str, Any] = {
                "target": t,
                "name": VESSEL_NAMES.get(t, "Overall coronary artery disease (angiographic)"),
                "probability": round(p, 4),
                "model_probability": round(o["raw_probability"], 4),
                "calibrated": cal["method"] != "none",
                "calibration_method": cal["method"],
                "interval_80": [round(o["interval_low"], 4), round(o["interval_high"], 4)],
                "ensemble_sd": round(o["ensemble_sd"], 4),
                "operating_point": round(o["threshold"], 4),
                "above_operating_point": bool(p >= o["threshold"]),
                "band": band_for(p),
                "confidence": conf,
                "held_out_auc": self.targets[t]["cv_summary"]["roc_auc"],
                "held_out_auc_ci95": self.targets[t]["cv_summary"]["roc_auc_ci95"],
            }
            if t == "CAD":
                block["consistency_adjusted"] = consistency_adjusted
                block["unadjusted_probability"] = round(cad_model_p, 4)
            return block

        cad = target_block("CAD")
        vessels = {v: target_block(v) for v in VESSELS}
        explanations = {t: self.contributions(t, vec, rec) for t in TARGET_ORDER}
        return {
            "cad": cad,
            "vessels": vessels,
            "explanations": explanations,
            "representativeness": rep,
            "feature_completeness": {
                "provided": len(rec.provided),
                "total": len(FEATURES),
                "fraction": round(completeness, 3),
                "imputed": rec.imputed,
            },
            "warnings": warnings,
            "visualization": self._visualization(cad, vessels),
            "provenance": {
                **self.version_info(),
                "prediction_timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
                "input_sha256": hashlib.sha256(
                    json.dumps(values, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "scenario_id": scenario_id,
                "leakage_audit": self.artifact["leakage_audit"]["status"],
                "calibration": {t: self.targets[t]["calibration"]["method"] for t in TARGET_ORDER},
                "evaluated": self.artifact["training"].get("trained_at")
                if "training" in self.artifact
                else None,
            },
            "safety_notice": SAFETY_NOTICE,
            "claims": {
                "is": "Estimated angiographic-CAD / vessel-level stenosis probability from clinical features.",
                "is_not": "Lesion localisation, plaque geometry, an imaging read-out, or a future-event / mortality risk.",
            },
        }

    @staticmethod
    def _confidence(width: float, rep_status: str, completeness: float) -> str:
        level = 2 if width <= 0.15 else 1 if width <= 0.30 else 0
        if rep_status == "borderline":
            level = min(level, 1)
        elif rep_status == "outside":
            level = 0
        if completeness < 0.25:
            level = 0
        elif completeness < 0.5:
            level = min(level, 1)
        return ("low", "moderate", "high")[level]

    @staticmethod
    def _warnings(
        rec: Any, rep: dict[str, Any], completeness: float, adjusted: bool
    ) -> list[dict[str, str]]:
        w: list[dict[str, str]] = []
        if rep["status"] == "outside":
            w.append(
                {
                    "code": "OUT_OF_DISTRIBUTION",
                    "severity": "high",
                    "message": (
                        "Prediction generated, but this profile lies outside the well-represented region "
                        "of the training cohort. Treat the estimate as unreliable."
                    ),
                }
            )
        elif rep["status"] == "borderline":
            w.append(
                {
                    "code": "BORDERLINE_REPRESENTATIVENESS",
                    "severity": "medium",
                    "message": "This profile is at the edge of the training cohort; uncertainty is likely understated.",
                }
            )
        if completeness < 0.5:
            w.append(
                {
                    "code": "LOW_FEATURE_COMPLETENESS",
                    "severity": "medium",
                    "message": (
                        f"Only {len(rec.provided)} of {len(FEATURES)} features were provided; the rest were "
                        "imputed with training medians."
                    ),
                }
            )
        if adjusted:
            w.append(
                {
                    "code": "CONSISTENCY_ADJUSTED",
                    "severity": "info",
                    "message": (
                        "The independent CAD model gave a lower value than the largest vessel estimate; overall "
                        "CAD was raised to that value because CAD includes any target-vessel stenosis."
                    ),
                }
            )
        return w

    @staticmethod
    def _visualization(cad: dict[str, Any], vessels: dict[str, Any]) -> dict[str, Any]:
        """Semantic visualisation state: one entry per vessel id, consumed by the 3D layer."""
        return {
            "encoding": {
                "probability": "vessel colour ramp (estimated probability, NOT a diagnosed stenosis)",
                "confidence": "outline strength",
                "uncertainty": "halo radius = 80% ensemble interval width",
            },
            "vessels": {
                v: {
                    "id": v,
                    "probability": b["probability"],
                    "band": b["band"],
                    "confidence": b["confidence"],
                    "halo": round(b["interval_80"][1] - b["interval_80"][0], 4),
                }
                for v, b in vessels.items()
            },
            "cad_probability": cad["probability"],
        }

    # ---- counterfactual / sensitivity -------------------------------------
    def counterfactual(
        self, values: dict[str, Any], perturbations: dict[str, Any]
    ) -> dict[str, Any]:
        unknown = sorted(set(perturbations) - set(FEATURE_INDEX))
        if unknown:
            raise RecordValidationError([f"unknown features in perturbations: {unknown}"])
        base = self.predict(values)
        changed = {**values, **perturbations}
        pert = self.predict(changed)
        rec_b = encode_record(values, self.impute)
        changes = []
        for name, new in perturbations.items():
            spec = FEATURE_INDEX[name]
            before = self._display_value(spec, np.array(rec_b.vector), RAW_TO_ENCODED_IDX[name])
            after = self._display_value(
                spec,
                np.array(encode_record({name: new}, self.impute).vector),
                RAW_TO_ENCODED_IDX[name],
            )
            changes.append(
                {
                    "feature": name,
                    "label": spec.label,
                    "before": before,
                    "after": after,
                    "unit": spec.unit,
                    "was_imputed": name in rec_b.imputed,
                }
            )
        rows = {}
        for t in TARGET_ORDER:
            b = base["cad"] if t == "CAD" else base["vessels"][t]
            p = pert["cad"] if t == "CAD" else pert["vessels"][t]
            delta = p["probability"] - b["probability"]
            rows[t] = {
                "before": b["probability"],
                "after": p["probability"],
                "delta": round(delta, 4),
                "within_model_uncertainty": abs(delta) < b["ensemble_sd"],
                "baseline_ensemble_sd": b["ensemble_sd"],
            }
        return {
            "changes": changes,
            "targets": rows,
            "baseline": base,
            "perturbed": pert,
            "label": "Model sensitivity simulation — how the model's output responds to changed inputs. "
            "Not a treatment recommendation and not a causal claim.",
        }

    def sensitivity(self, values: dict[str, Any], feature: str, points: int = 15) -> dict[str, Any]:
        if feature not in FEATURE_INDEX:
            raise RecordValidationError([f"unknown feature {feature!r}"])
        spec = FEATURE_INDEX[feature]
        rec = encode_record(values, self.impute)
        vec0 = np.array(rec.vector)
        idx = RAW_TO_ENCODED_IDX[feature]
        if spec.kind == "numeric":
            r = self.artifact["ood"]["feature_ranges"][feature]
            grid = np.linspace(r["p5"], r["p95"], points)
            labels = [round(float(g), 3) for g in grid]
            cells = [[float(g)] for g in grid]
        elif spec.kind == "ordinal":
            labels = list(spec.options)
            cells = [[float(k)] for k in range(len(spec.options))]
        elif spec.kind == "binary":
            labels, cells = ["No", "Yes"], [[0.0], [1.0]]
        else:
            labels = list(spec.options)
            cells = [
                [1.0 if k == j else 0.0 for k in range(1, len(spec.options))]
                for j in range(len(spec.options))
            ]
        curve = []
        for lab, cell in zip(labels, cells, strict=True):
            v = vec0.copy()
            for i, e in zip(idx, cell, strict=True):
                v[i] = e
            curve.append(
                {"value": lab, **{t: round(p, 4) for t, p in self._probabilities(v).items()}}
            )
        current = self._display_value(spec, vec0, idx)
        return {
            "feature": feature,
            "label": spec.label,
            "unit": spec.unit,
            "kind": spec.kind,
            "current_value": current,
            "was_imputed": feature in rec.imputed,
            "curve": curve,
            "note": "Model response curve holding every other input fixed — not an intervention effect.",
        }

    # ---- model card -------------------------------------------------------
    def card(self) -> dict[str, Any]:
        a = self.artifact
        return {
            **self.version_info(),
            "task": "binary classification x4 (CAD, LAD, LCX, RCA)",
            "purpose": (
                "Estimate the probability of angiographic CAD and of stenosis (>=50%) in each of the "
                "three major coronary vessels from demographic, clinical, ECG, laboratory and echo features."
            ),
            "model_family": a["model_family"],
            "calibration": {t: a["targets"][t]["calibration"] for t in TARGET_ORDER},
            "metrics": {t: a["targets"][t]["cv_summary"] for t in TARGET_ORDER},
            "metric_definition": a["evaluation_protocol"],
            "dataset": {**a["dataset"], "source": SOURCE_DATASET},
            "leakage_audit": a["leakage_audit"],
            "limitations": a["limitations"],
            "safety_notice": SAFETY_NOTICE,
        }


@lru_cache(maxsize=1)
def load_model(path: str | None = None) -> CardioModel:
    p = Path(path) if path else ARTIFACT_PATH
    if not p.exists():
        raise ModelArtifactError(
            f"CardioTwin model artifact missing at {p}. Train it with `python -m app.cardiotwin.training`."
        )
    try:
        artifact = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ModelArtifactError(f"CardioTwin model artifact is not valid JSON: {e}") from e
    model = CardioModel(artifact)
    if not model.integrity_verified:
        raise ModelArtifactError("CardioTwin model artifact failed its SHA-256 integrity check")
    return model


def load_json_artifact(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())  # type: ignore[no-any-return]
