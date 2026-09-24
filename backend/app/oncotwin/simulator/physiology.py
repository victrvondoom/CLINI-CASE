"""Mechanistic core shared by the synthetic simulator AND the twin.

Two pieces:

1. Neutrophil kinetics — the semi-mechanistic myelosuppression model of
   Friberg et al., J Clin Oncol 2002;20:4713-21: a proliferating
   compartment, three transit compartments and a circulating compartment,
   with a feedback term (Circ0/Circ)^gamma and a linear drug effect
   E = slope · exposure. G-CSF is modelled as a transient increase in
   proliferation and maturation rate.

2. Latent physiology — three unitless latent loads that drive the observable
   signals:
     infection   — infection / systemic inflammation load; grows when
                   neutrophils are low, cleared when they recover or when
                   antibiotics are given
     dehydration — GI toxicity / volume depletion load; driven by emesis and
                   diarrhea pulses after each dose, reduced by supportive-
                   medication adherence and hydration
     fatigue     — treatment-related deconditioning load

   The observation model maps latent loads to each signal (in the signal's
   transformed units, see signals.py) plus measurement noise.

IMPORTANT (honesty note): the synthetic cohort is generated with this same
model structure, so evaluating the twin on it is an "identical-twin
experiment" — model STRUCTURE is shared, patient PARAMETERS and latent
states are unknown to the twin and must be estimated from observations.
Real-world use requires validation of this structure on real cohorts.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LATENT = ("infection", "dehydration", "fatigue")

# Effect of +1 unit of each latent load on each signal (transformed units:
# log for hrv_sdnn / steps, linear otherwise). Columns follow LATENT.
LOADINGS: dict[str, tuple[float, float, float]] = {
    "resting_hr":    (8.0, 6.0, 3.0),
    "hrv_sdnn":      (-0.30, -0.20, -0.15),
    "temperature":   (1.15, 0.10, 0.0),
    "spo2":          (-0.9, 0.0, 0.0),
    "steps":         (-0.55, -0.35, -0.45),
    "sleep_hours":   (-0.55, -0.35, -0.25),
    "weight":        (0.0, -1.4, 0.0),
    "sbp":           (-6.0, -7.0, 0.0),
    "symptom_score": (2.2, 2.0, 1.2),
    "dbp":           (-4.0, -4.0, 0.0),
    "glucose_cgm":   (10.0, 6.0, 0.0),
}

# Day-to-day biological + measurement noise, transformed units.
OBS_NOISE: dict[str, float] = {
    "resting_hr": 1.8, "hrv_sdnn": 0.10, "temperature": 0.13, "spo2": 0.5,
    "steps": 0.22, "sleep_hours": 0.5, "weight": 0.3, "sbp": 5.0,
    "symptom_score": 0.6, "dbp": 4.0, "glucose_cgm": 7.0,
}

# A qualifying acute-care event occurs when a latent load crosses these.
EVENT_THRESHOLDS = {"infection": 1.5, "dehydration": 1.6}

# Population neutrophil-model parameters (days). MTT/gamma are held at
# population values; the patient-specific drug sensitivity (`slope`) is fitted.
FRIBERG_MTT_DAYS = 4.5       # ≈108 h, within the published docetaxel/paclitaxel range
FRIBERG_GAMMA = 0.17
EXPOSURE_KEL_PER_DAY = 0.5   # effective myelotoxic exposure half-life ≈ 1.4 d
SLOPE_PER_MYELOTOX = 1.6     # slope = regimen.myelotox × patient sensitivity × this
GCSF_ACTIVE_DAYS = 10
# G-CSF: self-limiting proliferation stimulus (only while ANC is below twice
# its baseline) plus faster maturation. Keeps the model bounded.
GCSF_STIM = 3.0
GCSF_KTR_MULT = 1.4

EMETO_PULSE = (0.9, 1.0, 0.8, 0.5, 0.25)                  # days 0..4 after dose
FATIGUE_PULSE = (0.6, 1.0, 1.0, 0.8, 0.6, 0.4, 0.2)       # days 0..6 after dose
IV_DIARRHEA_PULSE = {3: 0.4, 4: 0.5, 5: 0.5, 6: 0.4, 7: 0.25}


# New-infection seeding: neutropenia-driven hazard (per-patient rate × nf) plus
# a small background hazard. Most pathogens are cleared by a normal neutrophil
# count; about one seed in five is virulent enough to progress even without
# neutropenia (community-acquired pneumonia / sepsis are OP-35 events too).
BACKGROUND_INFECTION_HAZARD = 0.003


def seed_virulence(u: np.ndarray | float) -> np.ndarray:
    """Map a uniform draw to a pathogen virulence (shared by simulator and twin)."""
    u = np.asarray(u, dtype=float)
    return np.where(u < 0.5, 0.0, np.where(u < 0.8, 0.1 + 1.15 * (u - 0.5), 0.7 + 1.5 * (u - 0.8)))


def sigmoid(x: np.ndarray | float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def neutropenia_factor(anc: np.ndarray | float) -> np.ndarray:
    """0 (normal ANC) → 1 (profound neutropenia). ANC in 10^3/µL."""
    return sigmoid((1.0 - np.asarray(anc, dtype=float)) / 0.18)


# =============================================================================
# Friberg neutrophil model (vectorised over a batch of parameter draws)
# =============================================================================


@dataclass
class FribergState:
    prol: np.ndarray
    t1: np.ndarray
    t2: np.ndarray
    t3: np.ndarray
    circ: np.ndarray
    exposure: np.ndarray

    @classmethod
    def steady(cls, circ0: np.ndarray) -> FribergState:
        c = np.asarray(circ0, dtype=float).copy()
        return cls(c.copy(), c.copy(), c.copy(), c.copy(), c.copy(), np.zeros_like(c))

    def copy(self) -> FribergState:
        return FribergState(*(np.array(getattr(self, f), copy=True) for f in
                              ("prol", "t1", "t2", "t3", "circ", "exposure")))


def friberg_advance_day(
    st: FribergState,
    circ0: np.ndarray,
    slope: np.ndarray,
    *,
    dose_scale: np.ndarray | float = 0.0,
    gcsf_active: np.ndarray | bool = False,
    mtt: float = FRIBERG_MTT_DAYS,
    gamma: float = FRIBERG_GAMMA,
    substeps: int = 8,
) -> FribergState:
    """Advance the neutrophil model by one day (explicit Euler, `substeps`).

    A dose (relative exposure `dose_scale`) is applied at the start of the day.
    Returns the new state; `st.circ` before the call is the morning ANC.
    """
    st = st.copy()
    st.exposure = st.exposure + np.asarray(dose_scale, dtype=float)
    gcsf = np.asarray(gcsf_active, dtype=bool)
    ktr_base = 4.0 / mtt
    ktr = np.where(gcsf, ktr_base * GCSF_KTR_MULT, ktr_base)
    dt = 1.0 / substeps
    decay = np.exp(-EXPOSURE_KEL_PER_DAY * dt)
    for _ in range(substeps):
        edrug = np.clip(slope * st.exposure, 0.0, 0.99)
        feedback = np.power(np.clip(circ0 / np.maximum(st.circ, 1e-3), 0.0, 50.0), gamma)
        # Stimulus fades as either the proliferating pool or the circulating
        # count approaches 2× baseline (the transit delay would otherwise let
        # the proliferating pool run away before the feedback sees it).
        stim = np.clip(1.0 - np.maximum(st.prol, st.circ) / (2.0 * circ0), 0.0, 1.0)
        prolif = np.where(gcsf, 1.0 + GCSF_STIM * stim, 1.0)
        d_prol = ktr_base * st.prol * (1.0 - edrug) * feedback * prolif - ktr * st.prol
        d_t1 = ktr * st.prol - ktr * st.t1
        d_t2 = ktr * (st.t1 - st.t2)
        d_t3 = ktr * (st.t2 - st.t3)
        d_circ = ktr * st.t3 - ktr_base * st.circ
        st.prol = np.maximum(st.prol + dt * d_prol, 1e-4)
        st.t1 = np.maximum(st.t1 + dt * d_t1, 1e-4)
        st.t2 = np.maximum(st.t2 + dt * d_t2, 1e-4)
        st.t3 = np.maximum(st.t3 + dt * d_t3, 1e-4)
        st.circ = np.maximum(st.circ + dt * d_circ, 1e-3)
        st.exposure = st.exposure * decay
    return st


def simulate_anc(
    circ0: np.ndarray,
    slope: np.ndarray,
    n_days: int,
    doses: dict[int, float],
    gcsf_days: set[int] | list[int],
    *,
    start_day: int = 1,
    state: FribergState | None = None,
) -> tuple[np.ndarray, FribergState]:
    """Morning ANC for days start_day … start_day+n_days-1. Shape (B, n_days).

    `doses` maps 1-based day → relative dose scale (1.0 = full dose).
    `gcsf_days` are days a long-acting G-CSF was administered.
    """
    circ0 = np.atleast_1d(np.asarray(circ0, dtype=float))
    slope = np.broadcast_to(np.asarray(slope, dtype=float), circ0.shape)
    st = state.copy() if state is not None else FribergState.steady(circ0)
    out = np.empty((circ0.shape[0], n_days))
    for j in range(n_days):
        day = start_day + j
        out[:, j] = st.circ
        active = any(g < day <= g + GCSF_ACTIVE_DAYS for g in gcsf_days)
        st = friberg_advance_day(st, circ0, slope, dose_scale=doses.get(day, 0.0), gcsf_active=active)
    return out, st


# =============================================================================
# Latent physiology dynamics (vectorised over a batch of runs)
# =============================================================================


@dataclass
class DayDrivers:
    """Everything that drives the latent loads on one day (per run)."""
    days_since_dose: int | None       # None = no dose yet this course
    emeto: float                      # regimen emetogenic load
    diarrhea: float                   # regimen diarrhea load
    fatigue: float                    # regimen fatigue load
    oral_days: int
    adherence: np.ndarray | float     # supportive-medication adherence today (0..1)
    infection_seed: np.ndarray | float = 0.0
    virulence: np.ndarray | float = 0.0
    abx_boost: np.ndarray | float = 0.0
    hydration_boost: np.ndarray | float = 0.0
    activity_boost: np.ndarray | float = 0.0
    gi_insult: np.ndarray | float = 0.0   # acute GI illness (injected / exogenous)


def gi_pulses(days_since_dose: int | None, emeto: float, diarrhea: float, oral_days: int) -> tuple[float, float]:
    """(emesis pulse, diarrhea pulse) on a given day of the cycle."""
    if days_since_dose is None or days_since_dose < 0:
        return 0.0, 0.0
    k = days_since_dose
    em = emeto * (EMETO_PULSE[k] if k < len(EMETO_PULSE) else 0.0)
    if oral_days > 0:
        di = diarrhea * (min(1.0, max(0.0, (k - 3) / 5.0)) if k <= oral_days + 2 else 0.0)
    else:
        di = diarrhea * IV_DIARRHEA_PULSE.get(k, 0.0)
    return em, di


def fatigue_pulse(days_since_dose: int | None, fatigue: float) -> float:
    if days_since_dose is None or days_since_dose < 0:
        return 0.0
    k = days_since_dose
    return fatigue * (FATIGUE_PULSE[k] if k < len(FATIGUE_PULSE) else 0.0)


def latent_step(
    infection: np.ndarray,
    dehydration: np.ndarray,
    fatigue: np.ndarray,
    anc: np.ndarray,
    drv: DayDrivers,
    *,
    infection_growth: np.ndarray | float = 0.60,
    gi_sensitivity: np.ndarray | float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """One-day update of the three latent loads. Returns (I, D, F, emesis)."""
    nf = neutropenia_factor(anc)
    growth = infection_growth * nf + np.asarray(drv.virulence, dtype=float)
    clear = 0.12 + 0.55 * (1.0 - nf) + np.asarray(drv.abx_boost, dtype=float)
    # Resolution is capped at 45 %/day: even with antibiotics an established
    # infection takes several days to settle.
    net = np.clip(growth - clear, -0.45, None)
    inf = infection + infection * net + np.asarray(drv.infection_seed, dtype=float)
    inf = np.clip(inf, 0.0, 4.0)

    em, di = gi_pulses(drv.days_since_dose, drv.emeto, drv.diarrhea, drv.oral_days)
    adh = np.clip(np.asarray(drv.adherence, dtype=float), 0.0, 1.0)
    emesis = em * (1.0 - 0.75 * adh) * gi_sensitivity + np.asarray(drv.gi_insult, dtype=float)
    diarrhea = di * (1.0 - 0.5 * adh) * gi_sensitivity
    # Rehydration is likewise capped (60 %/day) so recovery is gradual.
    recovery = np.clip(0.30 + np.asarray(drv.hydration_boost, dtype=float), 0.0, 0.6)
    deh = dehydration + 0.5 * (emesis + diarrhea) - recovery * dehydration
    deh = np.clip(deh, 0.0, 4.0)

    fat = (fatigue + 0.10 * fatigue_pulse(drv.days_since_dose, drv.fatigue)
           + 0.08 * infection + 0.05 * dehydration
           - 0.10 * (1.0 + np.asarray(drv.activity_boost, dtype=float)) * fatigue)
    fat = np.clip(fat, 0.0, 4.0)
    return inf, deh, fat, emesis


def observation_means(
    baseline: dict[str, float],
    infection: np.ndarray,
    dehydration: np.ndarray,
    fatigue: np.ndarray,
    *,
    emesis: np.ndarray | float = 0.0,
    steroid: np.ndarray | float = 0.0,
) -> dict[str, np.ndarray]:
    """Expected value of each signal in TRANSFORMED units given latent loads.

    `baseline` holds the patient's baseline in transformed units (log for
    hrv_sdnn / steps).
    """
    out: dict[str, np.ndarray] = {}
    for key, base in baseline.items():
        load = LOADINGS.get(key)
        if load is None:
            continue
        v = base + load[0] * infection + load[1] * dehydration + load[2] * fatigue
        if key == "symptom_score":
            v = v + 1.5 * np.asarray(emesis, dtype=float)
        if key == "glucose_cgm":
            v = v + 25.0 * np.asarray(steroid, dtype=float)
        out[key] = np.asarray(v, dtype=float)
    return out
