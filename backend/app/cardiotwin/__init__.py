"""CardioTwin — cardiovascular risk visualisation & vessel-level prediction.

An ADDITIVE ClinCase subsystem (mirrors OncoTwin's conventions: JSON model
artifact + SHA-256 integrity, bootstrap-ensemble uncertainty, exact linear
attribution). It does not modify any ClinCase or OncoTwin code path.

What it predicts (and what it does NOT):

  * P(angiographic CAD) and P(stenosis) for LAD, LCX and RCA, estimated from
    tabular demographic / clinical / ECG / laboratory / echo features
    (Extension of the Z-Alizadeh Sani dataset, n = 303, UCI id 411, CC BY 4.0).
  * It does NOT localise a lesion, size a plaque, read an image, or predict
    future events. The 3D view is a semantic display of model output.
"""

CARDIOTWIN_VERSION = "1.0.0"
