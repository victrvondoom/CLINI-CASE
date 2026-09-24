"""One-command, reproducible OncoTwin journey (flagship synthetic patient OT-005).

    python -m app.oncotwin.demo                 # prints the journey, writes JSON + Markdown reports
    python -m app.oncotwin.demo --out DIR

Baseline → treatment → wearable stream changes → the twin detects a trajectory
change → elevated deterioration risk → WHY NOW → evidence → WHAT IF → clinician
review → intervention recorded → ClinCase handoff → twin updates → recovery →
counterfactual (with synthetic ground truth) → audit reproduction.

Every step runs the real runtime (event bus, agent graph, ledger) on a fresh,
isolated organisation store; nothing is scripted except the synthetic patient's
physiology. The process exits non-zero if any journey property fails, so the
same command is the end-to-end check in CI. Everything is SYNTHETIC.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.oncotwin import runtime
from app.oncotwin.fhir.mapping import build_bundle
from app.oncotwin.simulator.archetypes import FLAGSHIP_PATIENT
from app.oncotwin.store import OrgTwinStore

DEFAULT_OUT = Path(__file__).resolve().parents[2] / ".cache" / "oncotwin" / "demo"
CLINICIAN = {"id": "demo-reviewer", "email": "reviewer@aerofyta.health", "role": "reviewer",
             "organization_id": "org_oncotwin_demo", "full_name": "Demo Reviewer"}


def run_journey(*, verbose: bool = True, with_handoff: bool = True) -> dict[str, Any]:
    t0 = time.perf_counter()
    store = OrgTwinStore(f"org_oncotwin_demo_{int(time.time() * 1000)}")
    pid = FLAGSHIP_PATIENT
    steps: list[dict[str, Any]] = []

    def step(title: str, detail: dict[str, Any], say: str) -> None:
        steps.append({"step": len(steps) + 1, "title": title, "say": say, "detail": detail})
        if verbose:
            print(f"\n[{len(steps):>2}] {title}\n     {say}")

    st = store.patient(pid)
    rec = st.record()
    types: dict[str, int] = {}
    for e in build_bundle(rec, st.live_day, include_daily=False)["entry"]:
        types[e["resource"]["resourceType"]] = types.get(e["resource"]["resourceType"], 0) + 1
    step("Synthetic cancer patient", {"profile": rec.profile.to_dict(), "fhir_resources": types},
         f"{rec.profile.label}: {rec.profile.age}{rec.profile.sex[0].upper()}, {rec.profile.cancer}, "
         f"{rec.profile.regimen_code}. FHIR R4 history: {sum(types.values())} resources. SYNTHETIC — not a real person.")

    it = runtime.intelligence(store, pid)
    dims = it["state"]["dimensions"]
    facts = runtime.bundle_for(st).day_facts[-1]
    step("Personal baseline established, treatment started",
         {"baseline": facts["baseline"], "treatment": dims["treatment"]["fields"]},
         f"Personal baseline Days {facts['baseline']['window'][0]}–{facts['baseline']['window'][1]} "
         f"({facts['baseline']['kind']}, adequacy {facts['baseline']['adequacy']:.0%}); {dims['treatment']['status']} "
         f"(first dose Day {dims['treatment']['fields']['last_dose_day']}). Twin clock Day {st.live_day}: "
         f"{dims['risk']['status']}.")

    daily, alert_id = [], None
    for _ in range(8):
        adv = runtime.advance(store, pid, 1, actor="demo")
        ev = adv["evaluations"][-1]
        itd = runtime.intelligence(store, pid)
        tr = [f"{t['label']}: {t['previous']} → {t['new']}" for t in itd["transitions_recent"] if t["day"] == ev["as_of_day"]]
        daily.append({"day": ev["as_of_day"], "tier": ev["tier"], "risk": ev["risk"], "transitions": tr})
        if verbose:
            print(f"     Day {ev['as_of_day']}: {ev['tier']:<14} risk {ev['risk']:.1%}  " + "; ".join(tr[:3]))
        if adv["alerts"]:
            alert_id = adv["alerts"][0]
            break
    step("Wearable stream → event-driven twin updates", {"days": daily},
         "Each day's feed is published as typed events; the twin updates incrementally and records state transitions.")
    if alert_id is None:
        raise RuntimeError("journey: no alert was raised")
    alert = store.alerts[alert_id]
    it = runtime.intelligence(store, pid)
    cps = [p for p in it["change_points"]["change_points"] if p["significance"] == "significant"]
    cp = it["change_points"].get("latest_unexplained_adverse") or (cps[-1] if cps else None)
    step("Twin detects a trajectory change",
         {"change_point": cp, "cross_signal": it["correlation"]["headline"], "trajectory": it["trajectory"]["dynamics"]},
         (cp["statement"] if cp else "No significant change point confirmed yet.") + f" {it['correlation']['summary']}")
    hz = it["horizons"].get("horizons", [])
    step("Temporal model predicts elevated deterioration risk",
         {"risk": it["prediction"]["risk"], "interval": [it["prediction"]["risk_p10"], it["prediction"]["risk_p90"]],
          "horizons": hz},
         f"{alert['tier']} — 7-day risk {alert['risk']:.1%} (80% interval {alert['risk_p10']:.1%}–{alert['risk_p90']:.1%}). "
         + ", ".join(f"{h['horizon']}: {'not supported' if h['risk'] is None else format(h['risk'], '.1%')}" for h in hz))
    step("WHY NOW?", {"why_now": it["why_now"]}, it["why_now"]["text"])
    ex = alert["explanation"]
    step("Evidence + Show your work",
         {"explanation_source": ex["source"], "safety_gates": ex["safety_gates"], "show_your_work": it["show_your_work"]},
         f"Explanation ({ex['source']}) passed {sum(g['passed'] for g in ex['safety_gates']['gates'])}/"
         f"{len(ex['safety_gates']['gates'])} safety gates; inputs SHA-256 {it['show_your_work']['input_sha256'][:12]}…")

    from app.oncotwin.service import compute_twin
    comp = compute_twin(st.record(), st.live_day, history=runtime.history_for(st),
                        simulate=["current", "early_intervention"],
                        custom_scenario={"label": "Antibiotics + G-CSF tomorrow", "antibiotics_start_day_offset": 1,
                                         "gcsf_tomorrow": True})
    sc = comp.simulation["scenarios"]
    step("WHAT IF? (simulation — not a recommendation)",
         {k: {"event_probability_7d": v["event_probability_7d"], "risk_day7_median": v["risk_day7_median"]}
          for k, v in sc.items()},
         "; ".join(f"{v['label']}: P(event within 7 d) {v['event_probability_7d']:.0%}" for v in sc.values()))

    runtime.act_on_alert(store, alert_id, "accept", "Reviewed the twin evidence; urgent clinic review arranged.", CLINICIAN)
    ivs = [runtime.record_intervention(store, pid, k, "Recorded after clinician review", CLINICIAN, alert_id)["intervention"]
           for k in ("urgent_eval_abx", "gcsf")]
    step("Clinician review (HITL) and intervention recorded", {"interventions": ivs},
         f"Accepted by {CLINICIAN['email']}; recorded {', '.join(i['label'] for i in ivs)} effective Day "
         f"{ivs[0]['effective_from_day']} (past data unchanged: {all(i['past_data_unchanged'] for i in ivs)}).")

    handoff = None
    if with_handoff:
        try:
            handoff = asyncio.run(runtime.handoff(store, alert_id, CLINICIAN))["handoff"]
            step("ClinCase handoff", {"case_id": handoff["case_id"], "requested": handoff["requested_treatment"],
                                      "policy_sections": len(handoff["policy_preview"])},
                 f"ClinCase case {handoff['case_id']} created for {handoff['requested_treatment']['name']} "
                 f"({len(handoff['policy_preview'])} policy sections matched) — nothing is submitted to a payer.")
        except Exception as e:  # noqa: BLE001 — reported, not hidden
            step("ClinCase handoff", {"error": str(e)[:200]}, f"Handoff unavailable in this environment: {str(e)[:120]}")

    after = runtime.advance(store, pid, 6, actor="demo")["evaluations"]
    step("Twin updates → recovery trajectory", {"days": after}, " → ".join(f"D{e['as_of_day']} {e['tier']}" for e in after))

    cf = runtime.counterfactual_view(store, pid, alert["as_of_day"])
    truth = cf["synthetic_truth"]
    step("Counterfactual twin", {"summary": cf["summary"], "synthetic_truth": truth},
         cf["summary"] + " Synthetic ground truth without the recorded interventions: "
         + str(truth.get("counterfactual_first_event_after_anchor") or "no event") + ".")

    first_eval = next(e for e in store.ledger.entries if e["kind"] == "evaluation")
    kn = runtime.knowledge(store, pid, entry_id=first_eval["id"])
    ver = store.ledger.verify()
    step("Audit — what did the twin know? (reproduced)",
         {"reproduction": kn["reproduction"], "ledger": ver, "events": store.bus.stats()["by_type"]},
         f"Ledger {ver['entries']} entries, chain valid: {ver['valid']}; first evaluation reproduced exactly: "
         f"{kn['reproduction']['reproduced']}.")

    onset = (truth.get("counterfactual_first_event_after_anchor") or {}).get("day")
    checks = {
        "alert_raised_before_counterfactual_admission": bool(onset and alert["as_of_day"] < onset),
        "no_acute_care_after_intervention": all(e["tier"] != "IN ACUTE CARE" for e in after),
        "returned_to_normal": after[-1]["tier"] == "NORMAL",
        "explanation_passed_safety_gates": bool(ex["safety_gates"]["passed"]),
        "past_data_unchanged_by_intervention": all(i["past_data_unchanged"] for i in ivs),
        "ledger_valid": bool(ver["valid"]),
        "evaluation_reproduced": bool(kn["reproduction"]["reproduced"]),
        "events_published": store.bus.stats()["events_in_log"] > 0,
    }
    return {"title": "OncoTwin flagship journey (synthetic OT-005)", "synthetic": True, "steps": steps,
            "checks": checks, "passed": all(checks.values()), "alert_id": alert_id,
            "handoff_case_id": (handoff or {}).get("case_id"), "runtime_seconds": round(time.perf_counter() - t0, 1)}


def _markdown(r: dict[str, Any]) -> str:
    lines = [f"# {r['title']}", "", "> Synthetic demonstration — not a real patient. Clinical decision support only.", ""]
    for s in r["steps"]:
        lines += [f"## {s['step']}. {s['title']}", "", s["say"], ""]
    lines += ["## Journey checks", ""] + [f"- {'PASS' if v else 'FAIL'} — {k.replace('_', ' ')}" for k, v in r["checks"].items()]
    return "\n".join([*lines, "", f"Runtime: {r['runtime_seconds']} s"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-handoff", action="store_true")
    a = ap.parse_args()
    r = run_journey(with_handoff=not a.no_handoff)
    from app.api.oncotwin import clean
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "oncotwin_journey.json").write_text(json.dumps(clean(r), indent=1, default=str), encoding="utf-8")
    (a.out / "oncotwin_journey.md").write_text(_markdown(r), encoding="utf-8")
    print("\nChecks:", json.dumps(r["checks"], indent=1))
    print(f"Report: {a.out / 'oncotwin_journey.md'}  ({r['runtime_seconds']} s)")
    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    main()
