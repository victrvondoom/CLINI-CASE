"""Evaluation harness.

  --mode verifier   Offline, no LLM. Injects known faults into otherwise-consistent decisions and measures the
                    independent verifier's catch rate and false-alarm rate. SYNTHETIC: it measures the
                    verifier's logic, not clinical accuracy.
  --mode live       Runs the real graph on the fixture bundles with the configured provider (needs LLM_PROVIDER
                    credentials + a database) and reports verdict mix, escalation, citation resolution, cost and
                    latency. Refuses to run without credentials rather than inventing numbers.

Usage:  python scripts/eval_harness.py --mode verifier [--out docs/EVALUATION_RESULTS.md]
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import statistics
import time
from pathlib import Path

from app.models import Citation, Decision, NecessityAssessment
from app.models.necessity import CriterionAssessment
from app.verification.verifier import derive_verdict, verify

BUNDLE = {"entry": [{"resource": {"id": f"obs-{i}"}} for i in range(4)]}


def _assessment(combo: tuple[tuple[str, str], ...]) -> NecessityAssessment:
    return NecessityAssessment(
        criteria=[
            CriterionAssessment(
                criterion_text=f"c{i}", criterion_type=t, policy_excerpt_index=0, status=s,
                supporting_evidence=[], confidence=0.9, rationale="r",
            )
            for i, (t, s) in enumerate(combo)
        ],
        overall_confidence=0.9,
        summary="s",
    )  # fmt: skip


def _decision(verdict: str, cites: list[str]) -> Decision:
    return Decision(
        verdict=verdict, rationale="r", confidence=0.9, risk_flags=[],
        citations=[Citation(kind="clinical", pointer=p, text="x") for p in cites],
    )  # fmt: skip


def run_verifier_eval() -> dict:
    kinds = [("inclusion", s) for s in ("MET", "NOT_MET", "AMBIGUOUS")] + [
        ("exclusion", s) for s in ("MET", "NOT_MET")
    ]
    combos = [c for n in (1, 2, 3) for c in itertools.product(kinds, repeat=n)]
    controls = caught = faults = false_alarms = 0
    by_fault: dict[str, list[int]] = {
        "wrong_verdict": [0, 0],
        "dangling_citation": [0, 0],
        "no_citations": [0, 0],
    }
    for combo in combos:
        a = _assessment(combo)
        truth = derive_verdict(a)
        cites = ["obs-1"] if truth != "REFER" else []
        controls += 1
        if verify(_decision(truth, cites), a, BUNDLE).pause_kind:
            false_alarms += 1
        for v in {"APPROVE", "DENY", "REFER"} - {truth}:
            by_fault["wrong_verdict"][1] += 1
            faults += 1
            if verify(_decision(v, ["obs-1"] if v != "REFER" else []), a, BUNDLE).pause_kind:
                by_fault["wrong_verdict"][0] += 1
                caught += 1
        if truth != "REFER":
            for name, cs in (("dangling_citation", ["nope-9"]), ("no_citations", [])):
                by_fault[name][1] += 1
                faults += 1
                if verify(_decision(truth, cs), a, BUNDLE).pause_kind:
                    by_fault[name][0] += 1
                    caught += 1
    return {
        "controls": controls, "false_alarms": false_alarms, "faults": faults, "caught": caught,
        "by_fault": {k: {"caught": v[0], "total": v[1]} for k, v in by_fault.items()},
    }  # fmt: skip


def render_verifier(r: dict) -> str:
    rows = "\n".join(
        f"| {k} | {v['caught']}/{v['total']} | {100 * v['caught'] / max(1, v['total']):.1f}% |"
        for k, v in r["by_fault"].items()
    )
    return (
        "# Verifier evaluation (synthetic fault injection, no LLM)\n\n"
        f"* Consistent control decisions: {r['controls']} - false alarms: {r['false_alarms']} "
        f"({100 * r['false_alarms'] / max(1, r['controls']):.1f}%)\n"
        f"* Injected faults: {r['faults']} - caught: {r['caught']} "
        f"({100 * r['caught'] / max(1, r['faults']):.1f}%)\n\n"
        "| Fault type | Caught | Rate |\n|---|---|---|\n" + rows + "\n\n"
        "This measures the verifier's deterministic logic over all 1-3 criterion combinations. It is **not** a "
        "measure of clinical accuracy or of any LLM.\n"
    )


async def run_live() -> str:
    from app.agents.framework.context import AgentContext  # noqa: F401
    from app.config import settings
    from app.db import db
    from app.graph.build import build_full_graph
    from app.graph.state import ClinCaseState

    have_key = {
        "openrouter": bool(settings.OPENROUTER_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
        "bedrock": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
    }[settings.LLM_PROVIDER]
    if not have_key:
        raise SystemExit(
            f"live mode needs credentials for LLM_PROVIDER={settings.LLM_PROVIDER!r}; none found"
        )
    await db.connect()
    fixtures = sorted(Path(__file__).resolve().parents[1].glob("tests/fixtures/stage3_*.json"))
    graph = build_full_graph()
    rows = []
    for fx in fixtures:
        bundle = json.loads(fx.read_text())
        t0 = time.time()
        st = ClinCaseState(
            case_id=f"eval-{fx.stem}", organization_id="org_demo", fhir_bundle=bundle,
            requested_treatment={"name": "Trastuzumab", "j_code": "J9355"}, payer_id="aetna",
        )  # fmt: skip
        out = await graph.ainvoke(st)
        final = out if isinstance(out, ClinCaseState) else ClinCaseState.model_validate(out)
        rows.append(
            (
                fx.stem,
                final.decision.verdict if final.decision else "PAUSED",
                final.pause_kind,
                time.time() - t0,
            )
        )
    lat = [r[3] for r in rows]
    body = "\n".join(f"| {n} | {v} | {p or '-'} | {t:.1f}s |" for n, v, p, t in rows)
    return (
        f"# Live run ({settings.LLM_PROVIDER})\n\n| Case | Verdict | Pause | Latency |\n|---|---|---|---|\n{body}\n\n"
        f"Median latency {statistics.median(lat):.1f}s over {len(rows)} cases. Compare verdicts to a clinician-"
        "labelled set before claiming accuracy.\n"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["verifier", "live"], required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    text = (
        render_verifier(run_verifier_eval()) if args.mode == "verifier" else asyncio.run(run_live())
    )
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
