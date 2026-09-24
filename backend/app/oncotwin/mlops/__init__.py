"""OncoTwin MLOps — lineage, prediction logging, delayed ground truth and drift.

  versions.py     feature-set version and dataset version (content hashes)
  predictions.py  every committed prediction with model / feature / dataset
                  version, input hash and — once observable — its ground truth
  drift.py        feature / prediction / missing-data drift against the training
                  reference profile (PSI with a sample-size-aware threshold)
"""
