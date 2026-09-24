"""Prediction log with delayed ground truth.

Every committed evaluation logs one row:
  prediction id · patient · twin day · created at · model id / version / artifact
  SHA-256 · feature-set version · training-dataset version · risk + 80 % interval
  · tier · horizon · input SHA-256 · ledger entry

Ground truth for OT-ACUTE-7 becomes observable later: a row is resolved to 1
when a qualifying Encounter starts within (day, day + 7] in the record the twin
can see, to 0 once the twin clock has passed day + 7 without one; otherwise it
stays "pending". Live metrics are computed on resolved rows only and report
their sample size — with a handful of demo patients they are illustrative, and
the payload says so.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.oncotwin.ml.logistic import auroc, brier
from app.oncotwin.mlops.versions import feature_version, training_dataset_version
from app.oncotwin.outcome import HORIZON_DAYS


def log_prediction(store, pid: str, comp, prov: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    p = comp.prediction
    row = {
        "prediction_id": f"otp_{uuid.uuid4().hex[:12]}", "patient_id": pid, "as_of_day": comp.as_of_day,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "model_id": p["model"]["model_id"], "model_version": p["model"]["version"],
        "artifact_sha256": p["model"]["artifact_sha256"], "feature_version": feature_version(),
        "dataset_version": training_dataset_version(), "risk": p["risk"], "risk_p10": p["risk_p10"],
        "risk_p90": p["risk_p90"], "tier": p["tier"], "horizon_days": HORIZON_DAYS,
        "input_sha256": prov["input_sha256"], "ledger_entry_id": entry["id"],
        "label": None, "label_status": "pending", "label_evidence": None,
    }
    store.predictions.append(row)
    return row


def resolve(store) -> int:
    """Attach ground truth to predictions whose outcome window is now observable. Returns rows resolved."""
    n = 0
    for row in store.predictions:
        if row["label_status"] != "pending":
            continue
        try:
            st = store.patient(row["patient_id"])
        except KeyError:
            continue
        d = row["as_of_day"]
        onset = next((e for e in st.record().events_until(st.live_day)
                      if e.kind == "encounter" and e.detail.get("qualifying") and d < e.day <= d + HORIZON_DAYS), None)
        if onset is not None:
            row.update(label=1, label_status="resolved", label_evidence={"encounter_id": onset.id, "day": onset.day})
            n += 1
        elif st.live_day >= d + HORIZON_DAYS:
            row.update(label=0, label_status="resolved", label_evidence={"observed_through_day": st.live_day})
            n += 1
    return n


def live_metrics(store) -> dict[str, Any]:
    resolve(store)
    rows = store.predictions
    done = [r for r in rows if r["label_status"] == "resolved"]
    y = np.array([r["label"] for r in done], dtype=float)
    p = np.array([r["risk"] for r in done], dtype=float)
    out: dict[str, Any] = {"n_predictions": len(rows), "n_resolved": len(done),
                           "n_pending": sum(1 for r in rows if r["label_status"] == "pending"),
                           "n_positive": int(y.sum()) if len(y) else 0}
    if len(done):
        out["brier"] = round(float(brier(y, p)), 4)
        out["mean_predicted"] = round(float(p.mean()), 4)
        out["observed_rate"] = round(float(y.mean()), 4)
        both = min(y.sum(), len(y) - y.sum())
        out["auroc"] = round(float(auroc(y, p)), 3) if both >= 3 else None
        by_tier: dict[str, dict[str, float]] = {}
        for r in done:
            t = by_tier.setdefault(r["tier"], {"n": 0, "events": 0})
            t["n"] += 1
            t["events"] += r["label"]
        out["by_tier"] = by_tier
    out["note"] = ("Ground truth resolves as the twin clock passes each prediction's 7-day window. Small samples from "
                   "a handful of synthetic demo patients are illustrative, not validation.")
    return out
