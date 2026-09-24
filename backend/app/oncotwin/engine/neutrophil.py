"""Neutrophil twin — personalised Friberg model fitted to the patient's own labs.

The population Friberg structure (physiology.py) is personalised in two ways:
  • Circ0 (baseline ANC) = the patient's pre-treatment ANC;
  • the drug-sensitivity parameter `slope` gets a grid posterior:
      prior   log(slope) ~ N(log(regimen slope × 1.1), 0.35²)
      likelihood  log(ANC_lab) ~ N(log(ANC_model(slope, day)), 0.15²)
    using ONLY labs dated on or before the as-of day.

Because the model is causal (ANC on day t depends only on doses given on or
before t), grid trajectories can be simulated once for the observed dose
history and reused for every as-of day without look-ahead.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.simulator import physiology as P

SLOPE_REL_GRID = np.geomspace(0.3, 3.5, 41)
PRIOR_REL_CENTER = float(np.exp(0.1))
PRIOR_LOG_SD = 0.35
OBS_LOG_SD = 0.15
POPULATION_ANC = 4.4


@dataclass
class NeutrophilFit:
    circ0: float
    circ0_source: str
    base_slope: float
    slopes: np.ndarray            # (G,)
    posterior: np.ndarray         # (G,) weights, sums to 1
    labs_used: list[tuple[int, float, str]]
    traj: np.ndarray              # (G, n) morning ANC under the observed dose history
    as_of_day: int

    def estimate(self, day: int) -> dict[str, float]:
        """Posterior mean and 10–90 % interval of ANC on `day` (≤ as_of)."""
        if not self.labs_used or day < self.labs_used[0][0]:
            return {"mean": POPULATION_ANC, "p10": 2.0, "p90": 7.5, "source": "population prior"}
        vals = np.log(self.traj[:, day - 1])
        mean = float(np.exp(np.sum(self.posterior * vals)))
        return {"mean": mean, "p10": float(np.exp(_wq(vals, self.posterior, 0.1))),
                "p90": float(np.exp(_wq(vals, self.posterior, 0.9))), "source": "fitted twin"}

    def predictive(self, day: int, q: tuple[float, float] = (0.1, 0.9)) -> dict[str, float]:
        """Interval for a NEW LAB MEASUREMENT on `day`: the posterior mixture over drug
        sensitivity convolved with the likelihood's lab noise (log-SD OBS_LOG_SD).
        `estimate()` describes the true ANC and is narrower — comparing a measured
        lab against it would under-cover (measured on the synthetic cohort)."""
        if not self.labs_used or day < self.labs_used[0][0]:
            return {"p_lo": 1.0, "p_hi": 9.0, "source": "population prior"}
        mu = np.log(np.maximum(self.traj[:, day - 1], 1e-3))
        xs = np.linspace(mu.min() - 4 * OBS_LOG_SD, mu.max() + 4 * OBS_LOG_SD, 600)
        cdf = (self.posterior[None, :] * _norm_cdf((xs[:, None] - mu[None, :]) / OBS_LOG_SD)).sum(axis=1)
        lo, hi = np.interp(q[0], cdf, xs), np.interp(q[1], cdf, xs)
        return {"p_lo": float(np.exp(lo)), "p_hi": float(np.exp(hi)), "source": "fitted twin predictive (incl. lab noise)"}

    def prob_below(self, day: int, threshold: float) -> float:
        if not self.labs_used or day < self.labs_used[0][0]:
            return 0.0
        return float(np.sum(self.posterior * (self.traj[:, day - 1] < threshold)))

    def sample_slopes(self, rng: np.random.Generator, n: int) -> np.ndarray:
        idx = rng.choice(len(self.slopes), size=n, p=self.posterior)
        jitter = np.exp(rng.normal(0.0, 0.04, size=n))
        return self.slopes[idx] * jitter

    def sensitivity_summary(self) -> dict[str, float]:
        rel = self.slopes / self.base_slope
        return {
            "relative_sensitivity_mean": float(np.sum(self.posterior * rel)),
            "relative_sensitivity_p10": float(_wq(rel, self.posterior, 0.1)),
            "relative_sensitivity_p90": float(_wq(rel, self.posterior, 0.9)),
        }


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF (Abramowitz & Stegun 7.1.26 erf approximation, |error| < 1.5e-7)."""
    z = np.abs(x) / np.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * z)
    erf = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-z * z)
    return 0.5 * (1.0 + np.sign(x) * erf)


def _wq(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    cw = np.cumsum(weights[order])
    return float(values[order][min(len(values) - 1, int(np.searchsorted(cw, q)))])


class NeutrophilTwin:
    """Grid trajectories for one patient's observed dose history; fit per as-of day."""

    def __init__(self, series: PatientSeries):
        self.series = series
        reg = series.regimen
        self.base_slope = max(reg.myelotox, 0.01) * P.SLOPE_PER_MYELOTOX
        first = series.first_dose_day
        anc_labs = series.labs.get("anc", [])
        pre = [v for d, v, _ in anc_labs if first is None or d < first]
        if pre:
            self.circ0, self.circ0_source = float(np.mean(pre)), "pre-treatment ANC"
        else:
            self.circ0, self.circ0_source = POPULATION_ANC, "population default"
        self.slopes = self.base_slope * SLOPE_REL_GRID
        G = len(self.slopes)
        self.traj, _ = P.simulate_anc(
            np.full(G, self.circ0), self.slopes, series.n,
            {d: s for d, s in series.dose_days.items()}, series.gcsf_days,
        )
        log_prior = -0.5 * ((np.log(SLOPE_REL_GRID) - np.log(PRIOR_REL_CENTER)) / PRIOR_LOG_SD) ** 2
        self.log_prior = log_prior - np.max(log_prior)
        self._fits: dict[int, NeutrophilFit] = {}

    def fit(self, as_of_day: int | None = None) -> NeutrophilFit:
        as_of = self.series.n if as_of_day is None else min(as_of_day, self.series.n)
        labs = [lab for lab in self.series.labs.get("anc", []) if lab[0] <= as_of]
        key = len(labs)
        if key in self._fits:
            f = self._fits[key]
            return NeutrophilFit(**{**f.__dict__, "as_of_day": as_of})
        loglik = self.log_prior.copy()
        for d, v, _ in labs:
            model = np.log(np.maximum(self.traj[:, d - 1], 1e-3))
            loglik += -0.5 * ((np.log(max(v, 1e-3)) - model) / OBS_LOG_SD) ** 2
        w = np.exp(loglik - np.max(loglik))
        w /= w.sum()
        fit = NeutrophilFit(self.circ0, self.circ0_source, self.base_slope, self.slopes, w, labs,
                            self.traj, as_of)
        self._fits[key] = fit
        return fit

    def daily_features(self) -> tuple[np.ndarray, np.ndarray]:
        """(log ANC estimate, P(ANC<1.0)) for every day, each using only labs ≤ that day."""
        n = self.series.n
        log_anc = np.full(n, np.log(POPULATION_ANC))
        p_low = np.zeros(n)
        for day in range(1, n + 1):
            f = self.fit(day)
            est = f.estimate(day)
            log_anc[day - 1] = np.log(est["mean"])
            p_low[day - 1] = f.prob_below(day, 1.0)
        return log_anc, p_low
