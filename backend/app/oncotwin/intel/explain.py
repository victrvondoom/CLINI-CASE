"""WHY NOW? and WHAT CHANGED? — assembled only from computed evidence.

WHY NOW answers, for the current as-of day, why the twin's assessment is what
it is *today* rather than yesterday or next week:

  trigger             tier transition / thresholds crossed / rules fired /
                      change point confirmed — whichever happened
  vs baseline         each adversely deviating signal: arrow, % change (ratio-
                      scaled signals) or absolute change (°C, SpO₂ points,
                      symptom points), SD vs the personal baseline, persistence
  persistence         days in the current episode, longest single-signal run
  treatment context   cycle / day of cycle / phase / nadir window, last dose,
                      recent interventions, G-CSF this cycle
  model               outcome, horizon, model id + version + artifact hash
  confidence          probability + 80 % interval + confidence label
  data quality        completeness, freshness, active flags, uncertainty notes

No number here is typed in by hand — every value is read from the twin's
computations, so the same code yields "HRV ↓ 18 %" for one patient and
"HRV ↓ 4 %" for another.
"""
from __future__ import annotations

from typing import Any

from app.oncotwin.engine.warning import RANK
from app.oncotwin.intel.state import compare
from app.oncotwin.signals import SIGNALS


def _magnitude(row: dict[str, Any]) -> str:
    k = row["signal"]
    arrow = row["direction"] or ""
    if row["pct_vs_baseline"] is not None:
        return f"{arrow} {abs(row['pct_vs_baseline']):.0f}%"
    unit = {"temperature": " °C", "spo2": " pts", "symptom_score": " pts"}.get(k, f" {SIGNALS[k].unit_display}")
    return f"{arrow} {abs(row['delta'] or 0):.{max(1, SIGNALS[k].decimals)}f}{unit}"


def why_now(*, as_of_day: int, prediction: dict[str, Any], history: list[dict[str, Any]], correlation: dict[str, Any],
            changepoints: dict[str, Any], trajectory: dict[str, Any], state: dict[str, Any],
            uncertainty: dict[str, Any], readiness: dict[str, Any],
            horizons: dict[str, Any] | None = None) -> dict[str, Any]:
    t = as_of_day
    prev = next((h for h in reversed(history) if h["day"] < t), None)
    trig = []
    if prediction["tier"] != prediction["previous_tier"]:
        trig.append(f"tier moved {prediction['previous_tier']} → {prediction['tier']}")
    for name, thr in prediction["thresholds"].items():
        if isinstance(thr, float) and prediction["risk"] >= thr and (prev is None or prev["risk"] < thr):
            trig.append(f"7-day risk crossed the {name.replace('_', ' ')} threshold ({thr:.1%}) today")
    trig += [f"rule fired: {r['text']}" for r in prediction["rules_fired"]]
    trig += [f"change point confirmed today (regime began Day {p['day']})"
             for p in changepoints.get("change_points", []) if p["detected_on_day"] == t]
    if not trig:
        trig.append("no new trigger today — the assessment continues an existing state"
                    if RANK.get(prediction["tier"], 0) >= RANK["WATCH"] else "no trigger — within the patient's usual range")

    rows = sorted((r for r in correlation["signals"] if r["deviating_adversely"]), key=lambda r: -(r["z_adverse_3d"] or 0))
    vs_baseline = [{
        "signal": r["signal"], "label": r["label"], "change": _magnitude(r), "z_sd": r["z_adverse_3d"],
        "recent_3d_mean": r["recent_3d_mean"], "baseline_median": r["baseline_median"], "unit": r["unit"],
        "persistence_days": r["persistence_days"], "onset_day": r["onset_day"],
        "model_contribution_logit": r["model_contribution_logit"],
    } for r in rows]

    txd = state["dimensions"]["treatment"]
    tx = txd["fields"]
    iv = state["dimensions"]["intervention"]["fields"].get("recent", [])
    recent_tx = bool(tx.get("last_dose_day")) and t - tx["last_dose_day"] <= 14
    treatment = {
        "cycle": tx.get("cycle"), "day_of_cycle": tx.get("day_of_cycle"), "last_dose_day": tx.get("last_dose_day"),
        "phase": txd["status"], "in_nadir_window": tx.get("in_nadir_window"), "gcsf_this_cycle": tx.get("gcsf_this_cycle"),
        "recent_treatment_event": recent_tx,
        "recent_interventions": [f"{e['display']} (Day {e['day']})" for e in iv],
        "text": (("Recent treatment event detected — " if recent_tx else "")
                 + (f"cycle {tx['cycle']}, day {tx['day_of_cycle']} of cycle (last dose Day {tx['last_dose_day']})"
                    if tx.get("cycle") else "not yet on treatment")
                 + ("; expected neutrophil nadir window" if tx.get("in_nadir_window") else "")),
    }
    cp = changepoints.get("latest_unexplained_adverse")
    persistence = {
        "episode_days": trajectory.get("days_at_watch_or_higher", 0), "episode_basis": correlation["window"]["basis"],
        "longest_signal_run_days": max((r["persistence_days"] for r in rows), default=0),
        "change_point": None if cp is None else {"day": cp["day"], "statement": cp["statement"]},
        "trajectory_dynamics": trajectory["dynamics"],
    }
    q = state["dimensions"]["data_quality"]
    model = {"outcome_id": prediction["outcome_id"], "horizon_days": prediction["horizon_days"],
             **{k: prediction["model"][k] for k in ("model_id", "version", "artifact_sha256", "integrity_verified")}}
    confidence = {"risk": prediction["risk"], "p10": prediction["risk_p10"], "p90": prediction["risk_p90"],
                  "label": prediction["confidence"]["label"], "score": prediction["confidence"]["score"],
                  "interval": prediction["interval"]}
    data_quality = {"status": q["status"], "completeness_7d": q["fields"]["completeness_7d"],
                    "freshness": q["fields"]["freshness"], "stale_signals": q["fields"]["stale_signals"],
                    "flags": [f["message"] for f in q["fields"]["active_flags"]][:4],
                    "uncertainty": uncertainty["statements"],
                    "readiness": {k: readiness[k] for k in ("score", "label", "limiting_factor")}}

    parts = [f"{prediction['tier']} on Day {t}: {'; '.join(x.rstrip('.') for x in trig)}."]  # rule texts end in "."
    if vs_baseline:
        parts.append("Compared with this patient's own baseline: "
                     + ", ".join(f"{v['label']} {v['change']} ({v['z_sd']:+.1f} SD)" for v in vs_baseline[:5]) + ".")
    parts.append(f"Temporal persistence: {persistence['episode_days']} day(s) at WATCH or higher "
                 f"(trajectory: {trajectory['dynamics']}).")
    parts.append(f"Treatment context: {treatment['text']}.")
    parts.append(f"Model {model['model_id']} v{model['version']}, horizon {model['horizon_days']} days: "
                 f"{confidence['risk']:.1%} (80% interval {confidence['p10']:.1%}–{confidence['p90']:.1%}), "
                 f"confidence {confidence['label']}.")
    parts.append(f"Data quality: {data_quality['status']} (7-day completeness {data_quality['completeness_7d']:.0%}).")
    return {
        "as_of_day": t, "tier": prediction["tier"], "triggers": trig, "compared_with_baseline": vs_baseline,
        "persistence": persistence, "treatment_context": treatment, "model": model, "confidence": confidence,
        "multi_horizon": horizons, "data_quality": data_quality, "text": " ".join(parts),
        "language_note": ("Signal changes are associations with the risk estimate; they are not presented as causes. "
                          "Clinical decision support only."),
    }


def what_changed(states: list[dict[str, Any]], day: int, compare_to: int | None = None) -> dict[str, Any]:
    """Previous twin state → current twin state (default: 3 days earlier) with the transition path."""
    ref = max(1, min(compare_to if compare_to is not None else day - 3, day))
    out = compare(states, ref, day)
    worse = [c for c in out["changed"] if c["direction"] == "worsening"]
    better = [c for c in out["changed"] if c["direction"] == "improving"]
    n = len(states[0]["dimensions"]) if states else 0
    out["headline"] = (
        (f"{len(out['changed'])} of {n} state dimensions changed between Day {ref} and Day {day}"
         + (f" — {len(worse)} worsening" if worse else "") + (f", {len(better)} improving" if better else "") + ".")
        if out["changed"] else f"No state dimension changed between Day {ref} and Day {day}.")
    return out
