"""OncoTwin intelligence layer — analytic engines over the as-of patient view.

Every engine here is deterministic and reads only data dated on or before the
as-of day (the same no-look-ahead boundary as `engine/series.py`):

  state          Living Twin State: 19 structured dimensions per day + a
                 transition ledger (previous → new, reason, source, confidence)
  changepoint    Bayesian online change-point detection on the personal-baseline
                 deviation vector
  correlation    cross-signal engine: direction, magnitude, onset order
                 (temporal precedence), coupling vs baseline, model contribution
  trajectory     risk-trajectory dynamics (acceleration, reversal, recovery …)
  memory         Twin Memory: treatment-cycle response profiles, recovery
                 velocity, similarity of the current cycle to previous cycles
  consistency    trajectory-conflict detector + twin consistency engine
  uncertainty    decomposition (model / measurement / missing data) + distribution
                 shift; Twin Readiness
  explain        WHY NOW? / WHAT CHANGED?
  graph          Patient State Graph (facts vs model-derived associations)
  counterfactual custom what-if scenarios + observed-vs-counterfactual twin

Language rule for every engine: statistical relationships are described as
"associated with", "temporally preceded" or "contributed to the model
prediction" — never as causation.
"""
