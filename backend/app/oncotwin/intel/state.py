"""Living Twin State — the patient's evolving, structured, machine-readable state.

For every day d the engine builds a 19-dimension state vector from
  (a) the as-of FACTS captured while the per-day history is computed
      (`day_facts`, only data dated ≤ d), and
  (b) that day's final history snapshot (tier after hysteresis, risk,
      trajectory pattern, latent loads).

States are never overwritten. The per-day state history is reproducible from
the record (so "what did the twin know on Day 24?" is always answerable), and
every committed evaluation writes the state's SHA-256 plus the transitions
since the previous evaluation to the hash-chained audit ledger.

Each dimension carries
  status        a CATEGORICAL label — a transition fires only when it changes,
                so day-to-day noise in the numbers never creates a transition
  severity      normal | attention | alert (visual weight only)
  fields        the numbers behind the status
  basis         observed (recorded fact) | computed (deterministic function of
                observations vs the personal baseline) | model-derived
  confidence    0–1, measured (completeness / recency / prediction confidence)
  data_quality  "ok" or the active data-quality flags touching its inputs
  sources       FHIR resource types + ids the dimension was built from
A transition records day, twin time, dimension, previous → new status, the
computed reason, sources, confidence and data quality.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline, adverse_z
from app.oncotwin.engine.features import IDX, signal_matrix
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.engine.state import LATENT_LABELS, confidence
from app.oncotwin.records import PatientRecord, day_to_iso
from app.oncotwin.signals import LAB_SIGNALS, MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P
from app.oncotwin.simulator.regimens import REGIMENS

DIMENSIONS: dict[str, dict[str, str]] = {
    "demographic": {"label": "Demographic", "group": "static"},
    "clinical": {"label": "Clinical", "group": "clinical"},
    "cancer": {"label": "Cancer", "group": "static"},
    "treatment": {"label": "Treatment", "group": "clinical"},
    "physiological": {"label": "Physiological", "group": "dynamic"},
    "laboratory": {"label": "Laboratory", "group": "clinical"},
    "pathology": {"label": "Pathology", "group": "static"},
    "genomic": {"label": "Genomic", "group": "static"},
    "medication": {"label": "Medication", "group": "clinical"},
    "symptom": {"label": "Symptom", "group": "dynamic"},
    "activity": {"label": "Activity", "group": "dynamic"},
    "sleep": {"label": "Sleep", "group": "dynamic"},
    "nutrition_recovery": {"label": "Nutrition / recovery", "group": "dynamic"},
    "adherence": {"label": "Adherence", "group": "clinical"},
    "risk": {"label": "Risk", "group": "twin"},
    "trajectory": {"label": "Trajectory", "group": "twin"},
    "uncertainty": {"label": "Uncertainty", "group": "twin"},
    "data_quality": {"label": "Data quality", "group": "twin"},
    "intervention": {"label": "Intervention", "group": "clinical"},
}
DIMENSION_ORDER = tuple(DIMENSIONS)
VITALS = ("resting_hr", "hrv_sdnn", "temperature", "spo2", "sbp")
SEVERITY_RANK = {"normal": 0, "attention": 1, "alert": 2}
INTERVENTION_WINDOW_DAYS = 14
# Dimensions derived from noisy daily signals get the same hysteresis as the
# tier engine: escalation is immediate, a milder/sideways status is shown only
# after it held on CONFIRM_DAYS consecutive days (the day's raw value is kept
# under "pending" so nothing is hidden).
DEBOUNCED = ("physiological", "symptom", "activity", "sleep", "nutrition_recovery", "trajectory",
             "uncertainty", "data_quality")
CONFIRM_DAYS = 2


def _f(v: Any, nd: int = 3) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if np.isnan(v) else round(v, nd)


# =============================================================================
# Per-day facts (captured inside the as-of history loop)
# =============================================================================


def day_facts(s: PatientSeries, b: Baseline, F: np.ndarray, ctx: dict[str, Any],
              p: float, lo: float, hi: float) -> dict[str, Any]:
    """Compact facts for day `s.as_of_day`, computed ONLY from the as-of series."""
    t = s.as_of_day
    idx = t - 1
    lo3 = max(0, idx - 2)
    Z = adverse_z(signal_matrix(s), b)[0]                       # (T, S) — no carry-forward
    signals: dict[str, Any] = {}
    for i, k in enumerate(MODEL_SIGNALS):
        vals = s.values[k][lo3: idx + 1]
        n3 = int(np.sum(~np.isnan(vals)))
        base = b.signals.get(k)
        signals[k] = {
            "v": _f(s.values[k][idx], 2), "id": s.obs_ids[k][idx],
            "m3": _f(np.nanmean(vals), 3) if n3 else None, "n3": n3,
            "z": _f(F[idx, IDX[f"z_{k}"]], 2),
            "z3": _f(np.nanmean(Z[lo3: idx + 1, i]), 2) if n3 else None,
            "slope3": _f(F[idx, IDX[f"slope3_{k}"]], 2),
            "ids3": [x for x in s.obs_ids[k][lo3: idx + 1] if x],
            "base": base.display()["median"] if base is not None and base.n_days else None,
        }
    sym = s.values["symptom_score"]
    sym_prev = next((float(sym[j]) for j in range(idx - 3, max(-1, idx - 6), -1) if j >= 0 and not np.isnan(sym[j])), None)
    signals["symptom_score"]["change3"] = (None if signals["symptom_score"]["v"] is None or sym_prev is None
                                           else round(signals["symptom_score"]["v"] - sym_prev, 2))
    # Analytic features (feature store): sleep debt, weight velocity.
    sb = signals["sleep_hours"]["base"]
    sl7 = s.values["sleep_hours"][max(0, idx - 6): idx + 1]
    signals["sleep_hours"]["debt7"] = (round(float(np.nansum(np.maximum(0.0, sb - sl7))), 2)
                                       if sb is not None and np.any(~np.isnan(sl7)) else None)
    w = s.values["weight"][max(0, idx - 6): idx + 1]
    wd = np.arange(len(w))[~np.isnan(w)]
    signals["weight"]["velocity7"] = (round(float(np.polyfit(wd, w[~np.isnan(w)], 1)[0]), 3)
                                      if wd.size >= 3 else None)

    labs: dict[str, Any] = {}
    for k in LAB_SIGNALS:
        rows = [r for r in s.labs.get(k, []) if r[0] <= t]
        if rows:
            d, v, oid = rows[-1]
            labs[k] = {"v": round(v, 3), "day": d, "id": oid, "first": round(rows[0][1], 3),
                       "prev": round(rows[-2][1], 3) if len(rows) >= 2 else None,
                       "prev_day": rows[-2][0] if len(rows) >= 2 else None}

    dose_days = sorted(s.dose_days)
    dsd = s.days_since_dose()[idx]
    reg = s.regimen
    last_dose = dose_days[-1] if dose_days else None
    nadir = bool(float(np.asarray(ctx["nadir"])[idx]) >= 0.25 * max(reg.myelotox, 1e-6))
    phase = None
    if last_dose is not None:
        phase = "post-dose" if dsd <= 4 else ("nadir window" if nadir else "recovery phase")
    next_planned = next((d for d in s.planned_dose_days if d > t and not any(abs(d - g) <= 3 for g in dose_days)), None)
    treatment = {
        "cycle": len(dose_days), "last_dose_day": last_dose,
        "day_of_cycle": None if np.isnan(dsd) else int(dsd) + 1, "phase": phase, "in_nadir_window": nadir,
        "next_planned_dose_day": next_planned,
        "dose_scale": s.dose_days[last_dose] if last_dose is not None else None,
        "gcsf_this_cycle": bool(s.gcsf_since_last_dose()[idx] > 0),
        "dose_ids": [e.id for e in s.events if e.kind == "chemo_dose" and e.day == last_dose],
    }
    recent = []
    for e in s.events:
        if e.kind in ("antibiotic", "hydration", "gcsf_dose", "careplan", "clinician_note", "encounter") \
                and 1 <= e.day <= t and e.day >= t - INTERVENTION_WINDOW_DAYS:
            det = {k: e.detail[k] for k in ("indication", "duration_days", "change", "qualifying", "encounter_class",
                                            "condition", "discharge_day") if k in e.detail}
            recent.append({"id": e.id, "day": e.day, "kind": e.kind, "display": e.display, "detail": det})
    supportive7 = [e.id for e in s.events if e.kind == "supportive_dose" and t - 6 <= e.day <= t]

    adh, sched = np.asarray(ctx["adherence_7d"]), np.asarray(ctx["adherence_sched"])
    missed7 = int(sum(sch - tk for d, (tk, sch) in s.adherence.items() if t - 6 <= d <= t))

    flags = []
    for f in s.flags:
        if f.kind == "gap" and f.severity == "info":
            continue
        if f.kind == "stale" or any(d >= t - 6 for d in f.days):
            flags.append({"kind": f.kind, "signal": f.signal, "days": f.days[-5:], "severity": f.severity,
                          "message": f.message, "observation_ids": f.observation_ids[:4]})
    conf = confidence(s, b, p, lo, hi)
    adm = s.in_acute_care_now()
    discharged = [a for a in s.admissions if a.get("discharge_day") is not None and a["discharge_day"] <= t]
    return {
        "day": t,
        "signals": signals,
        "labs": labs,
        "treatment": treatment,
        "recent_events": recent,
        "supportive_dose_ids_7d": supportive7[-6:],
        "adherence": {"frac": round(float(adh[idx]), 3), "scheduled": int(sched[idx]), "missed": missed7},
        "quality": {
            "completeness": round(float(np.mean([s.quality[k].completeness_7d for k in MODEL_SIGNALS])), 3),
            "freshness": round(float(np.mean([s.quality[k].freshness for k in MODEL_SIGNALS])), 3),
            "stale": [k for k in MODEL_SIGNALS if not s.quality[k].fresh],
            "flags": flags,
        },
        "confidence": {"score": conf["score"], "label": conf["label"], "components": conf["components"]},
        "care": {"admission": None if adm is None else {k: adm.get(k) for k in ("id", "day", "condition", "display")},
                 "last_discharge_day": max((a["discharge_day"] for a in discharged), default=None)},
        "multi": {"n_concordant": int(F[idx, IDX["n_concordant"]]), "anomaly": _f(F[idx, IDX["anomaly"]], 2),
                  "persist_max": int(F[idx, IDX["persist_max"]])},
        "baseline": {"window": list(b.window), "kind": b.kind, "adequacy": round(b.adequacy, 3)},
        "model_risk": {"p": round(p, 4), "lo": round(lo, 4), "hi": round(hi, 4)},
        # The exact model input row of this day (feature store + drift monitor); not sent to the UI wholesale.
        "x": [round(float(v), 5) for v in F[idx]],
        "missing_today": [k for k in MODEL_SIGNALS if np.isnan(s.values[k][idx])],
    }


# =============================================================================
# State vector
# =============================================================================


def _dim(status: str, *, severity: str = "normal", basis: str = "observed", fields: dict[str, Any] | None = None,
         confidence: float | None = 1.0, data_quality: str | list = "ok",
         sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": status, "severity": severity, "basis": basis, "fields": fields or {},
            "confidence": None if confidence is None else round(float(confidence), 3),
            "data_quality": data_quality, "sources": sources or []}


def _zcat(z3: float | None, n3: int, adverse: str, better: str) -> tuple[str, str]:
    if not n3 or z3 is None:
        return "no recent data", "attention"
    if z3 >= 3.0:
        return f"markedly {adverse}", "alert"
    if z3 >= 2.0:
        return adverse, "attention"
    if z3 >= 1.0:
        return f"mildly {adverse}", "normal"
    if z3 <= -1.5:
        return better, "normal"
    return "at personal baseline", "normal"


def _signal_quality(facts: dict[str, Any], keys: tuple[str, ...]) -> str | list[str]:
    msgs = [f["message"] for f in facts["quality"]["flags"] if f["signal"] in keys]
    return msgs or "ok"


def _obs_sources(facts: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    ids = [i for k in keys for i in facts["signals"].get(k, {}).get("ids3", [])]
    return [{"type": "Observation", "ids": ids}] if ids else []


class _Static:
    """Pre-indexed static EHR context (diagnosis, pathology, genomics, comorbidities)."""

    def __init__(self, record: PatientRecord):
        self.record = record
        self.by_kind: dict[str, list] = {}
        for e in record.events:
            self.by_kind.setdefault(e.kind, []).append(e)

    def first(self, kind: str, day: int, pred=lambda e: True):
        return next((e for e in self.by_kind.get(kind, []) if e.day <= day and pred(e)), None)

    def all(self, kind: str, day: int, pred=lambda e: True):
        return [e for e in self.by_kind.get(kind, []) if e.day <= day and pred(e)]


def _state_for_day(static: _Static, snap: dict[str, Any], facts: dict[str, Any],
                   recovery_index: float | None) -> dict[str, Any]:
    prof = static.record.profile
    d = facts["day"]
    sig = facts["signals"]
    dims: dict[str, dict[str, Any]] = {}

    dims["demographic"] = _dim(
        f"{prof.age}{prof.sex[0].upper()} · {'age ≥ 65' if prof.age >= 65 else 'age < 65'}",
        fields={"age": prof.age, "sex": prof.sex, "age_65_or_over": prof.age >= 65},
        sources=[{"type": "Patient", "ids": [prof.patient_id]}])

    adm = facts["care"]["admission"]
    ecog_ev = static.first("performance_status", d)
    comorb = static.all("diagnosis", d, lambda e: e.detail.get("comorbidity"))
    dims["clinical"] = _dim(
        f"inpatient — {str(adm['condition']).replace('_', ' ')}" if adm else "outpatient",
        severity="alert" if adm else "normal",
        fields={"care_setting": "inpatient (qualifying acute care)" if adm else "outpatient", "ecog": prof.ecog,
                "comorbidities": [e.display for e in comorb], "admission": adm,
                "last_discharge_day": facts["care"]["last_discharge_day"]},
        sources=[x for x in (
            {"type": "Encounter", "ids": [adm["id"]]} if adm else None,
            {"type": "Observation", "ids": [ecog_ev.id]} if ecog_ev else None,
            {"type": "Condition", "ids": [e.id for e in comorb]} if comorb else None) if x])

    diag = static.first("diagnosis", d, lambda e: not e.detail.get("comorbidity"))
    dims["cancer"] = _dim(
        f"{prof.icd10} · stage {prof.stage}",
        fields={"diagnosis": prof.cancer, "icd10": prof.icd10, "stage": prof.stage,
                "diagnosed": diag.effective[:10] if diag else None},
        sources=[{"type": "Condition", "ids": [diag.id]}] if diag else [])

    path = static.first("pathology", d)
    dims["pathology"] = _dim(
        "report on file" if path else "no report on file", severity="normal" if path else "attention",
        fields={"summary": path.display if path else None, "biomarkers": prof.biomarkers,
                "reported": path.effective[:10] if path else None},
        sources=[{"type": "DiagnosticReport", "ids": [path.id]}] if path else [])

    geno = static.first("genomics", d)
    dims["genomic"] = _dim(
        "molecular profile on file" if geno else "no molecular profile",
        fields={"markers": (geno.detail.get("biomarkers") if geno else {}), "reported": geno.effective[:10] if geno else None},
        sources=[{"type": "DiagnosticReport", "ids": [geno.id]}] if geno else [])

    tx = facts["treatment"]
    reg = REGIMENS[prof.regimen_code]
    plan = static.first("careplan", d, lambda e: "regimen" in e.detail)
    dims["treatment"] = _dim(
        "pre-treatment" if not tx["cycle"] else f"cycle {tx['cycle']} · {tx['phase']}",
        severity="attention" if tx["in_nadir_window"] else "normal",
        fields={"regimen": reg.code, "regimen_name": reg.name, **{k: tx[k] for k in (
            "cycle", "day_of_cycle", "last_dose_day", "next_planned_dose_day", "dose_scale", "gcsf_this_cycle",
            "in_nadir_window")},
            "phase_basis": "days since dose; nadir window from the regimen-timing model (simulation parameter)"},
        sources=[x for x in ({"type": "MedicationAdministration", "ids": tx["dose_ids"]} if tx["dose_ids"] else None,
                             {"type": "CarePlan", "ids": [plan.id]} if plan else None) if x])

    # Medication classes currently active
    classes: set[str] = set()
    med_ids: list[str] = []
    if tx["last_dose_day"] is not None and d - tx["last_dose_day"] <= reg.cycle_days + 7:
        classes.add("chemotherapy")
        med_ids += tx["dose_ids"]
    for e in facts["recent_events"]:
        if e["kind"] == "gcsf_dose" and d - e["day"] < P.GCSF_ACTIVE_DAYS:
            classes.add("G-CSF")
            med_ids.append(e["id"])
        elif e["kind"] == "antibiotic" and d <= e["day"] + int(e["detail"].get("duration_days", 7)) - 1:
            classes.add("antibiotics")
            med_ids.append(e["id"])
        elif e["kind"] == "hydration" and d - e["day"] <= 1:
            classes.add("IV hydration")
            med_ids.append(e["id"])
    if facts["supportive_dose_ids_7d"]:
        classes.add("supportive (antiemetic/antidiarrheal)")
        med_ids += facts["supportive_dose_ids_7d"][-2:]
    dims["medication"] = _dim(
        " + ".join(sorted(classes)) if classes else "none active",
        fields={"active_classes": sorted(classes), "regimen_drugs": [x.name for x in reg.drugs]},
        sources=[{"type": "MedicationAdministration/MedicationRequest", "ids": med_ids}] if med_ids else [])

    labs = facts["labs"]
    anc = labs.get("anc")
    lab_age = d - max((v["day"] for v in labs.values()), default=-999)
    status, sev = "within reference flags", "normal"
    if not labs or lab_age > 14:
        status, sev = "no recent labs (> 14 d)", "attention"
    elif anc and anc["v"] < 0.5 and d - anc["day"] <= 7:
        status, sev = "ANC < 0.5 ×10³/µL", "alert"
    elif anc and anc["v"] < 1.0 and d - anc["day"] <= 7:
        status, sev = "ANC 0.5–1.0 ×10³/µL", "alert"
    elif anc and anc["v"] < 1.5 and d - anc["day"] <= 7:
        status, sev = "ANC 1.0–1.5 ×10³/µL", "attention"
    elif labs.get("hemoglobin") and labs["hemoglobin"]["v"] < 10:
        status, sev = "hemoglobin < 10 g/dL", "attention"
    elif labs.get("platelets") and labs["platelets"]["v"] < 100:
        status, sev = "platelets < 100 ×10³/µL", "attention"
    elif labs.get("creatinine") and labs["creatinine"]["v"] >= 1.5 * labs["creatinine"]["first"]:
        status, sev = "creatinine ≥ 1.5 × own first value", "attention"
    dims["laboratory"] = _dim(
        status, severity=sev,
        fields={k: {"value": v["v"], "day": v["day"], "unit": SIGNALS[k].unit_display} for k, v in labs.items()}
        | {"days_since_last_draw": lab_age if labs else None},
        confidence=max(0.0, 1.0 - max(0, lab_age) / 14.0) if labs else 0.0,
        sources=[{"type": "Observation", "ids": [v["id"] for v in labs.values()]}] if labs else [])

    # Physiological: vital signs vs personal baseline + latent twin loads
    vit = {k: sig[k]["z3"] for k in VITALS if sig[k]["z3"] is not None}
    dev = sorted(((k, z) for k, z in vit.items() if z >= 1.5), key=lambda kv: -kv[1])
    n = len(dev)
    top = max((z for _, z in dev), default=0.0)
    if n == 0:
        status, sev = "within personal range", "normal"
    elif n == 1:
        status, sev = "isolated deviation", "attention" if top >= 2.0 else "normal"
    elif n >= 3 or top >= 3.0:
        status, sev = "marked multi-signal deviation", "alert"
    else:
        status, sev = "multi-signal deviation", "attention"
    lat = snap.get("latent", {})
    dominant = max(lat, key=lambda k: lat[k]) if lat else None
    dims["physiological"] = _dim(
        status, severity=sev, basis="computed (vs personal baseline) + model-derived (latent loads)",
        fields={"deviating": [{"signal": k, "label": SIGNALS[k].label, "z3": z} for k, z in dev],
                "vitals_z3": vit,
                "latent_loads": {k: {"label": LATENT_LABELS[k], "value": v} for k, v in lat.items()},
                "dominant_latent": (LATENT_LABELS[dominant] if dominant and lat[dominant] >= 0.3 else None),
                "n_concordant_all_signals": facts["multi"]["n_concordant"]},
        confidence=float(np.mean([sig[k]["n3"] / 3 for k in VITALS])),
        data_quality=_signal_quality(facts, VITALS), sources=_obs_sources(facts, VITALS))

    for key, sk, adverse, better in (("symptom", "symptom_score", "elevated", "below baseline"),
                                     ("activity", "steps", "reduced", "above baseline"),
                                     ("sleep", "sleep_hours", "reduced", "above baseline")):
        si = sig[sk]
        status, sev = _zcat(si["z3"], si["n3"], adverse, better)
        fields: dict[str, Any] = {"signal": sk, "value_3d_mean": si["m3"], "personal_baseline": si["base"],
                                  "z_3d": si["z3"], "unit": SIGNALS[sk].unit_display}
        if si["m3"] is not None and si["base"]:
            fields["pct_vs_baseline"] = round(100.0 * (si["m3"] - si["base"]) / si["base"], 1)
            fields["delta_vs_baseline"] = round(si["m3"] - si["base"], 2)
        if sk == "sleep_hours":
            fields["sleep_debt_7d_h"] = si.get("debt7")
        if sk == "symptom_score":
            fields["change_3d"] = si.get("change3")
        dims[key] = _dim(status, severity=sev, basis="computed (vs personal baseline)", fields=fields,
                         confidence=si["n3"] / 3, data_quality=_signal_quality(facts, (sk,)),
                         sources=_obs_sources(facts, (sk,)))

    wi = sig["weight"]
    pct = None if (wi["m3"] is None or not wi["base"]) else 100.0 * (wi["m3"] - wi["base"]) / wi["base"]
    if pct is None:
        status, sev = "no recent weight", "attention"
    elif pct <= -5:
        status, sev = "weight loss ≥ 5 %", "alert"
    elif pct <= -2:
        status, sev = "weight loss 2–5 %", "attention"
    elif pct >= 2:
        status, sev = "weight gain ≥ 2 %", "normal"
    else:
        status, sev = "weight stable", "normal"
    dims["nutrition_recovery"] = _dim(
        status, severity=sev, basis="computed (vs personal baseline)",
        fields={"weight_3d_mean_kg": wi["m3"], "personal_baseline_kg": wi["base"],
                "pct_vs_baseline": None if pct is None else round(pct, 2), "weight_velocity_kg_per_day": wi.get("velocity7"),
                "recovery_index": recovery_index,
                "recovery_index_meaning": "fraction of the recent peak latent load that has resolved (twin model)"},
        confidence=wi["n3"] / 3, data_quality=_signal_quality(facts, ("weight",)), sources=_obs_sources(facts, ("weight",)))

    a = facts["adherence"]
    if not a["scheduled"]:
        status, sev = "no supportive doses scheduled", "normal"
    elif a["frac"] >= 0.9:
        status, sev = "on schedule (≥ 90 %)", "normal"
    elif a["frac"] >= 0.6:
        status, sev = "partial (60–90 %)", "attention"
    else:
        status, sev = "low (< 60 %)", "alert"
    dims["adherence"] = _dim(status, severity=sev, fields={"adherence_7d": a["frac"], "scheduled_7d": a["scheduled"],
                                                            "missed_7d": a["missed"]},
                             sources=[{"type": "MedicationAdministration", "ids": facts["supportive_dose_ids_7d"]}]
                             if facts["supportive_dose_ids_7d"] else [])

    tier = snap["tier"]
    sev = {"HIGH PRIORITY": "alert", "EARLY WARNING": "alert", "WATCH": "attention", "IN ACUTE CARE": "attention"}.get(tier, "normal")
    dims["risk"] = _dim(
        tier, severity=sev, basis="model-derived",
        fields={"risk_7d": snap["risk"], "p10": snap["risk_p10"], "p90": snap["risk_p90"], "outcome_id": "OT-ACUTE-7",
                "probability_tier": snap["probability_tier"], "rule_tier": snap["rule_tier"],
                "rules": [r["rule"] for r in snap["rules"]],
                "top_contributors": snap["top_contributors"]},
        confidence=facts["confidence"]["score"])

    dims["trajectory"] = _dim(
        snap["pattern"], severity="alert" if "deterioration" in snap["pattern"] or "sudden" in snap["pattern"]
        else "attention" if snap["pattern"] in ("emerging deviation", "isolated deviation") else "normal",
        basis="computed (multivariate personal-baseline trajectory)",
        fields=facts["multi"])

    c = facts["confidence"]
    dims["uncertainty"] = _dim(
        f"{c['label']} confidence", severity={"low": "attention"}.get(c["label"], "normal"), basis="computed",
        fields={"score": c["score"], **c["components"]}, confidence=c["score"])

    q = facts["quality"]
    warn = [f for f in q["flags"] if f["severity"] in ("warning", "critical")]
    if q["completeness"] < 0.5 or len(q["stale"]) >= 3:
        status, sev = "poor", "alert"
    elif q["completeness"] < 0.8 or warn or q["stale"]:
        status, sev = "degraded", "attention"
    else:
        status, sev = "good", "normal"
    dims["data_quality"] = _dim(
        status, severity=sev, basis="computed",
        fields={"completeness_7d": q["completeness"], "freshness": q["freshness"], "stale_signals": q["stale"],
                "active_flags": [{"kind": f["kind"], "signal": f["signal"], "message": f["message"]} for f in q["flags"]]},
        confidence=q["completeness"], data_quality=[f["message"] for f in warn] or "ok",
        sources=[{"type": "Observation", "ids": [i for f in q["flags"] for i in f["observation_ids"]]}]
        if any(f["observation_ids"] for f in q["flags"]) else [])

    kinds: set[str] = set()
    iv_ids = []
    for e in facts["recent_events"]:
        label = {
            "antibiotic": "antibiotics", "hydration": "IV hydration",
            "careplan": "care-plan change" if e["detail"].get("change") else None,   # revisions, not the initial plan
            "clinician_note": "care-team outreach",
        }.get(e["kind"])
        if e["kind"] == "gcsf_dose":
            label = "G-CSF (treatment)" if e["detail"].get("indication") == "treatment" else None
        if e["kind"] == "encounter" and not e["detail"].get("qualifying"):
            label = "urgent evaluation"
        if label:
            kinds.add(label)
            iv_ids.append(e["id"])
    dims["intervention"] = _dim(
        " + ".join(sorted(kinds)) if kinds else f"none in last {INTERVENTION_WINDOW_DAYS} days",
        fields={"recent": [e for e in facts["recent_events"] if e["id"] in iv_ids]},
        sources=[{"type": "Encounter/MedicationRequest/MedicationAdministration/CarePlan", "ids": iv_ids}] if iv_ids else [])

    return {"day": d, "as_of_time": day_to_iso(d, 23, 59), "dimensions": {k: dims[k] for k in DIMENSION_ORDER}}


def _debounce(states: list[dict[str, Any]]) -> None:
    for key in DEBOUNCED:
        shown: tuple[str, str] | None = None
        cand, cand_n = None, 0
        for st in states:
            dim = st["dimensions"][key]
            raw = (dim["status"], dim["severity"])
            if shown is None or raw[0] == shown[0] or SEVERITY_RANK[raw[1]] > SEVERITY_RANK[shown[1]]:
                shown, cand, cand_n = raw, None, 0
                continue
            cand_n = cand_n + 1 if cand == raw[0] else 1
            cand = raw[0]
            if cand_n >= CONFIRM_DAYS:
                shown, cand, cand_n = raw, None, 0
                continue
            dim["pending"] = {"status": raw[0], "severity": raw[1], "consecutive_days": cand_n,
                              "note": (f"Held by hysteresis: today's values meet '{raw[0]}'; a milder or sideways "
                                       f"change is confirmed after {CONFIRM_DAYS} consecutive days.")}
            dim["status"], dim["severity"] = shown


def state_hash(state: dict[str, Any]) -> str:
    body = {"day": state["day"], "dimensions": {k: {"status": v["status"], "fields": v["fields"]}
                                                for k, v in state["dimensions"].items()}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _recovery_indices(snapshots: list[dict[str, Any]]) -> list[float | None]:
    """Per day: fraction of the recent (≤10-day) peak total latent load that has resolved."""
    tot = np.array([sum(s.get("latent", {}).values()) for s in snapshots], dtype=float)
    out: list[float | None] = []
    for i in range(len(tot)):
        w = tot[max(0, i - 10): i + 1]
        peak = float(w.max()) if w.size else 0.0
        out.append(None if peak < 0.3 else round(float(np.clip(1.0 - w[-1] / peak, 0.0, 1.0)), 3))
    return out


def build_states(record: PatientRecord, snapshots: list[dict[str, Any]],
                 facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The full per-day state history (index = day-1)."""
    static = _Static(record)
    rec_idx = _recovery_indices(snapshots)
    states = [_state_for_day(static, snap, f, rec_idx[i]) for i, (snap, f) in enumerate(zip(snapshots, facts, strict=True))]
    _debounce(states)
    for st in states:
        st["sha256"] = state_hash(st)
    return states


# =============================================================================
# Transitions (the state-change ledger)
# =============================================================================


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:+.0f}%"


def _reason(key: str, prev: dict[str, Any], cur: dict[str, Any]) -> str:
    f = cur["fields"]
    if key in ("activity", "sleep", "symptom"):
        if f.get("value_3d_mean") is None:
            return "No readings in the last 3 days."
        unit = f.get("unit", "")
        dec = SIGNALS[f["signal"]].decimals

        def fmt(v: float) -> str:
            return f"{v:,.0f}" if dec == 0 else f"{v:.{dec}f}"
        txt = (f"3-day mean {fmt(f['value_3d_mean'])} {unit} vs personal baseline {fmt(f['personal_baseline'])} {unit}"
               f" ({_pct(f.get('pct_vs_baseline'))}; {f['z_3d']:+.1f} SD adverse)")
        if key == "sleep" and f.get("sleep_debt_7d_h") is not None:
            txt += f"; 7-day sleep debt {f['sleep_debt_7d_h']:.1f} h"
        return txt + "."
    if key == "physiological":
        if not f["deviating"]:
            return "No vital sign beyond 1.5 SD of the personal baseline (3-day mean)."
        dev = ", ".join(f"{x['label']} {x['z3']:+.1f} SD" for x in f["deviating"])
        dom = f" Twin latent pattern: {f['dominant_latent'].lower()}." if f.get("dominant_latent") else ""
        return f"{len(f['deviating'])} vital sign(s) beyond 1.5 SD adverse (3-day mean): {dev}.{dom}"
    if key == "laboratory":
        parts = [f"{SIGNALS[k].label} {v['value']:g} {v['unit']} (Day {v['day']})" for k, v in f.items()
                 if isinstance(v, dict) and "value" in v]
        return ("Latest results: " + "; ".join(parts) + ".") if parts else "No laboratory result in the last 14 days."
    if key == "treatment":
        if not f["cycle"]:
            return "No chemotherapy administered yet."
        return (f"Cycle {f['cycle']} (last dose Day {f['last_dose_day']}, day {f['day_of_cycle']} of cycle"
                f"{', expected nadir window' if f['in_nadir_window'] else ''}).")
    if key == "medication":
        before, after = set(prev["fields"].get("active_classes", [])), set(f.get("active_classes", []))
        added, removed = sorted(after - before), sorted(before - after)
        return "; ".join(x for x in (f"started/recorded: {', '.join(added)}" if added else "",
                                    f"no longer active: {', '.join(removed)}" if removed else "") if x) + "."
    if key == "adherence":
        return (f"7-day supportive-medication adherence {f['adherence_7d']:.0%} "
                f"({f['missed_7d']} missed of {f['scheduled_7d']} scheduled).")
    if key == "nutrition_recovery":
        if f.get("pct_vs_baseline") is None:
            return "No recent weight reading."
        vel = f.get("weight_velocity_kg_per_day")
        return (f"Weight 3-day mean {f['weight_3d_mean_kg']:.1f} kg vs baseline {f['personal_baseline_kg']} kg "
                f"({f['pct_vs_baseline']:+.1f}%)" + (f"; trend {vel:+.2f} kg/day" if vel is not None else "") + ".")
    if key == "risk":
        pf = prev["fields"]
        drivers = ", ".join(c["label"] for c in f["top_contributors"] if c["logit"] > 0) or "—"
        rules = f"; rules: {', '.join(f['rules'])}" if f["rules"] else ""
        return (f"7-day risk {pf['risk_7d']:.1%} → {f['risk_7d']:.1%} (80% interval {f['p10']:.1%}–{f['p90']:.1%}); "
                f"tier basis: probability tier {f['probability_tier']}, rule tier {f['rule_tier']}, then 2-day "
                f"de-escalation hysteresis; main drivers: {drivers}{rules}.")
    if key == "trajectory":
        return (f"{f['n_concordant']} signal(s) ≥ 1.5 SD adverse together; Mahalanobis anomaly {f['anomaly']}; "
                f"longest persistence {f['persist_max']} d.")
    if key == "uncertainty":
        return (f"Confidence score {f['score']:.2f} (completeness {f['input_completeness_7d']:.0%}, freshness "
                f"{f['input_freshness']:.0%}, model agreement {f['model_agreement']:.0%}).")
    if key == "data_quality":
        flags = "; ".join(x["message"] for x in f["active_flags"][:2])
        return f"7-day completeness {f['completeness_7d']:.0%}" + (f"; {flags}" if flags else "") + "."
    if key == "intervention":
        rec = f.get("recent", [])
        return ("; ".join(f"{e['display']} (Day {e['day']})" for e in rec[-3:]) + ".") if rec else "No recent intervention."
    if key == "clinical":
        adm = f.get("admission")
        if adm:
            return f"{adm['display']} (Day {adm['day']})."
        return f"Outpatient{f' — discharged Day ' + str(f['last_discharge_day']) if f.get('last_discharge_day') else ''}."
    return f"{prev['status']} → {cur['status']}."


def _direction(a: dict[str, Any], b: dict[str, Any]) -> str:
    ds = SEVERITY_RANK[b["severity"]] - SEVERITY_RANK[a["severity"]]
    return "worsening" if ds > 0 else "improving" if ds < 0 else "change"


def transitions(states: list[dict[str, Any]], *, from_day: int | None = None,
                to_day: int | None = None) -> list[dict[str, Any]]:
    """Every categorical status change between consecutive days (oldest first)."""
    out: list[dict[str, Any]] = []
    for prev, cur in zip(states, states[1:]):
        if (from_day is not None and cur["day"] < from_day) or (to_day is not None and cur["day"] > to_day):
            continue
        for key in DIMENSION_ORDER:
            a, b = prev["dimensions"][key], cur["dimensions"][key]
            if a["status"] == b["status"]:
                continue
            out.append({
                "day": cur["day"], "at": cur["as_of_time"], "dimension": key, "label": DIMENSIONS[key]["label"],
                "previous": a["status"], "new": b["status"], "direction": _direction(a, b),
                "severity": b["severity"], "reason": _reason(key, a, b), "basis": b["basis"],
                "sources": b["sources"], "confidence": b["confidence"], "data_quality": b["data_quality"],
                "state_sha256": cur["sha256"],
            })
    return out


def compare(states: list[dict[str, Any]], day_a: int, day_b: int) -> dict[str, Any]:
    """WHAT CHANGED between two as-of days: net change per dimension + the path of transitions."""
    a, b = states[day_a - 1], states[day_b - 1]
    changed = []
    for key in DIMENSION_ORDER:
        x, y = a["dimensions"][key], b["dimensions"][key]
        if x["status"] != y["status"]:
            changed.append({"dimension": key, "label": DIMENSIONS[key]["label"], "previous": x["status"],
                            "current": y["status"], "severity": y["severity"], "direction": _direction(x, y),
                            "reason": _reason(key, x, y), "basis": y["basis"], "sources": y["sources"]})
    changed.sort(key=lambda c: (-SEVERITY_RANK[c["severity"]], c["direction"] != "worsening"))
    return {"from_day": day_a, "to_day": day_b, "from_sha256": a["sha256"], "to_sha256": b["sha256"],
            "changed": changed,
            "unchanged": [k for k in DIMENSION_ORDER if a["dimensions"][k]["status"] == b["dimensions"][k]["status"]],
            "transitions": transitions(states, from_day=day_a + 1, to_day=day_b)}
