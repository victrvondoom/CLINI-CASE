"""Multimodal longitudinal timeline.

One chronologically ordered list that interleaves every modality with the
twin's own state changes, so a clinician can read — day by day — which data
arrived and how the twin's assessment moved in response. Every item carries
its provenance (FHIR resourceType/id or ledger entry).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline, adverse_z
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.records import PatientRecord, day_to_iso
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

LANE = {
    "diagnosis": "ehr", "pathology": "pathology", "genomics": "genomics", "imaging": "ehr",
    "careplan": "treatment", "medication_request": "treatment", "chemo_dose": "treatment",
    "gcsf_dose": "treatment", "antibiotic": "treatment", "hydration": "treatment",
    "supportive_dose": "adherence", "encounter": "ehr", "procedure": "ehr",
    "performance_status": "ehr", "clinician_note": "hitl",
}


def build_timeline(
    record: PatientRecord,
    series: PatientSeries,
    baseline: Baseline,
    history: list[dict[str, Any]],
    *,
    hitl_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    t = series.as_of_day
    items: list[dict[str, Any]] = []

    # --- EHR / treatment events (supportive doses aggregated per day) ------
    adherence_days: dict[int, list] = {}
    for e in record.events_until(t):
        if e.kind == "supportive_dose":
            adherence_days.setdefault(e.day, []).append(e)
            continue
        sev = "high" if (e.kind == "encounter" and e.detail.get("qualifying")) else "info"
        items.append({"day": e.day, "time": e.effective, "lane": LANE.get(e.kind, "ehr"), "title": e.display,
                      "detail": {k: v for k, v in e.detail.items() if k != "biomarkers"} or None,
                      "severity": sev, "fhir": {"resourceType": e.fhir_type, "id": e.id}, "source": "EHR"})
    for day, doses in adherence_days.items():
        taken = sum(1 for d in doses if d.detail.get("status") == "completed")
        drug = doses[0].code["display"] if doses[0].code else "supportive medication"
        items.append({"day": day, "time": doses[-1].effective, "lane": "adherence",
                      "title": f"Supportive medication ({drug}): {taken}/{len(doses)} scheduled doses taken",
                      "detail": None, "severity": "warning" if taken < len(doses) else "info",
                      "fhir": {"resourceType": "MedicationAdministration", "id": doses[0].id},
                      "source": "smart dispenser / patient app"})

    # --- Labs (one entry per draw) ------------------------------------------
    by_day: dict[int, list[tuple[str, float, str]]] = {}
    for key, rows in series.labs.items():
        for d, v, oid in rows:
            by_day.setdefault(d, []).append((key, v, oid))
    for d, rows in sorted(by_day.items()):
        parts = [f"{SIGNALS[k].label} {v:g} {SIGNALS[k].unit_display}" for k, v, _ in sorted(rows)]
        anc = next((v for k, v, _ in rows if k == "anc"), None)
        items.append({"day": d, "time": day_to_iso(d, 7, 30), "lane": "labs", "title": "Laboratory results: " + "; ".join(parts),
                      "detail": None, "severity": "warning" if (anc is not None and anc < 1.0) else "info",
                      "fhir": {"resourceType": "Observation", "id": rows[0][2]}, "source": "EHR laboratory"})

    # --- Wearables / PRO: only days with a notable personal deviation -------
    vals = np.stack([series.transformed(k) for k in MODEL_SIGNALS], axis=-1)[None]
    z = adverse_z(vals, baseline)[0]
    for d in range(1, t + 1):
        notable = [(MODEL_SIGNALS[i], float(z[d - 1, i])) for i in range(len(MODEL_SIGNALS))
                   if not np.isnan(z[d - 1, i]) and z[d - 1, i] >= 2.0]
        if not notable:
            continue
        notable.sort(key=lambda kv: -kv[1])
        wear = [(k, zz) for k, zz in notable if SIGNALS[k].category != "patient_reported"]
        pro = [(k, zz) for k, zz in notable if SIGNALS[k].category == "patient_reported"]
        if wear:
            items.append({"day": d, "time": day_to_iso(d, 7), "lane": "wearables",
                          "title": "Personal-baseline deviation: " + ", ".join(f"{SIGNALS[k].label} {zz:+.1f} SD" for k, zz in wear[:4]),
                          "detail": None, "severity": "warning" if len(wear) >= 3 else "info",
                          "fhir": {"resourceType": "Observation", "id": series.obs_ids[wear[0][0]][d - 1]},
                          "source": "wearables / home devices"})
        for k, zz in pro:
            items.append({"day": d, "time": day_to_iso(d, 20), "lane": "symptoms",
                          "title": f"Patient-reported symptom burden {series.values[k][d - 1]:.1f}/10 ({zz:+.1f} SD vs baseline)",
                          "detail": None, "severity": "warning" if zz >= 3 else "info",
                          "fhir": {"resourceType": "Observation", "id": series.obs_ids[k][d - 1]}, "source": "patient app"})

    # --- Data quality (dated events; rolling gap/stale metrics live in the freshness panel)
    for f in series.flags:
        if f.kind in ("gap", "stale"):
            continue
        day = f.days[0] if f.days else t
        items.append({"day": day, "time": day_to_iso(day, 12), "lane": "quality", "title": f.message,
                      "detail": {"kind": f.kind, "signal": f.signal}, "severity": "warning",
                      "fhir": {"resourceType": "Observation", "id": f.observation_ids[0]} if f.observation_ids else None,
                      "source": "OncoTwin data-quality engine"})

    # --- Twin state changes (why the twin moved) ------------------------------
    prev = None
    for h in history:
        if h["day"] > t:
            break
        if prev is not None and h["tier"] != prev["tier"]:
            drivers = ", ".join(c["label"] for c in h["top_contributors"] if c["logit"] > 0) or "—"
            rules = "; ".join(r["text"] for r in h["rules"]) if h["rules"] else None
            items.append({"day": h["day"], "time": day_to_iso(h["day"], 23, 59), "lane": "twin",
                          "title": f"Twin state {prev['tier']} → {h['tier']} (7-day risk {prev['risk']:.1%} → {h['risk']:.1%})",
                          "detail": {"pattern": h["pattern"], "top_drivers": drivers, "rules": rules,
                                     "n_concordant": h["n_concordant"]},
                          "severity": "high" if h["tier"] in ("HIGH PRIORITY", "EARLY WARNING") else "info",
                          "fhir": None, "source": "OncoTwin (computed as-of that day)"})
        prev = h

    items.extend(hitl_items or [])
    items.sort(key=lambda i: (i["day"], i["time"] or ""))
    return items
