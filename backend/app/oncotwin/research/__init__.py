"""Twin Research Lab — reproducible experiments on the synthetic cohort.

  dataset.py     the cohort dataset (same seed + patient split as the deployed
                 OT-ACUTE-7 model), cached locally so experiments are fast
  lab.py         configurable experiments: feature groups × horizon × baseline
                 (personal vs population) → AUROC / AUPRC / Brier / calibration
                 / precision / recall / F1 / false-alert rate / lead time,
                 with patient-level bootstrap confidence intervals
  benchmark.py   the standard studies (modality benchmark, ablation,
                 personalisation, lead time, change-point detection,
                 neutrophil-twin and latent-state validation) → a committed,
                 reproducible results artifact

Every number is computed on SYNTHETIC patients and says so.
"""
