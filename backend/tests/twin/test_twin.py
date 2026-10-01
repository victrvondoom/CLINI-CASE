from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.twin import build_twin, case_intelligence_id, evidence_id

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _case(bundle=None, status="approved"):
    return {
        "id": "case_1",
        "created_at": T0,
        "payer_id": "aetna",
        "status": status,
        "requested_treatment_name": "Trastuzumab",
        "requested_j_code": "J9355",
        "fhir_bundle": bundle
        if bundle is not None
        else {
            "entry": [
                {"resource": {"resourceType": "Observation", "id": "obs-her2"}},
                {"resource": {"resourceType": "Condition", "id": "cond-1"}},
            ]
        },
    }


def _run(name, off, lat, out=None, model="anthropic.claude-sonnet", err=None):
    return {
        "agent_name": name,
        "started_at": T0 + timedelta(seconds=off),
        "finished_at": T0 + timedelta(seconds=off, milliseconds=lat),
        "latency_ms": lat,
        "output_json": json.dumps(out or {}),
        "error_text": err,
        "model_id": model,
        "input_tokens": 1000,
        "output_tokens": 200,
    }


def _decision(cites, verdict="APPROVE", at=10):
    return {
        "verdict": verdict,
        "confidence": 0.9,
        "rationale": "because",
        "citations_json": json.dumps(cites),
        "created_at": T0 + timedelta(seconds=at),
    }


def _build(**kw):
    base = {
        "organization_id": "org_a",
        "case": _case(),
        "job": None,
        "runs": [],
        "decisions": [],
        "appeal": None,
        "actions": [],
    }
    base.update(kw)
    return build_twin(**base)


def test_ids_are_stable_and_scoped():
    a = case_intelligence_id("org_a", "case_1")
    assert a == case_intelligence_id("org_a", "case_1")
    assert a != case_intelligence_id("org_b", "case_1")
    assert a.startswith("CI-") and len(a) == 15
    assert evidence_id("case_1", "clinical", "obs-her2") != evidence_id(
        "case_1", "policy", "obs-her2"
    )


def test_empty_case_has_no_invented_content():
    t = _build()
    assert t["evidence"] == [] and t["agent_history"] == [] and t["infrastructure_events"] == []
    assert t["outcome"]["last_verdict"] is None and t["trace"]["totals"]["agent_ms"] == 0
    assert t["patient_fhir"]["resource_counts"] == {"Condition": 1, "Observation": 1}


def test_dangling_clinical_citation_is_reported():
    d = _decision(
        [
            {"kind": "clinical", "text": "HER2+", "pointer": "obs-her2"},
            {"kind": "clinical", "text": "ghost", "pointer": "obs-missing"},
        ]
    )
    t = _build(decisions=[d])
    by = {e["pointer"]: e for e in t["evidence"]}
    assert (
        by["obs-her2"]["resolved"] is True and by["obs-her2"]["fhir_resource_type"] == "Observation"
    )
    assert by["obs-missing"]["resolved"] is False
    assert t["integrity"]["dangling_citations"] == [by["obs-missing"]["evidence_id"]]
    assert t["integrity"]["all_clinical_citations_resolve"] is False


def test_policy_citation_lineage_and_unknowns_stay_null():
    d = _decision(
        [
            {
                "kind": "policy",
                "text": "x",
                "pointer": "Aetna CPB 0084 v2024.3 (rev 2024-08) § II.B.3",
            }
        ]
    )
    runs = [
        _run(
            "policy_retriever",
            1,
            500,
            {"excerpts": ["Aetna CPB 0084 v2024.3 (rev 2024-08) § II.B.3"]},
        )
    ]
    e = _build(decisions=[d], runs=runs)["evidence"][0]
    assert e["policy_version"] == "2024.3" and e["section"].startswith("§")
    assert e["first_seen_agent"] == "policy_retriever" and e["model_id"]
    assert e["source_document"] is None and e["page"] is None


def test_trace_human_wait_and_cost():
    runs = [_run("a", 0, 1000), _run("b", 1, 2000, model="claude-haiku")]
    t = _build(
        runs=runs,
        decisions=[_decision([], at=5)],
        actions=[
            {
                "reviewer_id": "u",
                "action": "approve",
                "note": None,
                "created_at": T0 + timedelta(seconds=65),
            }
        ],
    )
    tr = t["trace"]
    assert tr["totals"]["agent_ms"] == 3000 and tr["totals"]["human_wait_ms"] == 60000
    assert tr["totals"]["input_tokens"] == 2000 and tr["totals"]["estimated_cost_usd"] > 0
    assert [s["stage"] for s in tr["stages"]][-1] == "human_review"


def test_awaiting_review_is_waiting_not_done():
    t = _build(case=_case(status="awaiting_review"), decisions=[_decision([], "REFER")])
    assert t["trace"]["stages"][-1] == {
        "stage": "human_review",
        "actor": "human",
        "offset_ms": 10000,
        "duration_ms": None,
        "status": "waiting",
    }
    assert t["outcome"]["final"] is False


def test_infra_events_show_retry_and_error():
    job = {
        "status": "error",
        "attempts": 3,
        "claimed_by": "w-1",
        "claimed_at": T0,
        "created_at": T0,
        "finished_at": T0 + timedelta(seconds=9),
        "error_text": "boom",
    }
    ev = _build(job=job)["infrastructure_events"]
    assert [e["event"] for e in ev] == ["queued", "claimed", "retried", "error"]


def test_twin_hash_is_deterministic_and_tamper_evident():
    kw = {"decisions": [_decision([{"kind": "clinical", "text": "t", "pointer": "obs-her2"}])]}
    a, b = _build(**kw), _build(**kw, now=T0)
    assert a["twin_sha256"] == b["twin_sha256"]
    kw2 = {"decisions": [_decision([{"kind": "clinical", "text": "t", "pointer": "cond-1"}])]}
    assert _build(**kw2)["twin_sha256"] != a["twin_sha256"]


def test_malformed_bundle_and_citations_degrade_safely():
    t = _build(
        case=_case(bundle="not json"),
        decisions=[
            {
                "verdict": "DENY",
                "confidence": 0.5,
                "rationale": "r",
                "citations_json": "{bad",
                "created_at": T0,
            }
        ],
    )
    assert t["patient_fhir"]["resources"] == [] and t["evidence"] == []


def test_snapshot_path_pointers_resolve_like_the_composer_enforces():
    snap = {"conditions": [{"name": "breast cancer", "source_resource_id": "cond-1"}]}
    runs = [_run("clinical_extractor", 0, 100, {"snapshot": snap})]
    d = _decision(
        [
            {"kind": "clinical", "text": "dx", "pointer": "conditions[0]"},
            {"kind": "clinical", "text": "gone", "pointer": "conditions[7]"},
        ]
    )
    by = {e["pointer"]: e for e in _build(decisions=[d], runs=runs)["evidence"]}
    assert (
        by["conditions[0]"]["resolved"] is True
        and by["conditions[0]"]["resolution"] == "snapshot_path"
    )
    assert by["conditions[7]"]["resolved"] is False


def test_duplicate_citations_collapse_to_one_evidence_item():
    c = {"kind": "clinical", "text": "t", "pointer": "obs-her2"}
    t = _build(decisions=[_decision([c, dict(c, text="again")])])
    ids = [n["id"] for n in t["evidence_graph"]["nodes"]]
    assert len(t["evidence"]) == 1 and len(ids) == len(set(ids))


def test_stale_reviewer_action_before_a_rerun_does_not_hide_a_pending_review():
    old = {
        "reviewer_id": "u",
        "action": "approve",
        "note": None,
        "created_at": T0 + timedelta(seconds=2),
    }
    t = _build(
        case=_case(status="awaiting_review"),
        decisions=[_decision([], "REFER", at=30)],
        actions=[old],
    )
    last = t["trace"]["stages"][-1]
    assert last["status"] == "waiting" and t["trace"]["totals"]["human_wait_ms"] is None


# ---- run-aware twin (Phase 2) ------------------------------------------------------------------
def _case_run(attempt, trigger="initial", status="completed", run_id=None, at=0, parent=None):
    return {
        "run_id": run_id or f"run_{attempt}", "attempt_no": attempt, "trigger": trigger, "status": status,
        "parent_run_id": parent, "trace_id": f"{attempt:032x}", "job_id": None,
        "created_at": T0 + timedelta(seconds=at), "finished_at": T0 + timedelta(seconds=at + 5),
    }  # fmt: skip


def _tag(row, run_id, job_attempt=1):
    return {**row, "run_id": run_id, "job_attempt": job_attempt}


def test_rerun_is_not_mixed_into_the_original_and_each_run_is_summarised():
    r1, r2 = _case_run(1, at=0), _case_run(2, "rerun", at=100, parent="run_1")
    agents = [
        _tag(_run("necessity_reasoner", 1, 500, {"criteria": [{"status": "MET"}]}), "run_1"),
        _tag(
            _run(
                "necessity_reasoner",
                101,
                900,
                {"criteria": [{"status": "NOT_MET"}, {"status": "MET"}]},
            ),
            "run_2",
        ),
    ]
    decs = [
        {**_decision([], "APPROVE", at=10), "run_id": "run_1"},
        {**_decision([], "DENY", at=110), "run_id": "run_2"},
    ]
    t = _build(case_runs=[r1, r2], runs=agents, decisions=decs, appeals=[])
    assert t["headline_run_id"] == "run_2"
    assert [a["latency_ms"] for a in t["agent_history"]] == [900]  # only the rerun's agents
    assert t["policy"]["criteria_total"] == 2 and t["outcome"]["last_verdict"] == "DENY"
    assert [r["attempt_no"] for r in t["runs"]] == [1, 2] and [r["verdict"] for r in t["runs"]] == [
        "APPROVE",
        "DENY",
    ]
    assert (
        t["trace"]["stages"][0]["offset_ms"] == 1000
    )  # relative to the rerun, not to the case's creation
    assert len(t["model_decisions"]) == 2 and {d["run_id"] for d in t["model_decisions"]} == {
        "run_1",
        "run_2",
    }


def test_a_resume_run_does_not_replace_the_execution_it_follows():
    r1, rs = _case_run(1, at=0), _case_run(2, "resume", at=60, parent="run_1")
    agents = [_tag(_run("necessity_reasoner", 1, 500), "run_1")]
    decs = [
        {**_decision([], "REFER", at=10), "run_id": "run_1"},
        {**_decision([], "APPROVE", at=70), "run_id": "run_2"},
    ]
    acts = [
        {
            "reviewer_id": "u",
            "action": "resume_with_approve",
            "note": None,
            "created_at": T0 + timedelta(seconds=70),
            "run_id": "run_2",
        }
    ]
    t = _build(case_runs=[r1, rs], runs=agents, decisions=decs, appeals=[], actions=acts)
    assert t["headline_run_id"] == "run_1" and len(t["agent_history"]) == 1
    assert [r["trigger"] for r in t["runs"]] == ["initial", "resume"] and t["runs"][1][
        "human_actions"
    ] == 1
    assert t["human_decisions"][0]["run_id"] == "run_2"


def test_rows_from_before_run_identity_appear_as_a_legacy_run():
    legacy = _run("necessity_reasoner", 1, 500)  # no run_id
    t = _build(
        case_runs=[_case_run(1)], runs=[legacy, _tag(_run("necessity_reasoner", 2, 700), "run_1")]
    )
    assert [r["trigger"] for r in t["runs"]] == ["legacy", "initial"] and t["runs"][0][
        "agent_rows"
    ] == 1


def test_stored_identity_is_used_and_a_mismatch_is_reported():
    good = case_intelligence_id("org_a", "case_1")
    assert _build(case={**_case(), "case_intelligence_id": good})["identity"] == {
        "case_intelligence_id": good, "stored": True, "matches_derived": True,
    }  # fmt: skip
    bad = _build(case={**_case(), "case_intelligence_id": "CI-FORGED000000"})
    assert (
        bad["case_intelligence_id"] == "CI-FORGED000000"
        and bad["integrity"]["identity_consistent"] is False
    )


def test_crash_retries_of_one_run_are_visible_but_not_separate_runs():
    r1 = _case_run(1)
    agents = [_tag(_run("a", 1, 10), "run_1", 1), _tag(_run("a", 2, 10), "run_1", 2)]
    t = _build(case_runs=[r1], runs=agents)
    assert len(t["runs"]) == 1 and t["runs"][0]["job_attempts"] == [1, 2]


def test_a_cancelled_run_never_becomes_the_headline():
    real, lost = _case_run(1, at=0), _case_run(2, "rerun", status="cancelled", at=50)
    agents = [_tag(_run("a", 1, 500), "run_1")]
    t = _build(
        case_runs=[real, lost],
        runs=agents,
        decisions=[{**_decision([], "APPROVE"), "run_id": "run_1"}],
    )
    assert (
        t["headline_run_id"] == "run_1"
        and len(t["agent_history"]) == 1
        and t["outcome"]["last_verdict"] == "APPROVE"
    )
    assert [r["status"] for r in t["runs"]] == ["completed", "cancelled"]


def test_headline_shows_only_the_attempt_that_produced_the_outcome():
    agents = [
        _tag(_run("a", 1, 100), "run_1", 1),
        _tag(_run("b", 2, 100), "run_1", 1),
        _tag(_run("a", 3, 200), "run_1", 2),
    ]
    t = _build(case_runs=[_case_run(1)], runs=agents)
    assert [a["latency_ms"] for a in t["agent_history"]] == [
        200
    ]  # attempt 1's rows are not double-counted
    assert t["trace"]["totals"]["agent_ms"] == 200 and t["runs"][0]["job_attempts"] == [1, 2]


def test_after_a_review_resume_the_human_decision_is_the_current_outcome():
    paused = _case_run(
        1, status="paused", at=0
    )  # finished_at = T0+5s, no model decision (graph stopped at the gate)
    resume = _case_run(2, "resume", at=60, parent="run_1")
    acts = [
        {
            "reviewer_id": "u",
            "action": "resume_with_deny",
            "note": None,
            "created_at": T0 + timedelta(seconds=65),
            "run_id": "run_2",
        }
    ]
    human = {
        **_decision(
            [{"kind": "human_override", "text": "t", "pointer": "reviewer_action:u"}], "DENY", at=65
        ),
        "run_id": "run_2",
    }
    t = _build(
        case=_case(status="denied"),
        case_runs=[paused, resume],
        runs=[_tag(_run("a", 1, 300), "run_1")],
        decisions=[human],
        actions=acts,
        appeals=[],
    )
    assert (
        t["outcome"]["last_verdict"] == "DENY" and t["outcome"]["latest_decision_run_id"] == "run_2"
    )
    review = next(s for s in t["trace"]["stages"] if s["stage"] == "human_review")
    assert (
        review["status"] == "ok" and review["duration_ms"] == 60000
    )  # from the pause to the human action
