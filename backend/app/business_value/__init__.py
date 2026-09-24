"""Business value instrumentation — turn agent outputs into payer KPIs.

Three sources of business value an ClinCase deployment delivers, each
quantified in $$ a sales team can defend:

  1. Direct PA-cost displacement
       Industry baseline (CAQH, AMA): $35B/year US PA admin spend; ~$1,500
       per PA fully loaded (clinician + staff time + appeals).
       ClinCase per-case: $0.45 (DENY+appeal), $0.25 (clean APPROVE).
       Savings: $1,499.55–$1,499.75 per case.

  2. Star Ratings revenue lift
       0.5 stars ≈ $2.1M / 10K MA members / year (Lilac Software 2025).
       At Humana scale (6M MA enrollees) = $1.26B / half-star.
       ClinCase's 7-day SLA hit + specific-reason denials feed the
       transparency metrics that the new MIPS "Electronic Prior Auth"
       measure (CY 2027) and the underlying Star measures index.

  3. Provider abrasion / network adequacy
       Physician turnover cost: $250K–$1.2M (AMN, SimpliMD).
       89–95% of physicians say PA contributes to burnout (AMA 2025).
       ClinCase's 2-minute-decision profile vs days/weeks reduces
       PA-induced abrasion; we score this per provider and aggregate.

Modules:
  roi.py             — per-case ROI; org rollups
  star_ratings.py    — projected Star measure / revenue impact at the org
  provider_abrasion.py — provider-level abrasion score from PA timing
"""
from app.business_value.provider_abrasion import provider_abrasion_score
from app.business_value.roi import case_roi, org_value_rollup
from app.business_value.star_ratings import (
    projected_star_impact,
    star_revenue_estimate,
)

__all__ = [
    "case_roi",
    "org_value_rollup",
    "projected_star_impact",
    "star_revenue_estimate",
    "provider_abrasion_score",
]
