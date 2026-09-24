"""Model registry — every model has a purpose, a task, an evaluation metric and a measured value.

Adapter contract (what the application depends on — so a model can be swapped
without changing the application):

    version_info() -> {model_id, version, artifact_sha256, integrity_verified}
    predict(features) -> calibrated probability (classification / survival tasks)
    card()          -> purpose, metric definitions, measured metrics, limitations

A model is promoted only through the Research Lab: it must beat the deployed
model on the SAME held-out synthetic test patients (paired bootstrap) before its
artifact is registered. Families deliberately NOT added (TFT, GRU/LSTM,
gradient boosting) are listed with the reason — no model is added for show.
"""
from __future__ import annotations

from typing import Any

from app.oncotwin.ml.horizon import load_horizon_model
from app.oncotwin.ml.model import load_model
from app.oncotwin.observability import METRICS
from app.oncotwin.research.benchmark import load_results


def _gate_pass_rate() -> dict[str, Any]:
    tot = {"pass": 0.0, "fail": 0.0}
    for c in METRICS.snapshot()["counters"]:
        if c["name"] == "oncotwin_safety_gate_total" and c["labels"].get("source") == "llm":
            tot[c["labels"]["outcome"]] += c["value"]
    n = tot["pass"] + tot["fail"]
    return {"llm_gate_checks": int(n), "pass_rate": None if not n else round(tot["pass"] / n, 3)}


def registry() -> dict[str, Any]:
    lr = load_model()
    hz = load_horizon_model()
    bench = load_results() or {}
    cp = (bench.get("change_point_detection") or {}).get("bocpd")
    neut = bench.get("neutrophil_twin")
    lat = bench.get("latent_state_recovery")
    anom = next((r for r in bench.get("comparators", []) if "anomaly" in r["config"]["name"].lower()), None)
    m = lr.artifact["metrics"]
    ew = m["event_level"]["early_warning_or_higher"]
    models = [
        {"id": lr.model_id, "version": lr.version, "task": "classification (patient-day)",
         "status": "deployed — primary tiering",
         "purpose": "P(OT-ACUTE-7): unplanned acute care for an OP-35 condition within 7 days",
         "metrics": {"test_auroc": m["day_level"]["auroc"], "test_auprc": m["day_level"]["auprc"],
                     "brier": m["day_level"]["brier"], "events_caught_at_EW": f"{ew['events_detected']}/{ew['events']}",
                     "median_lead_days": ew["median_lead_time_days"]},
         "metric_definition": "AUROC / AUPRC / Brier on held-out synthetic test patients; event-level lead time",
         "artifact": lr.version_info()},
        {"id": "oncotwin-horizon-survival", "version": hz.artifact["version"] if hz else None,
         "task": "discrete-time survival", "status": "deployed — multi-horizon panel" if hz else "not trained",
         "purpose": "consistent 24 h / 72 h / 7-day cumulative risk (monotone by construction)",
         "metrics": ({k: {"auroc": v["auroc"], "ci95": v["auroc_95ci_patient_bootstrap"], "positives": v["n_positive"]}
                      for k, v in hz.artifact["metrics"].items() if isinstance(v, dict)} if hz else None),
         "metric_definition": "per-horizon AUROC (patient-bootstrap 95 % CI) on held-out synthetic test patients",
         "artifact": hz.version_info() if hz else None},
        {"id": "bocpd-changepoint", "version": "1.1.0", "task": "change-point detection",
         "status": "deployed — trajectory intelligence",
         "purpose": "detect regime shifts in the personal-baseline deviation vector", "metrics": cp,
         "metric_definition": "sensitivity vs the generator's latent onsets, detection delay, false detections / 100 patient-days"},
        {"id": "mahalanobis-anomaly", "version": "1.0.0", "task": "anomaly detection", "status": "deployed — model feature",
         "purpose": "multi-signal deviation magnitude under the patient's own correlation structure",
         "metrics": None if anom is None else {"test_auroc_as_score": anom["metrics"]["auroc"]},
         "metric_definition": "AUROC of the score alone for OT-ACUTE-7"},
        {"id": "friberg-neutrophil-twin", "version": "1.0.0", "task": "mechanistic state estimation",
         "status": "deployed — twin core",
         "purpose": "patient-fitted neutrophil kinetics (ANC estimate, nadir projection, what-if)",
         "metrics": None if not neut else {"mae_log_anc": neut["mae_log_anc"], "coverage": neut.get("coverage_of_80pct_intervals")},
         "metric_definition": "next-ANC prediction error vs carry-forward and population prior; interval coverage"},
        {"id": "latent-nnls-inversion", "version": "1.0.0", "task": "state estimation", "status": "deployed — twin core",
         "purpose": "infection / dehydration / fatigue loads from all signals",
         "metrics": None if not lat else lat["pearson_r_estimated_vs_true"],
         "metric_definition": "Pearson r of estimated vs generator latent loads (synthetic ground truth)"},
        {"id": "explanation-agent-llm", "version": "prompt SHA-256", "task": "explanation synthesis (optional LLM)",
         "status": "opt-in (ONCOTWIN_LLM_EXPLANATIONS=1)",
         "purpose": "clinician-readable synthesis of computed evidence; the deterministic narrative is always available",
         "metrics": _gate_pass_rate(), "metric_definition": "share of LLM outputs passing every safety gate (live)"},
    ]
    not_added = [
        {"family": "Temporal Fusion Transformer / Transformer",
         "reason": "56-day daily series and ~21k training patient-days do not justify it, and the linear model's exact "
                   "contributions are needed for explanation. Register via the adapter only if it beats the deployed "
                   "model on the Research Lab benchmark."},
        {"family": "GRU / LSTM", "reason": "no demonstrated gain; recurrent state would duplicate the explicit "
                                           "personal-baseline, slope and persistence features."},
        {"family": "Gradient-boosted trees (XGBoost)", "reason": "no dependency added for an unproven gain; candidates "
                                                                 "must first clear the paired-bootstrap ΔAUROC test."},
        {"family": "Isolation Forest / autoencoder anomaly", "reason": "the Mahalanobis score already serves this purpose "
                                                                       "in closed form, tied to the personal baseline."},
    ]
    return {"models": models, "not_added_by_design": not_added,
            "adapter_contract": ["version_info()", "predict(features) → calibrated probability", "card()"],
            "promotion_policy": ("train → validate (Research Lab, same test patients) → paired ΔAUROC 95 % CI > 0 → "
                                 "register artifact (SHA-256) → deploy → monitor (prediction log + drift)")}
