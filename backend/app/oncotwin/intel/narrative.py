"""Explanation Agent core — clinician-readable reasoning, safety-gated, LLM optional.

  deterministic  (always available) composed from the computed WHY NOW, the
                 cross-signal table and the uncertainty decomposition; every
                 key point carries the observation ids it rests on
  llm            (opt-in: ONCOTWIN_LLM_EXPLANATIONS=1 and a configured ClinCase
                 LLM provider) the same evidence JSON is synthesised by the LLM
                 under a versioned prompt; the output must pass the safety
                 gates or it is discarded and the deterministic text is shown

LLM observability: each call records model, prompt version (SHA-256 of the
prompt file), latency, input/output tokens, tool calls (none), the evidence ids
it was given, a SHA-256 of the output (NOT the text — no patient narrative is
logged), and the validation result.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.oncotwin.observability import METRICS
from app.oncotwin.records import PatientRecord, day_to_datetime
from app.oncotwin.safety import gates
from app.oncotwin.signals import MODEL_SIGNALS

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "oncotwin" / "explanation.txt"
DECISION_SUPPORT = ("Clinical decision support only — OncoTwin does not diagnose or treat; a clinician reviews "
                    "every alert.")


def prompt() -> tuple[str, str]:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode()).hexdigest()[:16]


def llm_enabled() -> bool:
    return os.getenv("ONCOTWIN_LLM_EXPLANATIONS", "").lower() in ("1", "true", "yes")


def newest_signal_hours(record: PatientRecord, as_of_day: int) -> float | None:
    ref = day_to_datetime(as_of_day, 23, 59)
    newest = None
    for o in record.observations:
        if o.signal in MODEL_SIGNALS and o.day <= as_of_day:
            eff = datetime.fromisoformat(o.effective.replace("Z", "+00:00"))
            if newest is None or eff > newest:
                newest = eff
    return None if newest is None else max(0.0, (ref - newest).total_seconds() / 3600.0)


def evidence_bundle(intel: dict[str, Any]) -> dict[str, Any]:
    """The compact evidence JSON given to the LLM and used to build the gate context."""
    w = intel["why_now"]
    facts = intel["facts"]
    return {
        "as_of_day": intel["as_of_day"], "tier": w["tier"], "triggers": w["triggers"],
        "risk": w["confidence"], "compared_with_baseline": w["compared_with_baseline"],
        "persistence": w["persistence"], "treatment_context": w["treatment_context"], "model": w["model"],
        "data_quality": w["data_quality"], "uncertainty": intel["uncertainty"]["statements"],
        "cross_signal": {k: intel["correlation"][k] for k in ("headline", "summary", "temporal_order")},
        "trajectory": {k: intel["trajectory"][k] for k in ("dynamics", "explanation")},
        "evidence_ids": {k: facts["signals"][k]["ids3"] for k in MODEL_SIGNALS},
    }


def deterministic(intel: dict[str, Any]) -> dict[str, Any]:
    w = intel["why_now"]
    facts = intel["facts"]
    points = [{"text": (f"{v['label']} {v['change']} versus this patient's baseline ({v['z_sd']:+.1f} SD), adverse for "
                        f"{v['persistence_days']} day(s); contribution to the model {v['model_contribution_logit']:+.2f} "
                        "log-odds."),
               "evidence_ids": facts["signals"][v["signal"]]["ids3"]} for v in w["compared_with_baseline"][:6]]
    points += [{"text": t["text"], "evidence_ids": facts["signals"][t["first"]]["ids3"][-1:]}
               for t in intel["correlation"]["temporal_order"][:2]]
    cp = w["persistence"]["change_point"]
    if cp:
        points.append({"text": cp["statement"], "evidence_ids": []})
    return {"summary": w["text"], "key_points": points,
            "caveats": [*intel["uncertainty"]["statements"], DECISION_SUPPORT]}


def _candidate(n: dict[str, Any], intel: dict[str, Any], source: str) -> dict[str, Any]:
    text = " ".join([n["summary"], *[p["text"] for p in n["key_points"]], *n.get("caveats", [])])
    return {"text": text, "evidence_ids": sorted({i for p in n["key_points"] for i in p.get("evidence_ids", [])}),
            "as_of_day": intel["as_of_day"], "risk": intel["why_now"]["confidence"]["risk"], "source": source}


def gate_context(record: PatientRecord, intel: dict[str, Any], model_integrity: bool) -> gates.EvidenceContext:
    return gates.build_context(
        record, intel["as_of_day"], [evidence_bundle(intel), intel["why_now"], intel["correlation"]["signals"],
                                     intel["uncertainty"], intel["prediction"], intel["change_points"]],
        newest_signal_hours=newest_signal_hours(record, intel["as_of_day"]),
        completeness=intel["facts"]["quality"]["completeness"],
        confidence_label=intel["why_now"]["confidence"]["label"], model_integrity=model_integrity)


def _parse(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in LLM output")
    data = json.loads(m.group(0))
    return {"summary": str(data.get("summary", "")),
            "key_points": [{"text": str(p.get("text", "")), "evidence_ids": [str(i) for i in p.get("evidence_ids", [])]}
                           for p in data.get("key_points", []) if isinstance(p, dict)],
            "caveats": [str(c) for c in data.get("caveats", [])]}


async def explain(record: PatientRecord, intel: dict[str, Any], *, model_integrity: bool,
                  use_llm: bool | None = None, client: Any = None, traces: list | None = None) -> dict[str, Any]:
    ctx = gate_context(record, intel, model_integrity)
    det = deterministic(intel)
    det_gate = gates.check(_candidate(det, intel, "deterministic"), ctx)
    narrative, shown_gate, source = det, det_gate, "deterministic"
    want_llm = llm_enabled() if use_llm is None else use_llm
    llm_info: dict[str, Any] = {"enabled": bool(want_llm)}
    if not want_llm:
        llm_info["reason"] = "LLM explanations disabled (set ONCOTWIN_LLM_EXPLANATIONS=1 with a configured provider)"
    else:
        system, pv = prompt()
        ev = evidence_bundle(intel)
        trace: dict[str, Any] = {
            "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "prompt_version": pv, "tool_calls": 0,
            "retrieved_evidence_ids": sorted({i for ids in ev["evidence_ids"].values() for i in ids}),
            "patient_ref": hashlib.sha256(str(record.profile.patient_id).encode()).hexdigest()[:12],
            "as_of_day": intel["as_of_day"]}
        t0 = time.perf_counter()
        try:
            if client is None:
                from app.llm.factory import get_llm_client
                client = get_llm_client()
            resp = await client.complete(system=system, user=json.dumps(ev, default=str), max_tokens=900, temperature=0.0)
            trace.update(model=resp.model_id, input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                         output_sha256=hashlib.sha256(resp.text.encode()).hexdigest())
            parsed = _parse(resp.text)
            g = gates.check(_candidate(parsed, intel, "llm"), ctx)
            failed = [x for x in g["gates"] if not x["passed"]]
            trace["validation"] = {"passed": g["passed"], "failed_gates": [x["gate"] for x in failed]}
            METRICS.inc("oncotwin_llm_calls_total", outcome="accepted" if g["passed"] else "rejected")
            if g["passed"]:
                narrative, shown_gate, source = parsed, g, "llm"
                llm_info["used"] = True
            else:
                llm_info.update(used=False, rejected_by_gates=[x["gate"] for x in failed], rejected_detail=failed)
        except Exception as e:  # noqa: BLE001 — LLM unavailable or malformed → deterministic path
            trace.update(error=str(e)[:200], validation={"passed": False, "failed_gates": ["llm_call"]})
            METRICS.inc("oncotwin_llm_calls_total", outcome="error")
            llm_info.update(used=False, error=str(e)[:200])
        trace["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        METRICS.observe_ms("oncotwin_llm_latency", trace["latency_ms"])
        llm_info["trace"] = trace
        if traces is not None:
            traces.append(trace)
    if not shown_gate["passed"]:
        narrative = {"summary": shown_gate["display_text"], "key_points": [], "caveats": [DECISION_SUPPORT]}
    return {"source": source, **narrative, "safety_gates": shown_gate, "llm": llm_info,
            "language": "associations and model contributions — not causation"}
