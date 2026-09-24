"""Counterfactual Twin — Observed Twin vs Simulated (counterfactual) Twin.

Pick an anchor day in the past (typically the day of an alert or of an
intervention). Two twins are then compared day by day up to the live day:

  Observed twin        what actually happened after the anchor: the as-of risk
                       history, observed signals, ANC labs, recorded
                       interventions and outcomes
  Counterfactual twin  the twin rolled forward FROM THE ANCHOR under a
                       scenario — by default "current trajectory", i.e. no new
                       clinical action after the anchor — using only data
                       available on the anchor day

Reported: per-day risk (observed vs simulated median and 80 % band), the
share of observed days inside the simulated band, the first divergence day,
and signal-level differences. When an intervention happened after the anchor,
the gap is what the twin associates with "what was done" — under its model
assumptions only.

Synthetic validation: for synthetic patients the generator's script is known,
so the TRUE counterfactual can be produced by re-running the simulator
without the post-anchor interventions. It is shown only to validate the
twin's counterfactual engine and is unavailable for real patients.

Everything here is a SIMULATION — not a clinical prediction, not a treatment
recommendation, and never presented as fact.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np

from app.oncotwin.engine.series import build_series
from app.oncotwin.engine.simulate import DISPLAY_SIGNALS
from app.oncotwin.records import PatientRecord
from app.oncotwin.service import compute_twin
from app.oncotwin.signals import SIGNALS

DISCLAIMER = "Simulation — not a clinical prediction or treatment recommendation."
INTERVENTION_KINDS = ("antibiotic", "hydration", "gcsf_dose", "careplan", "clinician_note")


def _interventions(record: PatientRecord, lo: int, hi: int) -> list[dict[str, Any]]:
    out = []
    for e in record.events:
        if not (lo < e.day <= hi):
            continue
        if e.kind == "gcsf_dose" and e.detail.get("indication") == "prophylaxis":
            continue
        if e.kind in INTERVENTION_KINDS or (e.kind == "encounter" and not e.detail.get("qualifying")):
            out.append({"day": e.day, "kind": e.kind, "display": e.display, "id": e.id})
    return out


def _outcomes(record: PatientRecord, lo: int, hi: int) -> list[dict[str, Any]]:
    return [{"day": e.day, "display": e.display, "condition": e.detail.get("condition"), "id": e.id}
            for e in record.events if lo < e.day <= hi and e.kind == "encounter" and e.detail.get("qualifying")]


def synthetic_truth(script, anchor_day: int) -> dict[str, Any]:
    """Re-run the synthetic generator without clinician interventions after the anchor (validation only)."""
    from app.oncotwin.simulator.patients import simulate

    factual = simulate(script)
    cf_script = copy.deepcopy(script)
    removed = [(d, k) for d, k in cf_script.interventions if d > anchor_day]
    cf_script.interventions = [(d, k) for d, k in cf_script.interventions if d <= anchor_day]
    cf = simulate(cf_script) if removed else factual

    def first_after(sim):
        return next(({"day": o["day"], "condition": o["condition"]} for o in sim.truth.event_onsets if o["day"] > anchor_day), None)

    return {
        "available": True,
        "removed_interventions": [{"day": d, "kind": k} for d, k in removed],
        "factual_first_event_after_anchor": first_after(factual),
        "counterfactual_first_event_after_anchor": first_after(cf),
        "factual_peak_infection_load": round(float(max(factual.truth.infection[anchor_day:], default=0.0)), 3),
        "counterfactual_peak_infection_load": round(float(max(cf.truth.infection[anchor_day:], default=0.0)), 3),
        "note": ("Ground truth from the synthetic generator — available only because this patient is simulated; used to "
                 "validate the twin's counterfactual projection, never shown for real patients."),
    }


def counterfactual(record: PatientRecord, history: list[dict[str, Any]], anchor_day: int, live_day: int, model, *,
                   scenario: str = "current", custom: dict[str, Any] | None = None, script=None) -> dict[str, Any]:
    first_dose = min((e.day for e in record.events if e.kind == "chemo_dose"), default=1)
    anchor = int(max(first_dose + 1, min(anchor_day, live_day - 1)))
    comp = compute_twin(record, anchor, history=[h for h in history if h["day"] <= anchor], model=model,
                        simulate=[scenario] if custom is None else ["current"], custom_scenario=custom)
    key = "custom" if custom is not None else scenario
    sim = comp.simulation["scenarios"][key]
    days = [d for d in sim["days"] if d <= live_day]
    obs_hist = {h["day"]: h for h in history if anchor < h["day"] <= live_day}
    rows, inside = [], []
    for i, d in enumerate(days):
        h = obs_hist.get(d)
        med, p10, p90 = sim["risk"]["median"][i], sim["risk"]["p10"][i], sim["risk"]["p90"][i]
        ok = None if h is None or h["tier"] == "IN ACUTE CARE" else bool(p10 <= h["risk"] <= p90)
        if ok is not None:
            inside.append(ok)
        rows.append({"day": d, "observed_risk": None if h is None else h["risk"],
                     "observed_tier": None if h is None else h["tier"],
                     "simulated_median": med, "simulated_p10": p10, "simulated_p90": p90,
                     "simulated_event_probability_cumulative": sim["event_probability_cumulative"][i],
                     "observed_within_band": ok, "difference_median": None if h is None else round(h["risk"] - med, 4)})
    diverge = next((r for r in rows if r["observed_within_band"] is False), None)

    series = build_series(record, live_day)
    signals = {}
    for k in DISPLAY_SIGNALS:
        s = sim["signals"][k]
        signals[k] = {"label": SIGNALS[k].label, "unit": SIGNALS[k].unit_display, "days": days,
                      "observed": [None if np.isnan(series.values[k][d - 1]) else
                                   round(float(series.values[k][d - 1]), SIGNALS[k].decimals) for d in days],
                      "simulated_median": s["median"][: len(days)], "simulated_p10": s["p10"][: len(days)],
                      "simulated_p90": s["p90"][: len(days)]}
    iv = _interventions(record, anchor, live_day)
    out = _outcomes(record, anchor, live_day)
    sim_ev = sim["event_probability_cumulative"][len(days) - 1] if days else 0.0
    summary = (f"From Day {anchor}, the counterfactual twin ({sim['label'].lower()}) projected a {sim_ev:.0%} "
               f"probability of qualifying acute care by Day {days[-1] if days else anchor}. ")
    summary += (f"Observed: {out[0]['display']} on Day {out[0]['day']}. " if out else "Observed: no qualifying acute care. ")
    if iv:
        done = "; ".join(f"{x['display']} (Day {x['day']})" for x in iv[:3])
        summary += (f"Recorded after the anchor: {done}. Under the twin's model assumptions, the gap between the two "
                    "trajectories is associated with these actions.")
    return {
        "disclaimer": DISCLAIMER,
        "anchor_day": anchor, "live_day": live_day,
        "scenario": {"key": key, "label": sim["label"], "assumptions": sim["assumptions"], "config": sim.get("config")},
        "data_used": {"as_of_day": anchor, "inputs_until": f"Day {anchor}", "model": comp.prediction["model"],
                      "risk_at_anchor": comp.prediction["risk"], "tier_at_anchor": comp.prediction["tier"]},
        "days": rows, "signals": signals,
        "anc": {"observed": [{"day": d, "value": v} for d, v, _ in series.labs.get("anc", []) if anchor < d <= live_day],
                "simulated": {k: v[: len(days)] for k, v in sim["anc"].items()}},
        "observed_interventions": iv, "observed_outcomes": out,
        "band_coverage": None if not inside else round(sum(inside) / len(inside), 3),
        "first_divergence": diverge, "summary": summary,
        "synthetic_truth": (synthetic_truth(script, anchor) if script is not None else
                            {"available": False, "note": "No generator script (real or ingested patient)."}),
    }
