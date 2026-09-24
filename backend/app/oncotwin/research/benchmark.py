"""Research-grade benchmark → committed, reproducible results artifact.

    python -m app.oncotwin.research.benchmark            # ≈ 3–4 min on the cached 1 000-patient cohort

Studies (all on the untouched synthetic TEST patients of the deployed model's split):

  1. modality benchmark   static context · clinical-only (EHR) · wearable-only ·
                          remote monitoring (wearables + home + PRO) · multimodal Digital Twin
  2. ablation             multimodal minus one group at a time, and minus personalisation
  3. personalisation      personal vs population baseline, same features
  4. comparators          population vital-sign thresholds; Mahalanobis anomaly score alone
  5. horizons             per-horizon logistic models (1 / 3 / 7 days) next to the
                          discrete-time survival model
  6. lead time            lead-time distributions, incl. the DEPLOYED system (rules + hysteresis)
  7. change points        BOCPD vs per-signal CUSUM against the generator's latent onsets
  8. neutrophil twin      next-ANC prediction vs carry-forward and population prior
  9. latent state         correlation of estimated latent loads with the generator's truth

Every arm is compared with the multimodal reference by a PAIRED patient bootstrap
(ΔAUROC with 95 % CI) — "does fusion actually help?" is answered with an interval,
not an adjective. All numbers are SYNTHETIC-cohort results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin import ONCOTWIN_VERSION
from app.oncotwin.engine.baseline import adverse_z, cusum
from app.oncotwin.engine.features import signal_matrix
from app.oncotwin.engine.neutrophil import POPULATION_ANC, NeutrophilTwin
from app.oncotwin.engine.state import estimate_latent
from app.oncotwin.engine.warning import RANK
from app.oncotwin.intel.changepoint import detect
from app.oncotwin.ml.model import load_model
from app.oncotwin.ml.train import tier_sequence
from app.oncotwin.research.dataset import load_cohort
from app.oncotwin.research.lab import ALL_GROUPS, ExperimentConfig, paired_delta, population_base, run_experiment
from app.oncotwin.simulator import physiology as P

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "benchmark_v1.json"
INF_ONSET, DEH_ONSET = 0.25, 0.30


def _without(*groups: str) -> tuple[str, ...]:
    return tuple(g for g in ALL_GROUPS if g not in groups)


MODALITY = [
    ExperimentConfig("Static context only", ("treatment", "demographics"),
                     notes="regimen myelotoxicity, cycle timing, on-treatment flag, age — no monitoring data"),
    ExperimentConfig("Clinical-only (EHR)", ("labs_twin", "treatment", "adherence", "demographics"),
                     notes="labs + neutrophil twin, treatment context, adherence — no wearables / home devices / PRO"),
    ExperimentConfig("Wearable-only", ("wearables", "multi_signal"),
                     notes="personal-baseline deviations of wearable signals and their composites only"),
    ExperimentConfig("Remote monitoring (wearables + home + PRO)", ("wearables", "home", "symptoms", "multi_signal"),
                     notes="all dynamic signals, no EHR context"),
    ExperimentConfig("Multimodal Digital Twin", ALL_GROUPS, notes="the deployed feature set"),
]
ABLATION = [
    ExperimentConfig("− wearables", _without("wearables")),
    ExperimentConfig("− home devices", _without("home")),
    ExperimentConfig("− symptoms (PRO)", _without("symptoms")),
    ExperimentConfig("− labs + neutrophil twin", _without("labs_twin")),
    ExperimentConfig("− treatment context", _without("treatment")),
    ExperimentConfig("− adherence", _without("adherence")),
    ExperimentConfig("− multi-signal composites", _without("multi_signal")),
    ExperimentConfig("− personalisation (population baseline)", ALL_GROUPS, baseline="population"),
]
COMPARATORS = [
    ExperimentConfig("Population vital-sign thresholds", (), model="vital_threshold_rule"),
    ExperimentConfig("Mahalanobis anomaly score alone", ALL_GROUPS, model="anomaly_score"),
]
HORIZONS = [ExperimentConfig(f"Multimodal, {h}-day horizon", ALL_GROUPS, horizon=h) for h in (1, 3, 7)]


def _arm_row(arm, ref) -> dict[str, Any]:
    keep = ("auroc", "auroc_95ci", "auprc", "brier", "ece", "precision", "recall", "f1", "threshold", "threshold_basis",
            "events", "events_detected", "event_sensitivity", "median_lead_time_days", "lead_times_days",
            "false_alert_onsets_per_100_patient_days", "n_features", "n_patient_days", "n_positive", "l2",
            "top_coefficients", "calibration")
    return {"config": arm.config.describe(), "metrics": {k: arm.metrics.get(k) for k in keep},
            "paired_vs_multimodal": None if ref is None or arm is ref else paired_delta(arm, ref),
            "seconds": round(arm.seconds, 1)}


def deployed_system_leads(cohort) -> dict[str, Any]:
    """The DEPLOYED alerting system (probability tiers ∨ clinical rules, then hysteresis): ≥ EARLY WARNING."""
    model = load_model()
    leads, n_events, detected = [], 0, 0
    for p in cohort.part("test"):
        d = p.data
        ranks = [RANK.get(t, 0) for t in tier_sequence(d, model.predict(d.F), model.thresholds)]
        first = d.series.first_dose_day
        for o in d.onsets:
            if first is None or o <= first:
                continue
            n_events += 1
            hits = [t for t in range(max(0, o - 8), o - 1) if ranks[t] >= RANK["EARLY WARNING"] and not d.acute[t]]
            if hits:
                detected += 1
                leads.append(o - (min(hits) + 1))
    return {"events": n_events, "events_detected": detected,
            "median_lead_time_days": float(np.median(leads)) if leads else None,
            "lead_times_days": sorted(int(x) for x in leads), "source": "deployed OT-ACUTE-7 model + rules + hysteresis"}


def _truth_onsets(truth, first_dose: int | None, acute: np.ndarray) -> list[int]:
    inf, deh = np.array(truth.infection), np.array(truth.dehydration)
    hot = (inf >= INF_ONSET) | (deh >= DEH_ONSET)
    return [i + 1 for i in range(3, len(hot))
            if hot[i] and not hot[i - 3:i].any() and first_dose is not None and i + 1 > first_dose and not acute[i]]


def changepoint_study(cohort) -> dict[str, Any]:
    stats = {"bocpd": {"hits": 0, "delays": [], "false": 0}, "cusum": {"hits": 0, "delays": [], "false": 0}}
    n_onsets, pdays, explained = 0, 0, 0
    for p in cohort.part("test"):
        s, b = p.data.series, p.baseline
        first = s.first_dose_day
        onsets = _truth_onsets(p.truth, first, p.data.acute)
        n_onsets += len(onsets)
        pdays += sum(1 for d in range(1, s.n + 1) if first is not None and d > first and not p.data.acute[d - 1])
        cps = detect(s, b)["change_points"]
        explained += sum(1 for c in cps if c["significance"] == "significant" and c["expected_treatment_effect"])
        boc = [(c["day"], c["detected_on_day"]) for c in cps
               if c["significance"] == "significant" and c["kind"] != "recovery shift" and not c["expected_treatment_effect"]]
        alarm = (cusum(adverse_z(signal_matrix(s), b))[0] >= 4.0).any(axis=1)
        cus = [(d, d) for d in range(2, s.n + 1) if alarm[d - 1] and not alarm[d - 2]]
        for name, dets in (("bocpd", boc), ("cusum", cus)):
            used = set()
            for o in onsets:
                cand = [(c, dd) for c, dd in dets if o - 3 <= c <= o + 3 and dd <= o + 5]
                if cand:
                    best = min(cand, key=lambda x: x[1])
                    stats[name]["hits"] += 1
                    stats[name]["delays"].append(best[1] - o)
                    used.add(best)
            stats[name]["false"] += sum(1 for c, dd in dets if (c, dd) not in used and first is not None and c > first
                                        and not any(abs(c - o) <= 5 for o in onsets))
    out: dict[str, Any] = {
        "truth_definition": (f"deterioration onset = first day the generator's latent infection ≥ {INF_ONSET} or "
                             f"dehydration ≥ {DEH_ONSET} after ≥ 3 days below, on treatment, outside acute care"),
        "match_rule": "detected regime start within ±3 days of the onset and confirmed ≤ 5 days after it",
        "n_truth_onsets": n_onsets, "on_treatment_patient_days": pdays,
        "treatment_explained_change_points": explained}
    for name, st in stats.items():
        out[name] = {"detected": st["hits"], "sensitivity": round(st["hits"] / max(1, n_onsets), 3),
                     "median_detection_delay_days": float(np.median(st["delays"])) if st["delays"] else None,
                     "delay_iqr": ([float(np.percentile(st["delays"], 25)), float(np.percentile(st["delays"], 75))]
                                   if st["delays"] else None),
                     "false_detections_per_100_patient_days": round(100.0 * st["false"] / max(1, pdays), 2)}
    out["bocpd"]["method"] = "BOCPD — significant, adverse/mixed, not explained by a chemotherapy dose"
    out["cusum"]["method"] = "per-signal one-sided CUSUM ≥ 4 on any signal (the pre-existing drift alarm)"
    return out


def neutrophil_study(cohort) -> dict[str, Any]:
    err: dict[str, list[float]] = {"twin": [], "carry_forward": [], "population_prior": []}
    cover = cover_pred = n = 0
    for p in cohort.part("test"):
        s = p.data.series
        first = s.first_dose_day
        if first is None:
            continue
        labs = [(d, v) for d, v, _ in s.labs.get("anc", [])]
        twin = NeutrophilTwin(s)
        for i, (d, v) in enumerate(labs):
            if d <= first or i == 0:
                continue
            fit = twin.fit(d - 1)
            est = fit.estimate(d)
            pred = fit.predictive(d)
            lv = np.log(max(v, 1e-3))
            err["twin"].append(abs(np.log(est["mean"]) - lv))
            err["carry_forward"].append(abs(np.log(max(labs[i - 1][1], 1e-3)) - lv))
            err["population_prior"].append(abs(np.log(POPULATION_ANC) - lv))
            cover += int(est["p10"] <= v <= est["p90"])
            cover_pred += int(pred["p_lo"] <= v <= pred["p_hi"])
            n += 1
    return {"task": "predict each on-treatment ANC result from the labs strictly before it plus the dose history",
            "n_predictions": n,
            "mae_log_anc": {k: round(float(np.mean(v)), 4) for k, v in err.items()},
            "median_fold_error": {k: round(float(np.exp(np.median(v))), 3) for k, v in err.items()},
            "coverage_of_80pct_intervals": {
                "latent_anc_interval": round(cover / max(1, n), 3),
                "predictive_interval_incl_lab_noise": round(cover_pred / max(1, n), 3)},
            "interpretation": ("The twin's displayed interval describes the TRUE ANC (drug-sensitivity uncertainty only); "
                               "a measured lab also carries assay noise, so lab-vs-twin comparisons use the predictive "
                               "interval.")}


def latent_study(cohort) -> dict[str, Any]:
    est: dict[str, list[float]] = {k: [] for k in P.LATENT}
    tru: dict[str, list[float]] = {k: [] for k in P.LATENT}
    for p in cohort.part("test"):
        s = p.data.series
        first = s.first_dose_day or s.n + 1
        lat = estimate_latent(s, p.baseline)["series"]
        truth = {"infection": p.truth.infection, "dehydration": p.truth.dehydration, "fatigue": p.truth.fatigue}
        for t in range(first - 1, s.n):
            for i, k in enumerate(P.LATENT):
                est[k].append(float(lat[t, i]))
                tru[k].append(float(truth[k][t]))
    return {"pearson_r_estimated_vs_true": {k: round(float(np.corrcoef(est[k], tru[k])[0, 1]), 3) for k in P.LATENT},
            "n_patient_days": len(est["infection"]),
            "note": "Identical-twin experiment: the generator shares the observation-model structure with the twin."}


def run_benchmark(n: int = 1000, *, write: bool = True, progress=print) -> dict[str, Any]:
    t0 = time.time()
    cohort = load_cohort(n)
    pb = population_base(cohort)

    def go(cfg):
        progress(f"  · {cfg.name}")
        return run_experiment(cohort, cfg, pop_base=pb)

    progress("modality benchmark")
    mod = [go(c) for c in MODALITY]
    ref = mod[-1]
    progress("ablation")
    abl = [go(c) for c in ABLATION]
    progress("comparators")
    cmp_ = [go(c) for c in COMPARATORS]
    progress("horizons")
    hor = [go(c) for c in HORIZONS]
    progress("lead time / change points / neutrophil twin / latent state")
    deployed = deployed_system_leads(cohort)
    cps = changepoint_study(cohort)
    neut = neutrophil_study(cohort)
    lat = latent_study(cohort)

    pers = next(a for a in abl if a.config.baseline == "population")
    hpath = Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "horizon_survival_v1.json"
    surv = json.loads(hpath.read_text(encoding="utf-8"))["metrics"] if hpath.exists() else None

    def hist(leads):
        return [sum(1 for x in leads if x == k) for k in range(0, 8)]

    results: dict[str, Any] = {
        "title": "OncoTwin research benchmark",
        "data_notice": "SYNTHETIC cohort — identical-twin experiment; demonstrates the method, not clinical performance.",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "oncotwin_version": ONCOTWIN_VERSION,
        "dataset": cohort.meta(),
        "deployed_model": load_model().version_info(),
        "reference_arm": "Multimodal Digital Twin",
        "modality_benchmark": [_arm_row(a, ref) for a in mod],
        "ablation": [_arm_row(a, ref) for a in abl],
        "personalization": {"question": "Do patient-specific baselines improve prediction over a pooled population 'normal'?",
                            "personal": _arm_row(ref, None), "population": _arm_row(pers, ref)},
        "comparators": [_arm_row(a, None) for a in cmp_],
        "horizons": {"per_horizon_logistic": [_arm_row(a, None) for a in hor], "survival_model_test_metrics": surv},
        "lead_time": {
            "definition": "days from the first alert (≥ EARLY WARNING) in the 7 days before a qualifying onset to that onset",
            "deployed_system": {**deployed, "histogram_0_to_7_days": hist(deployed["lead_times_days"])},
            "arms": [{"name": a.config.name, "median_lead_time_days": a.metrics.get("median_lead_time_days"),
                      "events_detected": a.metrics.get("events_detected"), "events": a.metrics.get("events"),
                      "histogram_0_to_7_days": hist(a.metrics.get("lead_times_days") or []),
                      "false_alert_onsets_per_100_patient_days": a.metrics.get("false_alert_onsets_per_100_patient_days")}
                     for a in (ref, pers, *mod[:4], *cmp_)]},
        "change_point_detection": cps,
        "neutrophil_twin": neut,
        "latent_state_recovery": lat,
        "event_metric_note": ("Arm-level event metrics use each arm's validation-derived probability threshold (PPV ≥ 25 %) "
                              "without clinical rules or hysteresis so arms are comparable; the deployed-system row uses "
                              "the full tiering."),
        "runtime_seconds": round(time.time() - t0, 1),
    }
    body = json.dumps({k: v for k, v in results.items() if k not in ("generated_at", "runtime_seconds")},
                      sort_keys=True, default=str).encode()
    results["sha256"] = hashlib.sha256(body).hexdigest()
    if write:
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    return results


def load_results() -> dict[str, Any] | None:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = run_benchmark(a.n, write=not a.dry_run)
    for sec in ("modality_benchmark", "ablation"):
        print(f"\n{sec}")
        for row in r[sec]:
            m, d = row["metrics"], row["paired_vs_multimodal"]
            print(f"  {row['config']['name']:<44} AUROC {m['auroc']} {m['auroc_95ci']}  lead {m['median_lead_time_days']}  "
                  f"FA/100 {m['false_alert_onsets_per_100_patient_days']}  Δ {d and (d['delta_auroc'], d['ci95'])}")
    print("\ncomparators", [(row["config"]["name"], row["metrics"]["auroc"], row["metrics"]["events_detected"],
                              row["metrics"]["median_lead_time_days"]) for row in r["comparators"]])
    print("horizons", [(row["config"]["name"], row["metrics"]["auroc"]) for row in r["horizons"]["per_horizon_logistic"]])
    print("change points", json.dumps({k: r["change_point_detection"][k] for k in ("bocpd", "cusum", "n_truth_onsets")}))
    print("neutrophil", json.dumps(r["neutrophil_twin"]))
    print("latent", json.dumps(r["latent_state_recovery"]))
    print("deployed", r["lead_time"]["deployed_system"]["median_lead_time_days"], r["lead_time"]["deployed_system"]["events_detected"],
          "runtime", r["runtime_seconds"])


if __name__ == "__main__":
    main()
