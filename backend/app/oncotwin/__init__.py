"""OncoTwin — a dynamic digital twin layer on top of ClinCase.

OncoTwin is an ADDITIVE extension. It does not modify the 7-agent ClinCase
LangGraph, its manifest, or any existing endpoint. It adds:

  • a continuously updated Patient State Vector per cancer patient
  • a personalized baseline engine (robust per-patient normal ranges)
  • a temporal ML engine predicting ONE precise outcome (see `outcome.py`)
  • a mechanistic twin core (Friberg neutrophil model + latent physiology)
    that powers what-if trajectory simulation
  • an explainable early-warning engine (NORMAL → WATCH → EARLY WARNING →
    HIGH PRIORITY) with a hash-chained prediction audit trail
  • a clinician-in-the-loop handoff into the EXISTING ClinCase case +
    7-agent prior-authorization pipeline

Everything in the demo cohort is SYNTHETIC and labelled as such. Model
metrics are computed on held-out synthetic patients, not clinical data.
"""

ONCOTWIN_VERSION = "1.0.0"
SYNTHETIC_TAG = {
    "system": "https://clincase.aerofyta.health/oncotwin/tags",
    "code": "SYNTHETIC",
    "display": "Synthetic demonstration data — not a real patient",
}
