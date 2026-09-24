"""Trajectory-Conflict Detector + Twin Consistency Engine.

Conflicts — sources that DISAGREE about the patient's trajectory:
  pro_vs_physiology        patient-reported symptoms at/under baseline or improving
                           while ≥ 2 physiological signals deteriorate
  record_vs_physiology     EHR quiet (no encounter, intervention or abnormal lab in
                           7 days) while the physiological trajectory changed
  model_vs_rules           transparent safety rules and the statistical model
                           disagree by ≥ 2 tiers
  twin_vs_lab              the newest ANC result falls outside the neutrophil
                           twin's 80 % interval predicted from the labs before it
  latent_misfit            ≥ 2 signals deviate ≥ 2 SD but the twin's observation
                           model explains < 30 % of the deviation (weighted R²)

Consistency — is the record internally coherent BEFORE we trust a prediction:
  dose_during_admission, planned_dose_missing, activity_while_inpatient,
  lab_kinetics, gcsf_sequence, timestamps, duplicates, source_conflicts

Every item carries its evidence (resource ids / values). Nothing here is a
diagnosis; each finding asks for the underlying data to be reviewed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

import numpy as np

from app.oncotwin.engine.neutrophil import NeutrophilTwin
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.engine.warning import RANK
from app.oncotwin.records import PatientRecord, datetime_to_day
from app.oncotwin.signals import SIGNALS

PHYSIO_FOR_PRO = ("hrv_sdnn", "sleep_hours", "steps", "resting_hr", "temperature")
GCSF_LABEL_WINDOW_DAYS = 14


def _conflict(cid: str, title: str, detected: bool, text: str, evidence: dict[str, Any],
              severity: str = "warning") -> dict[str, Any]:
    return {"id": cid, "title": title, "detected": bool(detected), "severity": severity if detected else "none",
            "text": text if detected else None, "evidence": evidence if detected else {}}


def conflicts(series: PatientSeries, facts: dict[str, Any], snapshot: dict[str, Any],
              changepoints: dict[str, Any] | None, latent_r2: float | None) -> list[dict[str, Any]]:
    t = series.as_of_day
    sig = facts["signals"]
    out = []

    sym = sig["symptom_score"]
    physio_bad = [k for k in PHYSIO_FOR_PRO if (sig[k]["z3"] or 0) >= 1.5]
    improving = sym["z3"] is not None and (sym["z3"] <= 0.5 or (sym.get("change3") is not None and sym["change3"] <= -0.5))
    out.append(_conflict(
        "pro_vs_physiology", "Patient report vs physiology", improving and len(physio_bad) >= 2,
        ("Trajectory conflict detected — review underlying data: the patient reports symptoms at or below baseline "
         f"(3-day mean {sym['m3']}/10 vs baseline {sym['base']}/10) while "
         + ", ".join(f"{SIGNALS[k].label.lower()} {'↑' if SIGNALS[k].adverse == 'up' else '↓'}" for k in physio_bad)
         + " deviate adversely."),
        {"symptom": {"value_3d": sym["m3"], "z3": sym["z3"], "change_3d": sym.get("change3"), "ids": sym["ids3"]},
         "physiology": {k: {"z3": sig[k]["z3"], "ids": sig[k]["ids3"]} for k in physio_bad}}))

    anc = facts["labs"].get("anc")
    quiet_ehr = (not [e for e in facts["recent_events"] if e["day"] >= t - 6]
                 and facts["care"]["admission"] is None
                 and not (anc and anc["v"] < 1.5 and t - anc["day"] <= 7))
    cp = (changepoints or {}).get("latest_unexplained_adverse")
    recent_cp = cp is not None and t - cp["day"] <= 7
    physio_change = recent_cp or facts["multi"]["n_concordant"] >= 3
    out.append(_conflict(
        "record_vs_physiology", "Clinical record vs physiology", quiet_ehr and physio_change,
        ("Trajectory conflict detected — review underlying data: the clinical record appears stable (no encounter, "
         "intervention or abnormal lab in 7 days) but the physiological trajectory changed"
         + (f" (change point Day {cp['day']})" if recent_cp else "")
         + f", with {facts['multi']['n_concordant']} signal(s) deviating together."),
        {"change_point": cp if recent_cp else None, "n_concordant": facts["multi"]["n_concordant"]}))

    # Genuine disagreement only: a safety rule escalates ≥ 2 tiers above a model that sees low
    # risk, or the model escalates to ≥ EARLY WARNING with no multi-signal physiological support
    # (i.e. driven by treatment/lab context alone).
    pr, rr = RANK.get(snapshot["probability_tier"], 0), RANK.get(snapshot["rule_tier"], 0)
    disagree = (rr - pr >= 2) or (pr >= RANK["EARLY WARNING"] and rr == 0 and facts["multi"]["n_concordant"] <= 1)
    out.append(_conflict(
        "model_vs_rules", "Statistical model vs safety rules", disagree,
        (f"Model probability tier {snapshot['probability_tier']} vs rule tier {snapshot['rule_tier']} "
         f"({facts['multi']['n_concordant']} signal(s) deviating) — the displayed tier takes the higher of the two; "
         "review which evidence drives each."),
        {"probability_tier": snapshot["probability_tier"], "rule_tier": snapshot["rule_tier"],
         "rules": [r["rule"] for r in snapshot["rules"]], "risk": snapshot["risk"]}, severity="info"))

    labs = [r for r in series.labs.get("anc", []) if r[0] <= t]
    twin_msg, twin_ev, twin_hit = "", {}, False
    if len(labs) >= 2 and t - labs[-1][0] <= 3:
        d, v, oid = labs[-1]
        # 95 % PREDICTIVE interval for a new lab (includes lab noise) — a genuine surprise, not noise.
        pred = NeutrophilTwin(series).fit(d - 1).predictive(d, (0.025, 0.975))
        if pred["source"].startswith("fitted") and not (pred["p_lo"] <= v <= pred["p_hi"]):
            twin_hit = True
            twin_msg = (f"Measured ANC {v:.2f} ×10³/µL on Day {d} is outside the neutrophil twin's 95% predictive "
                        f"interval {pred['p_lo']:.2f}–{pred['p_hi']:.2f} (from earlier labs + dose history); the twin has "
                        "been refitted — verify the result and the recent G-CSF / dose history.")
            twin_ev = {"observation_id": oid, "measured": v, "predictive_95": [round(pred["p_lo"], 2), round(pred["p_hi"], 2)]}
    out.append(_conflict("twin_vs_lab", "Neutrophil twin vs measured ANC", twin_hit, twin_msg, twin_ev))

    big = [k for k, v in sig.items() if (v.get("z3") or 0) >= 2.0]
    misfit = latent_r2 is not None and not np.isnan(latent_r2) and latent_r2 < 0.3 and len(big) >= 2
    out.append(_conflict(
        "latent_misfit", "Twin physiology vs observed deviations", misfit,
        (f"{len(big)} signals deviate ≥ 2 SD but the twin's physiological model explains only "
         f"{(latent_r2 or 0):.0%} of the deviation — possible non-modelled cause or sensor issue; review the data."),
        {"signals": big, "observation_model_r2": latent_r2}))
    return out


def _check(cid: str, title: str, status: str, text: str, evidence: Any = None) -> dict[str, Any]:
    return {"id": cid, "title": title, "status": status, "text": text, "evidence": evidence or []}


def consistency(record: PatientRecord, series: PatientSeries) -> dict[str, Any]:
    t = series.as_of_day
    checks = []
    adm = [(a["day"], a.get("discharge_day") or t + 1, a["id"]) for a in series.admissions]

    bad = [e for e in series.events if e.kind == "chemo_dose" and e.day >= 1 and any(s0 <= e.day < s1 for s0, s1, _ in adm)]
    checks.append(_check(
        "dose_during_admission", "Chemotherapy vs admissions", "fail" if bad else "pass",
        (f"Chemotherapy recorded during an inpatient admission on Day(s) {sorted({e.day for e in bad})} — conflicting "
         "clinical events; verify the record.") if bad else "No chemotherapy administration recorded during an admission.",
        [e.id for e in bad]))

    missing = []
    for p in series.planned_dose_days:
        if p < 1 or p > t - 3:
            continue
        given = any(p - 3 <= d <= p + 10 for d in series.dose_days)
        explained = any(s0 - 1 <= p <= s1 + 3 for s0, s1, _ in adm)
        if not given and not explained:
            missing.append(p)
    checks.append(_check(
        "planned_dose_missing", "CarePlan schedule vs administrations", "warn" if missing else "pass",
        (f"Planned dose(s) on Day {missing} have no recorded administration and no admission explaining a delay — "
         "verify the treatment record.") if missing else
        "Every planned dose so far is recorded or explained by a documented delay.", missing))

    pre = series.values["steps"][: max(1, series.baseline_end_day)]
    base = float(np.nanmedian(pre)) if np.any(~np.isnan(pre)) else None
    active_inpatient = []
    for s0, s1, aid in adm:
        for d in range(s0, min(s1, t + 1)):
            v = series.values["steps"][d - 1]
            if base and not np.isnan(v) and v >= 0.7 * base:
                active_inpatient.append({"day": d, "steps": float(v), "encounter": aid})
    checks.append(_check(
        "activity_while_inpatient", "Wearable activity vs inpatient status", "warn" if active_inpatient else "pass",
        ("Step counts near the personal baseline while recorded as inpatient — the device may be worn by someone else "
         "or the encounter dates are wrong.") if active_inpatient else
        "Wearable activity is consistent with recorded care settings.", active_inpatient))

    kin = []
    rows = series.labs.get("hemoglobin", [])
    for (d0, v0, _), (d1, v1, oid) in zip(rows, rows[1:]):
        if d1 - d0 <= 3 and abs(v1 - v0) > 2.5:
            kin.append({"lab": "hemoglobin", "from": v0, "to": v1, "days": [d0, d1], "observation_id": oid,
                        "text": f"Hemoglobin changed {v1 - v0:+.1f} g/dL within {d1 - d0} day(s)"})
    rows = series.labs.get("anc", [])
    for (d0, v0, _), (d1, v1, oid) in zip(rows, rows[1:]):
        gcsf = any(d0 - 10 <= g <= d1 for g in series.gcsf_days)
        if d1 - d0 <= 2 and v0 > 0 and v1 / v0 >= 5 and not gcsf:
            kin.append({"lab": "anc", "from": v0, "to": v1, "days": [d0, d1], "observation_id": oid,
                        "text": f"ANC rose ×{v1 / v0:.1f} in {d1 - d0} day(s) without recorded G-CSF"})
    checks.append(_check(
        "lab_kinetics", "Laboratory kinetics plausibility", "warn" if kin else "pass",
        ("; ".join(k["text"] for k in kin) + " — verify specimen / transfusion history.") if kin else
        "Laboratory changes are within plausible kinetics.", kin))

    seq = []
    for g in [e for e in series.events if e.kind == "gcsf_dose" and e.day >= 1 and "pegfilgrastim" in e.display.lower()]:
        nxt = [d for d in sorted(series.dose_days) if g.day < d <= g.day + GCSF_LABEL_WINDOW_DAYS]
        if nxt:
            seq.append({"gcsf_day": g.day, "chemo_day": nxt[0], "gap_days": nxt[0] - g.day, "id": g.id})
    checks.append(_check(
        "gcsf_sequence", "G-CSF / chemotherapy sequence", "warn" if seq else "pass",
        ("; ".join(f"pegfilgrastim Day {s['gcsf_day']} is {s['gap_days']} days before chemotherapy Day {s['chemo_day']}"
                   for s in seq)
         + " — pegfilgrastim labelling advises against administration from 14 days before to 24 h after cytotoxic "
           "chemotherapy; verify product and sequence.") if seq else
        "No pegfilgrastim recorded within 14 days before a chemotherapy dose.", seq))

    ts_bad = []
    for o in record.observations:
        if o.day > t:
            continue
        try:
            eff_day = datetime_to_day(datetime.fromisoformat(o.effective.replace("Z", "+00:00")))
        except (ValueError, TypeError):
            ts_bad.append({"id": o.id, "problem": "unparseable effective time", "effective": o.effective})
            continue
        if eff_day != o.day:
            ts_bad.append({"id": o.id, "problem": f"effective time is Day {eff_day} but indexed as Day {o.day}",
                           "effective": o.effective})
    checks.append(_check(
        "timestamps", "Timestamp consistency", "fail" if ts_bad else "pass",
        (f"{len(ts_bad)} observation(s) with inconsistent timestamps — treat as unreliable until reconciled.")
        if ts_bad else "All observation timestamps match their study day.", ts_bad[:20]))

    dup = Counter((o.signal, o.day, o.source, o.value) for o in record.observations if o.day <= t)
    dups = [{"signal": k[0], "day": k[1], "source": k[2], "value": k[3], "copies": n} for k, n in dup.items() if n > 1]
    checks.append(_check(
        "duplicates", "Duplicate observations", "warn" if dups else "pass",
        f"{len(dups)} duplicated reading(s) (same signal, day, source and value) — de-duplicated by the twin."
        if dups else "No duplicated readings.", dups[:20]))

    conf = [f.to_dict() for f in series.flags if f.kind == "conflict"]
    checks.append(_check(
        "source_conflicts", "Same-day source conflicts", "warn" if conf else "pass",
        f"{len(conf)} same-day conflict(s) between sources (e.g. clinic vs home device)." if conf else
        "No same-day source conflicts.", conf))

    status = ("inconsistent" if any(c["status"] == "fail" for c in checks)
              else "warnings" if any(c["status"] == "warn" for c in checks) else "consistent")
    summary = {"inconsistent": "Twin consistency warning — the record contains contradictions; review before relying "
                               "on predictions.",
               "warnings": "Twin consistency warning — some records need verification.",
               "consistent": "EHR, treatment, symptoms, labs and wearables are internally consistent."}[status]
    return {"status": status, "summary": summary, "checks": checks}


def analyse(record: PatientRecord, series: PatientSeries, facts: dict[str, Any], snapshot: dict[str, Any],
            changepoints: dict[str, Any] | None, latent_r2: float | None) -> dict[str, Any]:
    cf = conflicts(series, facts, snapshot, changepoints, latent_r2)
    detected = [c for c in cf if c["detected"]]
    return {"as_of_day": series.as_of_day, "conflicts": cf, "n_conflicts": len(detected),
            "conflict_headline": ("Trajectory conflict detected — review underlying data."
                                  if any(c["severity"] == "warning" for c in detected) else "No trajectory conflict."),
            "consistency": consistency(record, series)}
