"""Live OncoTwin operations: the twin clock, alerts, HITL actions, ingestion, handoff.

Read paths (dashboard, replay, timeline, intelligence) recompute
deterministically from the data feed. Write paths (advance the clock,
evaluate, act on an alert, record an intervention, hand off) run the twin
through its agent graph and append to the hash-chained ledger, so every
surfaced prediction can later be explained — and reproduced — exactly.

Event-driven update: data released by the feed (or ingested) is published as
typed events; the store's handler marks the patient dirty and `drain` runs ONE
incremental twin update per batch (the per-day history extends by the new
days only — see service.compute_history_bundle).
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.oncotwin.agents.graph import run_twin_graph
from app.oncotwin.engine.timeline import build_timeline
from app.oncotwin.engine.warning import RANK, TIERS
from app.oncotwin.events import data_event_for
from app.oncotwin.fhir.mapping import fhir_to_observation, wearable_sample_to_observation
from app.oncotwin.intel.state import build_states, transitions
from app.oncotwin.ml.model import load_model
from app.oncotwin.observability import METRICS
from app.oncotwin.records import day_to_iso
from app.oncotwin.service import (
    HistoryBundle,
    TwinComputation,
    compute_history_bundle,
    compute_twin,
    key_moments,
    provenance,
    signal_panels,
    twin_card,
)
from app.oncotwin.signals import SIGNALS
from app.oncotwin.simulator.patients import InfectionSeed
from app.oncotwin.store import OrgTwinStore, PatientState

ALERT_ACTIONS = {"accept": "accepted", "dismiss": "dismissed", "investigate": "investigating"}
INJECTIONS = {
    "infection": "Introduce a new infection (pathogen seeded tomorrow)",
    "dehydration": "Introduce an acute GI illness (5 days of emesis)",
    "nonadherence": "Supportive-medication adherence drops to 20 % from tomorrow",
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _actor(user: dict[str, Any]) -> str:
    return f"{user.get('email', user.get('id', 'unknown'))} ({user.get('role', '?')})"


# =============================================================================
# Read paths
# =============================================================================


def bundle_for(st: PatientState) -> HistoryBundle:
    """Per-day as-of history (+ facts) up to the live day. Same data version and a later clock →
    extend incrementally; changed data → full recomputation."""
    cached = st.bundle_cache
    if cached and cached[0] == st.data_version:
        b = cached[1]
        if b.until_day == st.live_day:
            return b
        if b.until_day < st.live_day:
            with METRICS.timed("oncotwin_history", mode="incremental"):
                b = compute_history_bundle(st.record(), st.live_day, load_model(), prior=b)
            st.bundle_cache = (st.data_version, b)
            return b
    with METRICS.timed("oncotwin_history", mode="full"):
        b = compute_history_bundle(st.record(), st.live_day, load_model())
    st.bundle_cache = (st.data_version, b)
    return b


def history_for(st: PatientState) -> list[dict[str, Any]]:
    return bundle_for(st).snapshots


def states_for(st: PatientState) -> list[dict[str, Any]]:
    """Living Twin State for every day 1..live_day (index = day-1), cached per data version + clock."""
    b = bundle_for(st)
    if st.states_cache and st.states_cache[:2] == (st.data_version, b.until_day):
        return st.states_cache[2]
    states = build_states(st.record(), b.snapshots, b.day_facts)
    st.states_cache = (st.data_version, b.until_day, states)
    return states


def patient_summary(store: OrgTwinStore, pid: str) -> dict[str, Any]:
    st = store.patient(pid)
    hist = history_for(st)
    last = hist[-1]
    prof = st.record().profile
    open_alerts = [a for a in store.alerts.values() if a["patient_id"] == pid and a["status"] in ("open", "investigating")]
    return {
        "patient": prof.to_dict(), "live_day": st.live_day, "n_days": st.sim.record.n_days,
        "tier": last["tier"], "risk": last["risk"], "risk_p10": last["risk_p10"], "risk_p90": last["risk_p90"],
        "pattern": last["pattern"], "in_acute_care": last["in_acute_care"],
        "risk_series": [{"day": h["day"], "risk": h["risk"], "tier": h["tier"]} for h in hist[-21:]],
        "open_alerts": len(open_alerts), "data_version": st.data_version,
        "injections": st.injections, "ingested_observations": len(st.ingested),
    }


def dashboard(store: OrgTwinStore, pid: str, as_of_day: int | None = None, *, simulate: bool = True) -> dict[str, Any]:
    st = store.patient(pid)
    hist = history_for(st)
    day = max(1, min(as_of_day or st.live_day, st.live_day))
    comp = compute_twin(st.record(), day, history=[h for h in hist if h["day"] <= day],
                        simulate=["current"] if simulate else False, model=load_model())
    return assemble(store, st, comp, hist)


def assemble(store: OrgTwinStore, st: PatientState, comp: TwinComputation, hist: list[dict[str, Any]]) -> dict[str, Any]:
    day = comp.as_of_day
    sim_cur = (comp.simulation or {}).get("scenarios", {}).get("current")
    prov = provenance(comp)
    return {
        "synthetic_notice": "SYNTHETIC demonstration patient — generated by OncoTwin's simulator; not a real person.",
        "patient": comp.record.profile.to_dict(),
        "live_day": st.live_day, "as_of_day": day, "n_days": st.sim.record.n_days,
        "is_replay": day < st.live_day,
        "card": twin_card(comp),
        "state": comp.state,
        "trajectory": comp.trajectory,
        "prediction": comp.prediction,
        "evidence": comp.evidence,
        "signals": signal_panels(comp),
        "risk_timeline": [{k: h[k] for k in ("day", "risk", "risk_p10", "risk_p90", "tier", "raw_tier", "in_acute_care")}
                          for h in hist if h["day"] <= day],
        "risk_forecast": None if not sim_cur else {"days": sim_cur["days"], **sim_cur["risk"],
                                                   "event_probability_cumulative": sim_cur["event_probability_cumulative"]},
        "latent_timeline": [{"day": h["day"], **h["latent"]} for h in hist if h["day"] <= day],
        "latent_forecast": None if not sim_cur else {"days": sim_cur["days"], **sim_cur["latent"]},
        "key_moments": key_moments(comp.record, [h for h in hist if h["day"] <= day]),
        "alerts": [alert_summary(a) for a in store.alerts.values() if a["patient_id"] == st.script.patient_id],
        "provenance": {k: prov[k] for k in ("input_sha256", "n_inputs", "feature_window_days", "model", "oncotwin_version")},
        "injections": st.injections,
    }


def replay(store: OrgTwinStore, pid: str) -> dict[str, Any]:
    st = store.patient(pid)
    hist = history_for(st)
    return {"patient_id": pid, "live_day": st.live_day, "n_days": st.sim.record.n_days,
            "snapshots": hist, "key_moments": key_moments(st.record(), hist),
            "note": "Each snapshot is recomputed as-of its own day using only data available on that day."}


def timeline(store: OrgTwinStore, pid: str, as_of_day: int | None = None) -> dict[str, Any]:
    from app.oncotwin.engine.baseline import compute_baseline
    from app.oncotwin.engine.series import build_series

    st = store.patient(pid)
    hist = history_for(st)
    day = max(1, min(as_of_day or st.live_day, st.live_day))
    record = st.record()
    series = build_series(record, day)
    items = build_timeline(record, series, compute_baseline(series), hist, hitl_items=hitl_timeline(store, pid, day))
    return {"patient_id": pid, "as_of_day": day, "lanes": sorted({i["lane"] for i in items}), "items": items}


def hitl_timeline(store: OrgTwinStore, pid: str, until_day: int) -> list[dict[str, Any]]:
    out = []
    for a in store.alerts.values():
        if a["patient_id"] != pid or a["as_of_day"] > until_day:
            continue
        out.append({"day": a["as_of_day"], "time": a["twin_time"], "lane": "twin",
                    "title": f"ALERT raised: {a['tier']} — risk {a['risk']:.0%} (alert {a['id']})",
                    "detail": {"ledger_entry": a["ledger_entry_id"]}, "severity": "high", "fhir": None,
                    "source": "OncoTwin alert"})
        for act in a["actions"]:
            out.append({"day": a["as_of_day"], "time": a["twin_time"], "lane": "hitl",
                        "title": f"Clinician {act['action'].upper()}: {act['user_email']}"
                                 + (f" — “{act['note']}”" if act.get("note") else ""),
                        "detail": {"ledger_entry": act["ledger_entry_id"], "at": act["at"]}, "severity": "info",
                        "fhir": None, "source": "clinician review"})
        if a.get("handoff"):
            h = a["handoff"]
            out.append({"day": a["as_of_day"], "time": a["twin_time"], "lane": "hitl",
                        "title": f"Handed off to ClinCase → case {h['case_id']} ({h['requested_treatment']['name']})",
                        "detail": {"ledger_entry": h["ledger_entry_id"], "package_sha256": h["package_sha256"]},
                        "severity": "info", "fhir": None, "source": "ClinCase handoff"})
    return out


# =============================================================================
# Write paths (ledgered)
# =============================================================================


def commit_evaluation(store: OrgTwinStore, pid: str, *, actor: str, trigger: str,
                      force_simulation: bool = False) -> dict[str, Any]:
    from app.oncotwin.mlops.predictions import log_prediction
    from app.oncotwin.mlops.versions import feature_version

    with store.lock, METRICS.timed("oncotwin_evaluation"):
        st = store.patient(pid)
        b = bundle_for(st)
        hist = b.snapshots
        states = states_for(st)
        comp, meta = run_twin_graph(st.record(), st.live_day, store.organization_id, history=hist,
                                    force_simulation=force_simulation, bundle=(hist, b.day_facts, states),
                                    drift=(store.drift_cache or (None, None))[1], llm_traces=store.llm_traces)
        prov = provenance(comp)
        pred = comp.prediction
        state = states[st.live_day - 1]
        since = st.last_committed_day
        trans = transitions(states, from_day=(since + 1) if since else st.live_day, to_day=st.live_day)
        expl = comp.intel.get("explanation") or {}
        cps_today = [p for p in (comp.intel.get("change_points") or {}).get("change_points", [])
                     if p["detected_on_day"] == st.live_day and p["significance"] == "significant"]
        entry = store.ledger.append("evaluation", patient_id=pid, actor=actor, payload={
            "as_of_day": comp.as_of_day, "twin_time": day_to_iso(comp.as_of_day, 23, 59), "trigger": trigger,
            "tier": pred["tier"], "previous_tier": pred["previous_tier"], "risk": pred["risk"],
            "risk_interval": [pred["risk_p10"], pred["risk_p90"]],
            "rules_fired": [r["rule"] for r in pred["rules_fired"]],
            "top_contributors": [{"label": c["label"], "logit": c["logit"]} for c in pred["contributors"][:5]],
            "confidence": pred["confidence"]["score"], "model": pred["model"],
            "input_sha256": prov["input_sha256"], "n_inputs": prov["n_inputs"],
            "agent_run_id": meta["run_id"], "agent_trace": meta["agent_trace"],
            # OncoTwin 2.0 lineage: what the twin knew, how it changed, how it was explained
            "twin_state_sha256": state["sha256"], "feature_version": feature_version(),
            "state_transitions": [{k: t[k] for k in ("day", "dimension", "previous", "new", "direction")} for t in trans],
            "readiness": (comp.intel.get("readiness") or {}).get("score"),
            "change_points_confirmed": [p["day"] for p in cps_today],
            "explanation": {"source": expl.get("source"), "safety_gates_passed": (expl.get("safety_gates") or {}).get("passed")},
        })
        prev = next((r for r in reversed(store.predictions) if r["patient_id"] == pid), None)
        log_prediction(store, pid, comp, prov, entry)
        st.last_committed_day = st.live_day
        store.agent_runs.append({"patient_id": pid, "as_of_day": comp.as_of_day, "run_id": meta["run_id"],
                                 "topology": meta["topology"], "agent_trace": meta["agent_trace"], "at": _now(),
                                 "trigger": trigger})
        alert = alert_entry = None
        if pred["escalated"] and RANK.get(pred["tier"], 0) >= RANK["EARLY WARNING"]:
            alert, alert_entry = _create_alert(store, pid, comp, prov, entry, actor)
        _publish_evaluation_events(store, pid, comp, entry, trans, cps_today, prev, alert, b.day_facts[st.live_day - 1])
        METRICS.inc("oncotwin_evaluations_total", tier=pred["tier"])
        return {"evaluation": entry, "alert": alert, "alert_entry": alert_entry, "agent_trace": meta["agent_trace"],
                "tier": pred["tier"], "risk": pred["risk"], "as_of_day": comp.as_of_day,
                "state_transitions": len(trans), "explanation_source": expl.get("source")}


def _publish_evaluation_events(store: OrgTwinStore, pid: str, comp: TwinComputation, entry: dict[str, Any],
                               trans: list[dict[str, Any]], cps_today: list[dict[str, Any]], prev: dict[str, Any] | None,
                               alert: dict[str, Any] | None, facts: dict[str, Any]) -> None:
    p, t, bus = comp.prediction, comp.as_of_day, store.bus
    bus.publish("TwinEvaluated", patient_id=pid, twin_day=t, payload={
        "tier": p["tier"], "risk": p["risk"], "ledger_entry": entry["id"], "input_sha256": entry["payload"]["input_sha256"],
        "readiness": entry["payload"]["readiness"]})
    if prev is None or prev["tier"] != p["tier"] or abs(prev["risk"] - p["risk"]) >= 0.02:
        bus.publish("RiskUpdated", patient_id=pid, twin_day=t, payload={
            "tier": p["tier"], "previous_tier": None if prev is None else prev["tier"], "risk": p["risk"],
            "previous_risk": None if prev is None else prev["risk"], "interval": [p["risk_p10"], p["risk_p90"]]})
    if trans:
        bus.publish("TwinStateChanged", patient_id=pid, twin_day=t, payload={
            "state_sha256": entry["payload"]["twin_state_sha256"],
            "transitions": [{k: x[k] for k in ("dimension", "previous", "new", "direction")} for x in trans]})
    for cp in cps_today:
        bus.publish("ChangePointDetected", patient_id=pid, twin_day=t, payload={
            "regime_start_day": cp["day"], "posterior": cp["posterior_mass"], "kind": cp["kind"],
            "contributors": [c["signal"] for c in cp["contributors"][:4]]})
    new_flags = [f for f in facts["quality"]["flags"] if f["kind"] in ("stuck", "implausible", "conflict")
                 and f["days"] and f["days"][-1] == t]
    if new_flags:
        bus.publish("DataQualityIssueDetected", patient_id=pid, twin_day=t, payload={
            "flags": [{"kind": f["kind"], "signal": f["signal"]} for f in new_flags]})
    if alert is not None:
        bus.publish("EarlyWarningGenerated", patient_id=pid, twin_day=t, payload={
            "alert_id": alert["id"], "tier": alert["tier"], "risk": alert["risk"]})
        METRICS.inc("oncotwin_alerts_total", tier=alert["tier"])


def _create_alert(store: OrgTwinStore, pid: str, comp: TwinComputation, prov: dict[str, Any],
                  eval_entry: dict[str, Any], actor: str) -> tuple[dict[str, Any], dict[str, Any]]:
    pred = comp.prediction
    alert_id = f"ota_{uuid.uuid4().hex[:10]}"
    alert = {
        "id": alert_id, "patient_id": pid, "patient_label": comp.record.profile.label,
        "as_of_day": comp.as_of_day, "twin_time": day_to_iso(comp.as_of_day, 23, 59), "created_at": _now(),
        "tier": pred["tier"], "previous_tier": pred["previous_tier"],
        "risk": pred["risk"], "risk_p10": pred["risk_p10"], "risk_p90": pred["risk_p90"],
        "headline": comp.evidence["headline"], "evidence": copy.deepcopy(comp.evidence),
        "prediction": {k: copy.deepcopy(pred[k]) for k in ("contributors", "rules_fired", "thresholds", "features",
                                                           "logit_check", "confidence", "model", "probability_tier",
                                                           "rule_tier", "raw_tier")},
        "state_summary": twin_card(comp), "provenance": prov,
        "history_window": [h for h in (comp.history or []) if h["day"] >= comp.as_of_day - 7],
        "evaluation_entry_id": eval_entry["id"], "evaluation_entry_hash": eval_entry["hash"],
        "status": "open", "actions": [], "handoff": None, "interventions": [],
        # OncoTwin 2.0: why now, the safety-gated explanation, readiness and uncertainty at raise time
        "why_now": copy.deepcopy(comp.intel.get("why_now")),
        "explanation": copy.deepcopy(comp.intel.get("explanation")),
        "readiness": copy.deepcopy(comp.intel.get("readiness")),
        "uncertainty_statements": list((comp.intel.get("uncertainty") or {}).get("statements", [])),
        "clinical_context": copy.deepcopy(comp.intel.get("clinical_context")),
        "twin_state_sha256": eval_entry["payload"].get("twin_state_sha256"),
    }
    entry = store.ledger.append("alert", patient_id=pid, actor="oncotwin", payload={
        "alert_id": alert_id, "tier": pred["tier"], "previous_tier": pred["previous_tier"], "risk": pred["risk"],
        "headline": alert["headline"], "evaluation_entry_id": eval_entry["id"], "input_sha256": prov["input_sha256"],
        "model": pred["model"], "raised_during": actor,
    })
    alert["ledger_entry_id"] = entry["id"]
    store.alerts[alert_id] = alert
    return alert, entry


def publish_day_data(store: OrgTwinStore, pid: str, day: int, *, source: str = "synthetic-feed") -> int:
    """Release one day of the patient's feed as typed data events (the twin clock moved)."""
    rec = store.patient(pid).record()
    n = 0
    for o in rec.observations:
        if o.day != day:
            continue
        spec = SIGNALS.get(o.signal)
        store.bus.publish(data_event_for(spec.category if spec else "other"), patient_id=pid, twin_day=day, source=source,
                          payload={"observation_id": o.id, "signal": o.signal, "value": o.value,
                                   "unit": spec.unit_display if spec else None, "source": o.source, "effective": o.effective})
        n += 1
    supportive = 0
    for e in rec.events:
        if e.day != day:
            continue
        if e.kind == "supportive_dose":
            supportive += 1
            continue
        store.bus.publish("TreatmentEventRecorded", patient_id=pid, twin_day=day, source=source,
                          payload={"event_id": e.id, "kind": e.kind, "display": e.display, "fhir_type": e.fhir_type})
        n += 1
    if supportive:
        store.bus.publish("TreatmentEventRecorded", patient_id=pid, twin_day=day, source=source,
                          payload={"kind": "supportive_dose", "count": supportive,
                                   "display": f"{supportive} supportive-medication administration record(s)"})
        n += 1
    return n


def drain(store: OrgTwinStore, pid: str, *, actor: str, trigger: str | None = None,
          force: bool = False) -> dict[str, Any] | None:
    """Consume the patient's pending data events with ONE incremental twin update."""
    evs = store.dirty.pop(pid, [])
    if not evs and not force:
        return None
    types: dict[str, int] = {}
    for e in evs:
        types[e["type"]] = types.get(e["type"], 0) + 1
    why = trigger or ("event batch: " + ", ".join(f"{n}× {t}" for t, n in sorted(types.items())))
    return commit_evaluation(store, pid, actor=actor, trigger=why)


def advance(store: OrgTwinStore, pid: str, days: int, *, actor: str) -> dict[str, Any]:
    results = []
    with store.lock:
        st = store.patient(pid)
        for _ in range(max(1, min(days, 14))):
            if st.live_day >= st.sim.record.n_days:
                break
            st.live_day += 1
            n = publish_day_data(store, pid, st.live_day)
            res = drain(store, pid, actor=actor, force=True,
                        trigger=(f"twin clock advanced to Day {st.live_day}: {n} data event(s) consumed"
                                 if n else f"twin clock advanced to Day {st.live_day}: no new data (staleness counts)"))
            results.append(res)
    return {"patient_id": pid, "live_day": store.patient(pid).live_day,
            "evaluations": [{k: r[k] for k in ("as_of_day", "tier", "risk")} | {"ledger_entry": r["evaluation"]["id"]}
                            for r in results],
            "alerts": [r["alert"]["id"] for r in results if r["alert"]],
            "entries": [r["evaluation"] for r in results] + [r["alert_entry"] for r in results if r["alert_entry"]]}


def inject(store: OrgTwinStore, pid: str, kind: str, *, actor: str) -> dict[str, Any]:
    if kind not in INJECTIONS:
        raise ValueError(f"kind must be one of {sorted(INJECTIONS)}")
    with store.lock:
        st = store.patient(pid)
        day = st.live_day + 1
        if day > st.sim.record.n_days:
            raise ValueError("The twin clock is at the end of this patient's synthetic feed.")
        before = _past_digest(st, st.live_day)
        script = copy.deepcopy(st.script)
        if kind == "infection":
            vir = 0.9 if st.sim.record.profile.regimen_code in ("PEMBRO", "CAPOX") else 0.35
            script.infection_seeds.append(InfectionSeed(day=day, size=0.25, virulence=vir))
        elif kind == "dehydration":
            script.gi_insults.append((day, 0.9, 5))
        else:
            script.adherence_plan = [*script.adherence_plan, (day, 0.2)]
        st.resimulate(script)
        record = {"kind": kind, "label": INJECTIONS[kind], "effective_from_day": day, "at": _now(),
                  "past_data_unchanged": before == _past_digest(st, st.live_day)}
        st.injections.append(record)
        entry = store.ledger.append("demo_injection", patient_id=pid, actor=actor, payload={
            **record, "notice": "DEMO CONTROL — synthetic perturbation of the simulated feed for future days only",
            "data_version": st.data_version})
        return {"injection": record, "entry": entry}


def _past_digest(st: PatientState, until_day: int) -> str:
    rows = [(o.id, o.value) for o in st.record().observations if o.day <= until_day]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def ingest(store: OrgTwinStore, pid: str, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    with store.lock:
        st = store.patient(pid)
        new = []
        errors: list[dict[str, Any]] = []
        for i, r in enumerate(payload.get("fhir_observations") or []):
            try:
                new.append(fhir_to_observation(r, pid))
            except (ValueError, KeyError, TypeError) as e:
                errors.append({"index": i, "kind": "fhir", "error": str(e)})
        for i, s in enumerate(payload.get("wearable_samples") or []):
            try:
                new.append(wearable_sample_to_observation(s, pid))
            except (ValueError, KeyError, TypeError) as e:
                errors.append({"index": i, "kind": "wearable", "error": str(e)})
        n_days = st.sim.record.n_days
        accepted = [o for o in new if 1 <= o.day <= n_days]
        errors += [{"id": o.id, "error": f"day {o.day} outside this patient's timeline (1–{n_days})"}
                   for o in new if not 1 <= o.day <= n_days]
        st.ingested.extend(accepted)
        if accepted:
            st.invalidate()
        entry = store.ledger.append("ingest", patient_id=pid, actor=actor, payload={
            "accepted": len(accepted), "rejected": len(errors),
            "observations": [{"id": o.id, "signal": o.signal, "day": o.day, "value": o.value, "source": o.source}
                             for o in accepted],
            "sha256": hashlib.sha256(json.dumps([o.to_dict() for o in accepted], sort_keys=True).encode()).hexdigest(),
        })
        for o in accepted:
            spec = SIGNALS.get(o.signal)
            store.bus.publish(data_event_for(spec.category if spec else "other"), patient_id=pid, twin_day=o.day,
                              source="api/ingest", payload={"observation_id": o.id, "signal": o.signal, "value": o.value,
                                                            "source": o.source, "effective": o.effective})
        update, extra = None, []
        if any(o.day <= st.live_day for o in accepted):
            n_before = len(store.ledger.entries)
            upd = drain(store, pid, actor=actor, trigger=f"{len(accepted)} ingested observation(s) for visible days")
            extra = store.ledger.entries[n_before:]           # evaluation (+ alert) entries — persisted by the caller
            if upd is not None:
                update = {k: upd[k] for k in ("as_of_day", "tier", "risk")} | {
                    "ledger_entry": upd["evaluation"]["id"], "alert": (upd["alert"] or {}).get("id")}
        else:
            store.dirty.pop(pid, None)       # future-day data are consumed when the clock reaches them
        return {"accepted": [o.to_dict() for o in accepted], "errors": errors, "entry": entry, "twin_update": update,
                "extra_entries": extra,
                "note": ("Observations dated on or before the twin clock triggered an immediate incremental twin update; "
                         "later-dated observations become visible when the clock reaches their day.")}


def alert_summary(a: dict[str, Any]) -> dict[str, Any]:
    return {k: a[k] for k in ("id", "patient_id", "patient_label", "as_of_day", "twin_time", "created_at", "tier",
                              "previous_tier", "risk", "risk_p10", "risk_p90", "headline", "status")} | {
        "n_actions": len(a["actions"]), "handoff_case_id": (a.get("handoff") or {}).get("case_id")}


def act_on_alert(store: OrgTwinStore, alert_id: str, action: str, note: str | None, user: dict[str, Any]) -> dict[str, Any]:
    if action not in ALERT_ACTIONS:
        raise ValueError(f"action must be one of {sorted(ALERT_ACTIONS)}")
    with store.lock:
        alert = store.alerts.get(alert_id)
        if alert is None:
            raise KeyError(alert_id)
        if alert["status"] == "dismissed":
            raise ValueError("Alert already dismissed; a new evaluation must raise a new alert.")
        rec = {"action": action, "note": (note or "").strip()[:2000] or None, "user_id": user.get("id"),
               "user_email": user.get("email"), "role": user.get("role"), "at": _now(),
               "status_before": alert["status"]}
        alert["status"] = ALERT_ACTIONS[action]
        entry = store.ledger.append("alert_action", patient_id=alert["patient_id"], actor=_actor(user), payload={
            "alert_id": alert_id, **rec, "status_after": alert["status"]})
        rec["ledger_entry_id"] = entry["id"]
        alert["actions"].append(rec)
        store.bus.publish("ClinicianReviewed", patient_id=alert["patient_id"], twin_day=alert["as_of_day"], payload={
            "alert_id": alert_id, "action": action, "role": user.get("role"), "ledger_entry": entry["id"]})
        return {"alert": alert_summary(alert), "action": rec, "entry": entry}


def why(store: OrgTwinStore, alert_id: str) -> dict[str, Any]:
    alert = store.alerts.get(alert_id)
    if alert is None:
        raise KeyError(alert_id)
    related = [e for e in store.ledger.entries
               if e["id"] in (alert["evaluation_entry_id"], alert["ledger_entry_id"])
               or e["payload"].get("alert_id") == alert_id]
    pred = alert["prediction"]
    crossed = [f"model risk {alert['risk']:.1%} ≥ {t.replace('_', ' ')} threshold {v:.1%}"
               for t, v in pred["thresholds"].items() if isinstance(v, float) and alert["risk"] >= v]
    rules = [r["text"] for r in pred["rules_fired"]]
    hw = alert["history_window"]
    trend = ", ".join(f"D{h['day']} {h['risk']:.0%}/{h['tier']}" for h in hw)
    drivers = ", ".join(c["label"] for c in pred["contributors"][:3] if c["logit"] > 0) or "—"
    answer = (
        f"At twin time {alert['twin_time']} (Day {alert['as_of_day']}) the twin moved {alert['previous_tier']} → "
        f"{alert['tier']}. Trigger: " + ("; ".join(crossed + rules) or "tier rules") + ". "
        f"Main drivers: {drivers}. Compared with: {alert['evidence']['compared_with']}. "
        f"{alert['evidence']['period']['text']} Preceding days: {trend}. "
        f"Model {pred['model']['model_id']} v{pred['model']['version']} (artifact {pred['model']['artifact_sha256'][:12]}…); "
        f"inputs SHA-256 {alert['provenance']['input_sha256'][:16]}… over {alert['provenance']['n_inputs']} "
        f"observations/events."
    )
    return {"alert": alert, "answer": answer, "thresholds_crossed": crossed, "rules_fired": rules,
            "history_window": hw, "ledger_entries": related, "chain_verification": store.ledger.verify()}


async def handoff(store: OrgTwinStore, alert_id: str, user: dict[str, Any],
                  requested_override: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.api.cases import CreateCaseRequest, create_case
    from app.oncotwin.handoff import build_package

    alert = store.alerts.get(alert_id)
    if alert is None:
        raise KeyError(alert_id)
    if alert["status"] not in ("accepted", "investigating"):
        raise ValueError("A clinician must ACCEPT or mark the alert INVESTIGATE before it can be handed to ClinCase.")
    if alert.get("handoff"):
        return {"handoff": alert["handoff"], "already_handed_off": True}
    st = store.patient(alert["patient_id"])
    pkg = await build_package(st.record(), alert, store.organization_id, requested_override)
    resp = await create_case(CreateCaseRequest(**pkg["create_case_request"]), user)
    rec = {
        "case_id": resp.case_id, "created_at": _now(), "created_by": user.get("email"),
        "requested_treatment": pkg["create_case_request"]["requested_treatment"],
        "requested_treatment_rationale": pkg["requested_treatment_rationale"],
        "policy_preview": pkg["policy_preview"], "policy_preview_note": pkg["policy_preview_note"],
        "package_sha256": pkg["package_sha256"], "bundle_resource_count": pkg["bundle_resource_count"],
        "physician_note_draft": pkg["create_case_request"]["physician_note"],
        "next_step": f"Open /cases/{resp.case_id} and run the ClinCase 7-agent pipeline (its HITL gate applies).",
    }
    with store.lock:
        entry = store.ledger.append("handoff", patient_id=alert["patient_id"], actor=_actor(user), payload={
            "alert_id": alert_id, "case_id": resp.case_id, "requested_treatment": rec["requested_treatment"]["name"],
            "package_sha256": rec["package_sha256"], "policy_sections_matched": len(rec["policy_preview"])})
        rec["ledger_entry_id"] = entry["id"]
        alert["handoff"] = rec
        store.handoffs.append({"alert_id": alert_id, **rec})
        store.bus.publish("HandoffCreated", patient_id=alert["patient_id"], twin_day=alert["as_of_day"], payload={
            "alert_id": alert_id, "case_id": resp.case_id, "requested_treatment": rec["requested_treatment"]["name"],
            "package_sha256": rec["package_sha256"]})
    return {"handoff": rec, "entry": entry, "already_handed_off": False}


def audit(store: OrgTwinStore, patient_id: str | None = None, limit: int = 200) -> dict[str, Any]:
    rows = [e for e in store.ledger.entries if patient_id is None or e["patient_id"] == patient_id]
    return {"organization_id": store.organization_id, "verification": store.ledger.verify(),
            "entries": rows[-limit:][::-1], "total": len(rows),
            "hashing": "SHA-256 over the canonical JSON of each entry, including the previous entry's hash"}


# =============================================================================
# OncoTwin 2.0 — intelligence, command center, clinical loop, knowledge, counterfactual
# =============================================================================

TRIAGE_ORDER = ("High Priority", "Early Warning", "Watch", "Data Quality Issue", "Stable", "In acute care")
SYNTHETIC_NOTICE = "SYNTHETIC demonstration patient — generated by OncoTwin's simulator; not a real person."
INTERVENTIONS = {
    "urgent_eval_abx": "Urgent evaluation + empiric oral antibiotics (7 days)",
    "gcsf": "G-CSF now (pegfilgrastim 6 mg SC)",
    "gcsf_secondary": "Care plan: pegfilgrastim secondary prophylaxis from the next cycle",
    "hydration": "IV fluids at the infusion center",
    "adherence_support": "Nurse-navigator supportive-medication adherence call",
    "dose_reduction": "Care plan: 20 % dose reduction from the next cycle",
    "activity": "Exercise-oncology referral (supervised activity programme)",
}


def drift_status(store: OrgTwinStore, *, refresh: bool = False) -> dict[str, Any]:
    """Population drift over every twin's recent scoring window (cached per data versions + clocks)."""
    from app.oncotwin.mlops.drift import monitor

    key = tuple((pid, st.data_version, st.live_day) for pid, st in sorted(store.patients.items()))
    if not refresh and store.drift_cache and store.drift_cache[0] == key:
        return store.drift_cache[1]
    prev = (store.drift_cache or (None, {}))[1] or {}
    with METRICS.timed("oncotwin_drift_monitor"):
        d = monitor(store)
    store.drift_cache = (key, d)
    if d.get("status") == "drift" and prev.get("status") != "drift":
        store.bus.publish("ModelDriftDetected", patient_id=None, payload={
            k: d.get(k) for k in ("message", "drifted_features", "drifted_missingness")})
    return d


def triage(intel: dict[str, Any]) -> dict[str, Any]:
    tier = intel["state"]["dimensions"]["risk"]["status"]
    dq = intel["state"]["dimensions"]["data_quality"]["status"]
    reasons = []
    if intel["readiness"]["label"] == "low":
        reasons.append(f"Twin readiness low (limited by {intel['readiness']['limiting_factor'].replace('_', ' ')})")
    if dq == "poor":
        reasons.append("data quality poor")
    if intel["consistency"]["status"] == "inconsistent":
        reasons.append("record inconsistent")
    if tier == "IN ACUTE CARE":
        cat = "In acute care"
    elif tier == "HIGH PRIORITY":
        cat = "High Priority"
    elif tier == "EARLY WARNING":
        cat = "Early Warning"
    elif reasons:
        cat = "Data Quality Issue"
    elif tier == "WATCH":
        cat = "Watch"
    else:
        cat = "Stable"
    return {"category": cat, "data_quality_reasons": reasons,
            "rule": "clinical tier first (HIGH PRIORITY / EARLY WARNING); otherwise a data-quality issue outranks WATCH"}


def intelligence(store: OrgTwinStore, pid: str, as_of_day: int | None = None) -> dict[str, Any]:
    """Every OncoTwin 2.0 engine for one patient as of a day (cached per data version + clock + day)."""
    from app.oncotwin.intel.analysis import compute

    st = store.patient(pid)
    b = bundle_for(st)
    states = states_for(st)
    day = max(1, min(as_of_day or st.live_day, st.live_day))
    key = (st.data_version, st.live_day, day)
    if key in st.intel_cache:
        return st.intel_cache[key]
    alerts = [alert_summary(a) for a in store.alerts.values() if a["patient_id"] == pid and a["as_of_day"] <= day]
    with METRICS.timed("oncotwin_intelligence"):
        out = compute(st.record(), b.snapshots, b.day_facts, states, day, load_model(),
                      drift=(store.drift_cache or (None, None))[1], alerts=alerts)
    out.update(patient=st.record().profile.to_dict(), live_day=st.live_day, n_days=st.sim.record.n_days,
               is_replay=day < st.live_day, synthetic_notice=SYNTHETIC_NOTICE,
               interventions=[i for i in st.interventions if i["recorded_at_twin_day"] <= day])
    out["triage"] = triage(out)
    if len(st.intel_cache) > 32:
        st.intel_cache.clear()
    st.intel_cache[key] = out
    return out


def command_center(store: OrgTwinStore) -> dict[str, Any]:
    for st in store.patients.values():
        bundle_for(st)
    drift = drift_status(store)
    rows = []
    for pid, st in store.patients.items():
        it = intelligence(store, pid)
        risk = it["state"]["dimensions"]["risk"]["fields"]
        hist = history_for(st)
        wc = it["what_changed"]["changed"]
        cp = it["change_points"].get("latest_unexplained_adverse")
        rows.append({
            "patient": it["patient"], "live_day": st.live_day, "n_days": it["n_days"],
            "category": it["triage"]["category"], "category_reasons": it["triage"]["data_quality_reasons"],
            "tier": it["state"]["dimensions"]["risk"]["status"], "risk": risk["risk_7d"],
            "risk_p10": risk["p10"], "risk_p90": risk["p90"],
            "risk_series": [{"day": h["day"], "risk": h["risk"], "tier": h["tier"]} for h in hist[-14:]],
            "readiness": {k: it["readiness"][k] for k in ("score", "label", "limiting_factor")},
            "data_quality": it["state"]["dimensions"]["data_quality"]["status"],
            "trajectory": it["trajectory"]["dynamics"], "pattern": it["state"]["dimensions"]["trajectory"]["status"],
            "top_change": wc[0] if wc else None, "n_changes_3d": len(wc),
            "change_point": None if cp is None else {"day": cp["day"], "kind": cp["kind"]},
            "conflicts": [c["title"] for c in it["conflicts"] if c["detected"]],
            "consistency": it["consistency"]["status"],
            "open_alerts": sum(1 for a in store.alerts.values() if a["patient_id"] == pid and a["status"] in ("open", "investigating")),
            "why_now": it["why_now"]["text"],
        })
    rank = {c: i for i, c in enumerate(TRIAGE_ORDER)}
    rows.sort(key=lambda r: (rank[r["category"]], -r["risk"]))
    counts = {c: sum(1 for r in rows if r["category"] == c) for c in TRIAGE_ORDER}
    for c, n in counts.items():
        METRICS.gauge("oncotwin_patients_by_category", n, category=c)
    return {"categories": list(TRIAGE_ORDER), "counts": counts, "patients": rows, "drift": drift,
            "ledger": store.ledger.verify(), "synthetic": True,
            "note": "Triage is decision support for prioritising review — not a clinical acuity score."}


def record_intervention(store: OrgTwinStore, pid: str, kind: str, note: str | None, user: dict[str, Any],
                        alert_id: str | None = None) -> dict[str, Any]:
    """Clinical Digital Twin loop: the clinician records an intervention; the (synthetic) patient's world
    responds from the next twin day; the twin sees the consequences only as new data arrive."""
    if kind not in INTERVENTIONS:
        raise ValueError(f"kind must be one of {sorted(INTERVENTIONS)}")
    with store.lock:
        st = store.patient(pid)
        day = st.live_day + 1
        if day > st.sim.record.n_days:
            raise ValueError("The twin clock is at the end of this patient's synthetic feed.")
        alert = store.alerts.get(alert_id) if alert_id else None
        if alert_id and (alert is None or alert["patient_id"] != pid):
            raise KeyError(alert_id)
        before = _past_digest(st, st.live_day)
        script = copy.deepcopy(st.script)
        script.interventions = [*script.interventions, (day, kind)]
        st.resimulate(script)
        rec = {"id": f"oti_{uuid.uuid4().hex[:10]}", "kind": kind, "label": INTERVENTIONS[kind],
               "effective_from_day": day, "recorded_at_twin_day": st.live_day, "note": (note or "").strip()[:2000] or None,
               "user_email": user.get("email"), "role": user.get("role"), "at": _now(), "alert_id": alert_id,
               "past_data_unchanged": before == _past_digest(st, st.live_day),
               "mechanism": ("synthetic world re-simulated from the effective day (in production: the EHR records the "
                             "order and the resulting MedicationAdministration / Encounter resources flow in as data)")}
        st.interventions.append(rec)
        if alert is not None:
            alert.setdefault("interventions", []).append(rec)
        entry = store.ledger.append("intervention", patient_id=pid, actor=_actor(user), payload={
            k: rec[k] for k in ("id", "kind", "label", "effective_from_day", "recorded_at_twin_day", "note", "alert_id",
                                "past_data_unchanged")})
        rec["ledger_entry_id"] = entry["id"]
        store.bus.publish("InterventionRecorded", patient_id=pid, twin_day=st.live_day, payload={
            "intervention_id": rec["id"], "kind": kind, "effective_from_day": day, "alert_id": alert_id})
        return {"intervention": rec, "entry": entry}


def knowledge(store: OrgTwinStore, pid: str, *, entry_id: str | None = None, day: int | None = None) -> dict[str, Any]:
    """What did the Digital Twin know at that moment? — and can we reproduce it exactly?"""
    st = store.patient(pid)
    recorded = None
    if entry_id:
        recorded = next((e for e in store.ledger.entries if e["id"] == entry_id and e["patient_id"] == pid
                         and e["kind"] == "evaluation"), None)
        if recorded is None:
            raise KeyError(entry_id)
        day = recorded["payload"]["as_of_day"]
    day = max(1, min(day or st.live_day, st.live_day))
    b = bundle_for(st)
    states = states_for(st)
    model = load_model()
    comp = compute_twin(st.record(), day, history=[h for h in b.snapshots if h["day"] <= day], model=model)
    prov = provenance(comp)
    now = {"as_of_day": day, "tier": comp.prediction["tier"], "risk": comp.prediction["risk"],
           "input_sha256": prov["input_sha256"], "n_inputs": prov["n_inputs"],
           "twin_state_sha256": states[day - 1]["sha256"], "model": model.version_info()}
    out: dict[str, Any] = {
        "patient_id": pid, "as_of_day": day, "twin_time": day_to_iso(day, 23, 59),
        "what_the_twin_knew": {"state": states[day - 1], "prediction": {k: comp.prediction[k] for k in (
            "risk", "risk_p10", "risk_p90", "tier", "rules_fired", "contributors", "confidence")},
            "inputs": prov["inputs"], "feature_window_days": prov["feature_window_days"]},
        "recomputed": now,
        "evaluations_on_this_day": [{"id": e["id"], "at": e["created_at"], "tier": e["payload"]["tier"],
                                     "risk": e["payload"]["risk"], "trigger": e["payload"].get("trigger")}
                                    for e in store.ledger.entries if e["patient_id"] == pid and e["kind"] == "evaluation"
                                    and e["payload"]["as_of_day"] == day],
    }
    if recorded is not None:
        p = recorded["payload"]
        checks = {
            "input_sha256": p["input_sha256"] == now["input_sha256"],
            "risk": abs(p["risk"] - now["risk"]) < 1e-9,
            "tier": p["tier"] == now["tier"],
            "model_artifact": p["model"]["artifact_sha256"] == now["model"]["artifact_sha256"],
            "twin_state": (p.get("twin_state_sha256") == now["twin_state_sha256"]) if p.get("twin_state_sha256") else None,
        }
        ok = all(v for v in checks.values() if v is not None)
        out["recorded"] = {"entry_id": recorded["id"], "hash": recorded["hash"], "created_at": recorded["created_at"],
                           **{k: p.get(k) for k in ("tier", "risk", "input_sha256", "twin_state_sha256", "model")}}
        out["reproduction"] = {
            "reproduced": ok, "checks": checks,
            "explanation": ("Recomputing from the record as of that day reproduces the ledgered prediction exactly."
                            if ok else "The recomputation differs: data dated on or before that day, or the model "
                                       "artifact, changed after the evaluation (see the ingest / model entries in the ledger)."),
        }
        out["chain_verification"] = store.ledger.verify()
    return out


def counterfactual_view(store: OrgTwinStore, pid: str, anchor_day: int | None = None, *, scenario: str = "current",
                        custom: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.oncotwin.intel.counterfactual import counterfactual

    st = store.patient(pid)
    b = bundle_for(st)
    if anchor_day is None:
        first_alert = min((a["as_of_day"] for a in store.alerts.values() if a["patient_id"] == pid), default=None)
        anchor_day = first_alert or max(1, st.live_day - 7)
    with METRICS.timed("oncotwin_counterfactual"):
        return counterfactual(st.record(), b.snapshots, anchor_day, st.live_day, load_model(), scenario=scenario,
                              custom=custom, script=st.script)
