"""Patient State Graph — the twin as typed nodes and typed edges, each with evidence.

Node groups (left → right in the UI): clinical (cancer, pathology, genomics),
treatment (regimen, chemotherapy, supportive medication), interventions,
dynamic signals (wearables, home devices, symptoms, labs), physiology (latent
loads, neutrophil twin), risk, outcomes, change points.

Edge kinds — the UI draws each differently and never mixes them:
  clinical     a relationship RECORDED in the EHR (e.g. cancer → treated with regimen)
  temporal     derived from timestamps only (e.g. dose on Day 14 preceded the
               HRV deviation on Day 21 by 7 days) — ordering, not causation
  data         provenance: which inputs a twin component is computed from
  model        a MODEL-DERIVED association (log-odds contribution to the risk
               estimate, or a statistical lead/lag between signals)
"""
from __future__ import annotations

from typing import Any

from app.oncotwin.engine.state import LATENT_LABELS
from app.oncotwin.records import PatientRecord
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P
from app.oncotwin.simulator.regimens import REGIMENS

EDGE_KINDS = {
    "clinical": "recorded clinical relationship (fact)",
    "temporal": "ordering derived from timestamps (fact; not causation)",
    "data": "data provenance (input to a twin component)",
    "model": "model-derived association (not a clinical fact, not causation)",
}
LOADING_MIN = 0.5    # draw signal → latent provenance edges only for material loadings (signal-noise units)


def build(record: PatientRecord, as_of_day: int, state: dict[str, Any], prediction: dict[str, Any],
          correlation: dict[str, Any], changepoints: dict[str, Any], memory: dict[str, Any],
          alerts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reg = REGIMENS[record.profile.regimen_code]
    dims = state["dimensions"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def node(nid, group, label, status, *, severity="normal", basis="fact", evidence=None, detail=None):
        nodes.append({"id": nid, "group": group, "label": label, "status": status, "severity": severity,
                      "basis": basis, "evidence": evidence or [], "detail": detail or {}})

    def edge(a, b, kind, label, *, weight=None, evidence=None):
        edges.append({"source": a, "target": b, "kind": kind, "label": label, "weight": weight, "evidence": evidence or []})

    node("cancer", "clinical", "Cancer", dims["cancer"]["status"], evidence=dims["cancer"]["sources"],
         detail=dims["cancer"]["fields"])
    node("pathology", "clinical", "Pathology", dims["pathology"]["status"], evidence=dims["pathology"]["sources"],
         detail=dims["pathology"]["fields"])
    edge("cancer", "pathology", "clinical", "characterised by")
    if dims["genomic"]["sources"]:
        node("genomics", "clinical", "Genomics", dims["genomic"]["status"], evidence=dims["genomic"]["sources"],
             detail=dims["genomic"]["fields"])
        edge("cancer", "genomics", "clinical", "molecular profile")
    node("treatment", "treatment", f"Regimen {reg.code}", dims["treatment"]["status"],
         severity=dims["treatment"]["severity"], evidence=dims["treatment"]["sources"], detail=dims["treatment"]["fields"])
    edge("cancer", "treatment", "clinical", "treated with")
    node("chemo", "treatment", "Chemotherapy", ", ".join(d.name for d in reg.drugs),
         evidence=dims["treatment"]["sources"][:1], detail={"last_dose_day": dims["treatment"]["fields"].get("last_dose_day")})
    edge("treatment", "chemo", "clinical", "administers")
    node("medication", "treatment", "Active medication", dims["medication"]["status"], evidence=dims["medication"]["sources"],
         detail=dims["medication"]["fields"])
    edge("treatment", "medication", "clinical", "includes")
    node("adherence", "treatment", "Adherence", dims["adherence"]["status"], severity=dims["adherence"]["severity"],
         evidence=dims["adherence"]["sources"], detail=dims["adherence"]["fields"])
    edge("medication", "adherence", "clinical", "taken as")
    for e in dims["intervention"]["fields"].get("recent", []):
        nid = f"iv_{e['id']}"
        node(nid, "intervention", e["display"][:48], f"Day {e['day']}", evidence=[{"type": "EHR", "ids": [e["id"]]}], detail=e)
        edge("treatment", nid, "clinical", "recorded intervention")

    sig_rows = {r["signal"]: r for r in correlation["signals"]}
    for k in MODEL_SIGNALS:
        r = sig_rows.get(k)
        spec = SIGNALS[k]
        group = {"wearable": "wearable", "home_device": "home", "patient_reported": "symptom"}[spec.category]
        status = ("no data" if not r or r["recent_3d_mean"] is None else
                  f"{r['direction']} {r['recent_3d_mean']} {spec.unit_display} (baseline {r['baseline_median']}; "
                  f"{r['z_adverse_3d']:+.1f} SD)")
        sev = "alert" if r and (r["z_adverse_3d"] or 0) >= 2.5 else "attention" if r and r["deviating_adversely"] else "normal"
        node(f"sig_{k}", group, spec.label, status, severity=sev, basis="computed",
             evidence=[{"type": "Observation", "code": f"{spec.code_system}|{spec.code}"}], detail=r or {})
    labs = dims["laboratory"]
    node("labs", "lab", "Laboratory", labs["status"], severity=labs["severity"], evidence=labs["sources"], detail=labs["fields"])

    for name, v in dims["physiological"]["fields"]["latent_loads"].items():
        node(f"lat_{name}", "physiology", LATENT_LABELS[name], f"{v['value']:.2f}",
             severity="alert" if v["value"] >= 0.8 else "attention" if v["value"] >= 0.3 else "normal", basis="model",
             detail={"value": v["value"], "event_threshold": P.EVENT_THRESHOLDS.get(name),
                     "method": "weighted NNLS inversion of the twin observation model"})
        j = P.LATENT.index(name)
        for k in MODEL_SIGNALS:
            w = P.LOADINGS[k][j] / P.OBS_NOISE[k]
            if abs(w) >= LOADING_MIN:
                edge(f"sig_{k}", f"lat_{name}", "data", "input to latent-state inversion", weight=round(w, 2))
    node("neutrophil_twin", "physiology", "Neutrophil twin (Friberg)", "fitted to this patient's ANC labs", basis="model",
         detail={"method": "Friberg semi-mechanistic model; drug sensitivity fitted per patient"})
    edge("labs", "neutrophil_twin", "data", "ANC results fitted")
    edge("chemo", "neutrophil_twin", "data", "dose history input")

    p = prediction
    node("risk", "risk", f"{p['outcome_id']} risk ({p['horizon_days']} d)", f"{p['tier']} · {p['risk']:.1%}",
         severity=dims["risk"]["severity"], basis="model",
         detail={"risk": p["risk"], "p10": p["risk_p10"], "p90": p["risk_p90"], "model": p["model"]})
    to_node = {**{k: f"sig_{k}" for k in MODEL_SIGNALS}, "neutrophil": "neutrophil_twin", "adherence": "adherence",
               "context": "treatment"}
    for c in p["contributors"]:
        src = to_node.get(c["group"])
        if src and abs(c["logit"]) >= 0.05:
            edge(src, "risk", "model", f"{c['logit']:+.2f} log-odds", weight=c["logit"],
                 evidence=[{"type": "model_contribution", "features": c["features"][:4]}])
    multi = next((c for c in p["contributors"] if c["group"] == "multi_signal"), None)
    if multi and abs(multi["logit"]) >= 0.05:
        node("multi_signal", "risk", "Multi-signal pattern", f"{correlation['n_deviating']} signals deviating", basis="computed",
             detail={"headline": correlation["headline"]})
        edge("multi_signal", "risk", "model", f"{multi['logit']:+.2f} log-odds", weight=multi["logit"])
        for k in correlation["deviating"]:
            edge(f"sig_{k}", "multi_signal", "data", "concordant deviation")
    for ll in correlation.get("lead_lag", []):
        edge(f"sig_{ll['leader']}", f"sig_{ll['follower']}", "model",
             f"associated {ll['lag_days']} d later (r = {ll['r']:.2f})", weight=ll["r"])

    last = dims["treatment"]["fields"].get("last_dose_day")
    for r in correlation["signals"]:
        if r["deviating_adversely"] and r["onset_day"] and last and r["onset_day"] >= last:
            edge("chemo", f"sig_{r['signal']}", "temporal",
                 f"dose Day {last} preceded deviation onset Day {r['onset_day']} by {r['onset_day'] - last} d")
    for cp in changepoints.get("change_points", []):
        if cp["significance"] != "significant":
            continue
        nid = f"cp_{cp['day']}"
        node(nid, "changepoint", f"Change point Day {cp['day']}", cp["kind"], severity="attention", basis="computed",
             detail={"statement": cp["statement"], "posterior": cp["posterior_mass"], "context": cp["context"]})
        for c in cp["contributors"][:4]:
            edge(nid, f"sig_{c['signal']}", "temporal", f"regime shift {c['shift_sd']:+.1f} SD")

    for e in record.events_until(as_of_day):
        if e.kind == "encounter" and e.detail.get("qualifying"):
            nid = f"out_{e.id}"
            node(nid, "outcome", "Acute care", e.display[:60], severity="alert", evidence=[{"type": "Encounter", "ids": [e.id]}],
                 detail={"day": e.day, "condition": e.detail.get("condition")})
            edge("risk", nid, "temporal", f"outcome recorded Day {e.day}")
    ids = {n["id"] for n in nodes}
    for ep in memory.get("episodes", []):
        for iv in ep.get("interventions", []):
            if f"iv_{iv['id']}" in ids and ep.get("end_day"):
                edge(f"iv_{iv['id']}", "risk", "temporal", f"followed by: {ep['resolution']} (Day {ep['end_day']})")
    for a in alerts or []:
        nid = f"alert_{a['id']}"
        node(nid, "outcome", f"Alert {a['tier']}", f"Day {a['as_of_day']} · {a['status']}", severity="attention",
             basis="computed", detail=a)
        edge("risk", nid, "temporal", f"alert raised Day {a['as_of_day']}")

    ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in ids and e["target"] in ids]
    return {
        "as_of_day": as_of_day, "nodes": nodes, "edges": edges, "edge_kinds": EDGE_KINDS,
        "groups": ["clinical", "treatment", "intervention", "wearable", "home", "symptom", "lab", "physiology",
                   "changepoint", "risk", "outcome"],
        "counts": {k: sum(1 for e in edges if e["kind"] == k) for k in EDGE_KINDS},
        "note": ("Solid edges are recorded facts; dotted edges are timestamp orderings; thin edges are data "
                 "provenance; dashed edges are model-derived associations — none of the latter imply causation."),
    }
