"""Risk-Trajectory Simulator — what-if scenarios on the personalised twin.

For each scenario the twin is rolled forward day by day from TODAY'S
estimated state:

  • neutrophils   — Friberg model with the patient's posterior drug
                    sensitivity (sampled), observed dose history, planned
                    CarePlan doses, and scenario-specific G-CSF / dose changes
  • latent loads  — infection / dehydration / fatigue dynamics (physiology.py)
                    starting from today's estimated loads, with uncertain
                    pathogen virulence and possible NEW infections
  • observations  — expected signals from the observation model plus noise
                    scaled by the patient's OWN baseline variability
  • risk          — the SAME deterioration model applied to the simulated
                    history + future, day by day

Scenarios share common random numbers (same parameter draws and noise), so
differences between them reflect the scenario, not Monte Carlo noise.

These are decision-support SIMULATIONS under stated assumptions — not
predictions of what will happen, and never treatment recommendations.
"""
from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline
from app.oncotwin.engine.features import feature_tensor, nadir_risk, signal_matrix
from app.oncotwin.engine.neutrophil import NeutrophilFit
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P

HORIZON_DAYS = 10
N_RUNS = 64
DISPLAY_SIGNALS = ("temperature", "resting_hr", "hrv_sdnn", "steps", "weight", "sbp", "symptom_score")

SCENARIOS: dict[str, dict[str, Any]] = {
    "current": {
        "label": "Current trajectory",
        "description": "Current treatment plan and the patient's observed 7-day behaviour; no new clinical action.",
        "assumptions": ["Planned CarePlan doses given on schedule at current dose",
                        "Supportive-medication adherence continues at the observed 7-day level",
                        "No new clinical intervention"],
    },
    "early_intervention": {
        "label": "Early intervention (within 24 h)",
        "description": "Clinician review tomorrow leading to early management: empiric oral antibiotics, "
                       "G-CSF if the twin projects ANC < 1.0, IV hydration if volume depletion is estimated, "
                       "and an adherence call.",
        "assumptions": ["Antibiotic effect modelled as increased infection clearance for 7 days",
                        "G-CSF given tomorrow only when twin-estimated ANC < 1.0 ×10³/µL",
                        "IV fluids on 2 days only when dehydration load > 0.3",
                        "Adherence raised to ≥ 95 %"],
    },
    "improved_recovery": {
        "label": "Improved recovery / activity",
        "description": "Structured activity programme plus oral hydration coaching.",
        "assumptions": ["Faster fatigue recovery (activity boost)", "Modest daily hydration support"],
    },
    "reduced_adherence": {
        "label": "Reduced medication adherence",
        "description": "Supportive-medication adherence falls to 40 % of the currently observed level.",
        "assumptions": ["Antiemetic / antidiarrheal protection falls proportionally"],
    },
    "regimen_change": {
        "label": "Regimen change: 80 % dose + G-CSF",
        "description": "Next planned cycle given at 80 % dose with pegfilgrastim secondary prophylaxis.",
        "assumptions": ["Applies only to doses falling inside the horizon — effects on a later cycle's nadir "
                        "may lie beyond it"],
    },
}


@dataclass(frozen=True)
class ScenarioConfig:
    """Declarative scenario definition. Every predefined scenario is one of these,
    so a custom (clinician-built) what-if runs through exactly the same code."""
    dose_scale: float = 1.0                  # scale of planned doses inside the horizon
    gcsf_with_future_doses: bool | None = None   # None → follow the care plan
    adherence_mode: str = "observed"         # observed | factor | at_least | level
    adherence_value: float = 1.0
    gcsf_now: str = "no"                     # no | if_needed (twin ANC < 1.0 or nadir) | yes — given tomorrow
    abx_days: tuple[int, ...] = ()           # day offsets (1 = tomorrow) with empiric antibiotic effect
    hydration_days: tuple[int, ...] = ()     # day offsets with IV hydration
    hydration_if_needed: bool = False        # IV hydration only if the estimated dehydration load > 0.3
    oral_hydration: float = 0.0              # daily background hydration support
    activity: float = 0.0                    # structured-activity effect on fatigue recovery
    delay_next_dose_days: int = 0
    new_infection: bool = False              # stress what-if: a new infection seeded tomorrow


PREDEFINED: dict[str, ScenarioConfig] = {
    "current": ScenarioConfig(),
    "early_intervention": ScenarioConfig(adherence_mode="at_least", adherence_value=0.95, gcsf_now="if_needed",
                                         abx_days=tuple(range(1, 8)), hydration_days=(1, 2), hydration_if_needed=True),
    "improved_recovery": ScenarioConfig(oral_hydration=0.25, activity=0.8),
    "reduced_adherence": ScenarioConfig(adherence_mode="factor", adherence_value=0.4),
    "regimen_change": ScenarioConfig(dose_scale=0.8, gcsf_with_future_doses=True),
}


def custom_scenario(params: dict[str, Any]) -> tuple[ScenarioConfig, dict[str, Any]]:
    """Validate clinician-entered what-if parameters → (config, descriptive metadata)."""
    adh = params.get("adherence")
    abx_start = params.get("antibiotics_start_day_offset")
    abx_len = int(params.get("antibiotics_days") or 7)
    hyd = tuple(sorted({int(d) for d in (params.get("iv_hydration_day_offsets") or []) if 1 <= int(d) <= HORIZON_DAYS}))
    cfg = ScenarioConfig(
        dose_scale=float(np.clip(params.get("next_dose_scale", 1.0), 0.5, 1.0)),
        gcsf_with_future_doses=params.get("gcsf_with_next_cycle"),
        adherence_mode="observed" if adh is None else "level",
        adherence_value=1.0 if adh is None else float(np.clip(adh, 0.0, 1.0)),
        gcsf_now="yes" if params.get("gcsf_tomorrow") else "no",
        abx_days=() if abx_start is None else tuple(range(int(abx_start), int(abx_start) + max(1, min(abx_len, 14)))),
        hydration_days=hyd,
        oral_hydration=0.25 if params.get("oral_hydration_coaching") else 0.0,
        activity=0.8 if params.get("activity_program") else 0.0,
        delay_next_dose_days=int(np.clip(params.get("delay_next_dose_days", 0), 0, 7)),
        new_infection=bool(params.get("new_infection", False)),
    )
    a = []
    a.append("Adherence continues at the observed 7-day level" if adh is None else f"Supportive-medication adherence {cfg.adherence_value:.0%}")
    if cfg.gcsf_now == "yes":
        a.append("G-CSF given tomorrow")
    if cfg.abx_days:
        a.append(f"Empiric antibiotic effect from day +{cfg.abx_days[0]} for {len(cfg.abx_days)} days (increased infection clearance)")
    if cfg.hydration_days:
        a.append(f"IV hydration on day(s) +{', +'.join(map(str, cfg.hydration_days))}")
    if cfg.oral_hydration:
        a.append("Daily oral hydration coaching (modest effect)")
    if cfg.activity:
        a.append("Structured activity programme (faster fatigue recovery)")
    if cfg.dose_scale < 1.0:
        a.append(f"Planned doses inside the horizon at {cfg.dose_scale:.0%}")
    if cfg.delay_next_dose_days:
        a.append(f"Planned doses delayed by {cfg.delay_next_dose_days} day(s)")
    if cfg.gcsf_with_future_doses:
        a.append("Pegfilgrastim with each planned dose")
    if cfg.new_infection:
        a.append("A new infection is seeded tomorrow (stress what-if)")
    return cfg, {"label": params.get("label") or "Custom scenario",
                 "description": "Clinician-configured what-if scenario.", "assumptions": a,
                 "parameters": {k: v for k, v in params.items() if k != "label"}}


def _seed_for(patient_id: str) -> int:
    return zlib.crc32(patient_id.encode())


def simulate_scenarios(
    series: PatientSeries,
    baseline: Baseline,
    fit: NeutrophilFit,
    latent_now: np.ndarray,
    history_ctx: dict[str, Any],
    model,
    *,
    scenarios: list[str] | None = None,
    custom: dict[str, Any] | None = None,
    horizon: int = HORIZON_DAYS,
    n_runs: int = N_RUNS,
) -> dict[str, Any]:
    t = series.as_of_day
    T = t + horizon
    keys = list(scenarios or SCENARIOS)
    configs: dict[str, ScenarioConfig] = {k: PREDEFINED[k] for k in keys}
    meta: dict[str, dict[str, Any]] = {k: SCENARIOS[k] for k in keys}
    if custom is not None:
        cfg_c, meta_c = custom_scenario(custom)
        if "current" not in keys:
            keys.insert(0, "current")
            configs["current"], meta["current"] = PREDEFINED["current"], SCENARIOS["current"]
        keys.append("custom")
        configs["custom"], meta["custom"] = cfg_c, meta_c
    reg = series.regimen
    M = n_runs
    rng = np.random.default_rng([_seed_for(series.profile.patient_id), t, 29])

    # ---- common random numbers (shared by every scenario) -----------------
    slopes = fit.sample_slopes(rng, M) if fit.labs_used else fit.base_slope * np.exp(rng.normal(0.1, 0.35, M))
    lat_noise = np.exp(rng.normal(0.0, 0.25, size=(M, 3)))
    virulence = np.where(latent_now[0] > 0.08, rng.uniform(0.0, 0.35, M), 0.0)
    growth = np.clip(rng.normal(0.60, 0.06, M), 0.4, 0.8)
    gi_sens = np.exp(rng.normal(0.0, 0.25, M))
    u_seed = rng.uniform(size=(horizon, M, 3))
    u_adh = rng.uniform(size=(horizon, M, 2))
    z_obs = rng.normal(size=(horizon, M, len(MODEL_SIGNALS)))

    circ0 = np.full(M, fit.circ0)
    _, f_state = P.simulate_anc(circ0, slopes, t, dict(series.dose_days), series.gcsf_days)

    past_doses = sorted(series.dose_days)
    planned_future = [d for d in series.planned_dose_days
                      if t < d <= T and not any(abs(d - g) <= 3 for g in past_doses)]
    plan_gcsf = reg.myelo_tier == "high" or any(
        e.kind == "careplan" and e.detail.get("change") == "add_gcsf_secondary_prophylaxis" for e in series.events)
    adh_frac, adh_sched = history_ctx["adherence_7d"], history_ctx["adherence_sched"]
    a0 = float(adh_frac[-1]) if adh_sched[-1] > 0 else 0.95
    twin_anc_today = fit.estimate(t)["mean"] if fit.labs_used else 4.4
    in_nadir_now = float(history_ctx["nadir"][-1]) >= 0.25 * max(reg.myelotox, 1e-6)

    med = {k: baseline.signals[k].median_t for k in MODEL_SIGNALS}
    spread = np.array([baseline.signals[k].spread_t for k in MODEL_SIGNALS])
    hist_values = signal_matrix(series)                                    # (1, t, S)
    sched_last = (reg.oral_days + 2) if reg.oral_days else 4
    hist_taken = np.array([[series.adherence.get(d, (0, 0))[0] for d in range(1, t + 1)]], dtype=float)
    hist_sched = np.array([series.adherence.get(d, (0, 0))[1] for d in range(1, t + 1)], dtype=float)

    results: dict[str, Any] = {}
    for key in keys:
        sc = configs[key]
        cfg = meta[key]
        dose_scale = sc.dose_scale
        gcsf_after_dose = plan_gcsf if sc.gcsf_with_future_doses is None else sc.gcsf_with_future_doses
        adh_level = {"observed": a0, "factor": sc.adherence_value * a0, "at_least": max(a0, sc.adherence_value),
                     "level": sc.adherence_value}[sc.adherence_mode]
        gcsf_days = list(series.gcsf_days)
        if sc.gcsf_now == "yes" or (sc.gcsf_now == "if_needed" and (twin_anc_today < 1.0 or in_nadir_now)):
            gcsf_days.append(t + 1)
        doses = dict(series.dose_days)
        planned_here = [d + sc.delay_next_dose_days for d in planned_future if d + sc.delay_next_dose_days <= T]
        for d in planned_here:
            doses[d] = dose_scale
            if gcsf_after_dose:
                gcsf_days.append(d + 1)

        st = f_state.copy()
        inf = latent_now[0] * lat_noise[:, 0]
        deh = latent_now[1] * lat_noise[:, 1]
        fat = latent_now[2] * lat_noise[:, 2]
        vir = virulence.copy()
        event_day = np.full(M, -1)
        admitted_until = np.full(M, -1)
        last_dose = past_doses[-1] if past_doses else None
        anc_f = np.zeros((M, horizon))
        lat_f = np.zeros((M, horizon, 3))
        val_f = np.zeros((M, horizon, len(MODEL_SIGNALS)))
        adh_taken = np.zeros((M, horizon))
        adh_sch = np.zeros(horizon)
        dsd_f = np.full(horizon, np.nan)
        gcsf_flag = np.zeros(horizon)

        for j in range(horizon):
            day = t + 1 + j
            dose_today = doses.get(day, 0.0)
            if dose_today:
                last_dose = day
            dsd = (day - last_dose) if last_dose is not None else None
            dsd_f[j] = np.nan if dsd is None else dsd
            gcsf_flag[j] = 1.0 if (last_dose is not None and any(last_dose <= g <= day for g in gcsf_days)) else 0.0
            anc_m = st.circ.copy()
            anc_f[:, j] = anc_m
            active = any(g < day <= g + P.GCSF_ACTIVE_DAYS for g in gcsf_days)
            st = P.friberg_advance_day(st, circ0, slopes, dose_scale=dose_today, gcsf_active=active)

            if dsd is not None and 0 <= dsd <= sched_last:
                taken = (u_adh[j] < adh_level).sum(axis=1) / 2.0
                adh_sch[j] = 2
            else:
                taken = np.ones(M)
            adh_taken[:, j] = taken

            admitted = admitted_until >= day
            abx = np.where(admitted, 1.2, 0.0)
            hyd = np.where(admitted, 0.9, 0.0)
            act = sc.activity
            if (j + 1) in sc.abx_days:
                abx = np.maximum(abx, 0.8)
            if (j + 1) in sc.hydration_days and (not sc.hydration_if_needed or latent_now[1] > 0.3):
                hyd = np.maximum(hyd, 0.6)
            if sc.oral_hydration:
                hyd = np.maximum(hyd, sc.oral_hydration)
            vir = np.where(admitted, 0.0, vir)
            nf = P.neutropenia_factor(anc_m)
            new_inf = (u_seed[j, :, 0] < 0.08 * nf + P.BACKGROUND_INFECTION_HAZARD) & (inf < 0.05) & ~admitted
            seed = np.where(new_inf, 0.06 + 0.24 * u_seed[j, :, 1], 0.0)
            vir = np.where(new_inf, P.seed_virulence(u_seed[j, :, 2]), vir)
            if sc.new_infection and j == 0:
                seed = np.maximum(seed, 0.25)
                vir = np.maximum(vir, 0.35)

            drv = P.DayDrivers(days_since_dose=dsd, emeto=reg.emeto, diarrhea=reg.diarrhea, fatigue=reg.fatigue,
                               oral_days=reg.oral_days, adherence=taken, infection_seed=seed, virulence=vir,
                               abx_boost=abx, hydration_boost=hyd, activity_boost=act)
            inf, deh, fat, emesis = P.latent_step(inf, deh, fat, anc_m, drv, infection_growth=growth,
                                                  gi_sensitivity=gi_sens)
            lat_f[:, j] = np.stack([inf, deh, fat], axis=1)
            crossed = (event_day < 0) & ((inf >= P.EVENT_THRESHOLDS["infection"]) | (deh >= P.EVENT_THRESHOLDS["dehydration"]))
            event_day = np.where(crossed, day, event_day)
            admitted_until = np.where(crossed, day + 3, admitted_until)

            steroid = 1.0 if (reg.steroid_premed and dsd is not None and 0 <= dsd <= 2) else 0.0
            means = P.observation_means(med, inf, deh, fat, emesis=emesis, steroid=steroid)
            val_f[:, j] = np.stack([means[k] for k in MODEL_SIGNALS], axis=1) + z_obs[j] * spread

        # ---- risk on simulated futures (same model, same features) ----------
        values = np.concatenate([np.repeat(hist_values, M, axis=0), val_f], axis=1)        # (M, T, S)
        dsd_all = np.concatenate([series.days_since_dose(), dsd_f])
        gcsf_all = np.concatenate([series.gcsf_since_last_dose(), gcsf_flag])
        nadir = nadir_risk(dsd_all, reg.myelotox, gcsf_all)
        anc_log = np.concatenate([np.repeat(np.asarray(history_ctx["anc_twin_log"])[None, :], M, 0),
                                  np.log(np.maximum(anc_f, 1e-3))], axis=1)
        anc_low = np.concatenate([np.repeat(np.asarray(history_ctx["anc_twin_low"])[None, :], M, 0),
                                  (anc_f < 1.0).astype(float)], axis=1)
        lab_low = np.concatenate([np.asarray(history_ctx["anc_lab_low"]), np.zeros(horizon)])
        last_low = [d for d, v, _ in series.labs.get("anc", []) if v < 1.0]
        if last_low:
            lab_low[t: min(T, max(last_low) + 6)] = 1.0
        taken_all = np.concatenate([np.repeat(hist_taken, M, 0), adh_taken * adh_sch], axis=1)
        sched_all = np.concatenate([hist_sched, adh_sch])
        kernel = np.ones(7)
        sched7 = np.convolve(sched_all, kernel)[:T]
        taken7 = np.stack([np.convolve(row, kernel)[:T] for row in taken_all])
        adh7 = np.where(sched7 > 0, taken7 / np.maximum(sched7, 1e-9), 1.0)
        F = feature_tensor(values, baseline, nadir=nadir, anc_twin_log=anc_log, anc_twin_low=anc_low,
                           anc_lab_low=lab_low, adherence_7d=adh7, adherence_sched=sched7,
                           age65=1.0 if series.profile.age >= 65 else 0.0,
                           on_treatment=(~np.isnan(dsd_all)).astype(float), myelotox=reg.myelotox)
        risk = model.predict(F[:, t:, :].reshape(-1, F.shape[-1])).reshape(M, horizon)

        days = list(range(t + 1, T + 1))
        cum_event = [float(np.mean((event_day > 0) & (event_day <= d))) for d in days]
        ev7 = float(np.mean((event_day > t) & (event_day <= t + 7)))
        sig_out = {}
        for k in DISPLAY_SIGNALS:
            i = MODEL_SIGNALS.index(k)
            arr = val_f[:, :, i]
            if SIGNALS[k].transform == "log":
                arr = np.exp(arr)
            dec = SIGNALS[k].decimals
            sig_out[k] = {q: [round(float(x), dec) for x in np.percentile(arr, pct, axis=0)]
                          for q, pct in (("median", 50), ("p10", 10), ("p90", 90))}
        results[key] = {
            "key": key, **cfg,
            "days": days,
            "risk": {q: [round(float(x), 4) for x in np.percentile(risk, pct, axis=0)]
                     for q, pct in (("median", 50), ("p10", 10), ("p90", 90))},
            "event_probability_cumulative": [round(x, 3) for x in cum_event],
            "event_probability_7d": round(ev7, 3),
            "risk_day7_median": round(float(np.median(risk[:, min(6, horizon - 1)])), 4),
            "anc": {q: [round(float(x), 2) for x in np.percentile(anc_f, pct, axis=0)]
                    for q, pct in (("median", 50), ("p10", 10), ("p90", 90))},
            "latent": {name: [round(float(x), 3) for x in np.median(lat_f[:, :, i], axis=0)]
                       for i, name in enumerate(P.LATENT)},
            "signals": sig_out,
            "doses_in_horizon": {str(d): doses[d] for d in planned_here},
            "gcsf_in_horizon": sorted(g for g in gcsf_days if g > t),
            "config": asdict(sc),
        }

    if "current" in results:
        base = results["current"]
        for r in results.values():
            r["delta_vs_current"] = {
                "event_probability_7d": round(r["event_probability_7d"] - base["event_probability_7d"], 3),
                "risk_day7_median": round(r["risk_day7_median"] - base["risk_day7_median"], 4),
                "risk_median_by_day": [round(a - b, 4) for a, b in zip(r["risk"]["median"], base["risk"]["median"], strict=True)],
                "event_probability_cumulative_by_day": [round(a - b, 3) for a, b in zip(
                    r["event_probability_cumulative"], base["event_probability_cumulative"], strict=True)],
            }
    return {
        "as_of_day": t,
        "horizon_days": horizon,
        "n_runs": M,
        "disclaimer": ("Decision-support simulation under the stated assumptions — not a guaranteed outcome "
                       "and not a treatment recommendation. Clinical judgement governs every decision."),
        "method": ("Monte Carlo forward simulation of the personalised twin (Friberg neutrophil model with the "
                   "patient's posterior drug sensitivity + latent infection/dehydration/fatigue dynamics); "
                   "risk = the deployed deterioration model applied to each simulated future; common random "
                   "numbers across scenarios."),
        "initial_state": {name: round(float(latent_now[i]), 3) for i, name in enumerate(P.LATENT)},
        "scenarios": results,
    }
