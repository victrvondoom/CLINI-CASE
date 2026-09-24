"""The five OncoTwin agents — real `Agent[I, O]` subclasses of the ClinCase framework.

They are deterministic (no LLM): every number they emit is computed by the
twin engine, so evaluations are reproducible and auditable. Each agent owns
exactly one stage of `app.oncotwin.service`; they share one in-flight
`TwinComputation` through the AgentContext's working memory, the same way
ClinCase parents share one AgentContext per case.

They live in `app.oncotwin.agents` (NOT `app.agents`) on purpose: ClinCase's
manifest auto-discovers parents under `app.agents`, and OncoTwin must not
change the 7-agent ClinCase manifest.
"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.agents.framework import Agent, AgentContext
from app.oncotwin.intel.analysis import stage_context, stage_intelligence, stage_quality, stage_temporal
from app.oncotwin.service import (
    TwinComputation,
    stage_evidence,
    stage_prediction,
    stage_simulation,
    stage_state,
    stage_trajectory,
    stage_validate,
)

WM_KEY = "oncotwin"


class TwinAgentInput(BaseModel):
    patient_id: str
    organization_id: str
    as_of_day: int
    run_id: str


class TwinStateOutput(BaseModel):
    as_of_day: int
    care_setting: str
    baseline_window: dict[str, int]
    baseline_adequacy: float
    latent_loads: dict[str, float]
    anc_estimate: dict[str, Any]
    in_nadir_window: bool
    adherence_7d: float
    quality_flags: int


class TrajectoryOutput(BaseModel):
    pattern: str
    signals_adverse: list[str]
    signals_rising: list[str]
    n_concordant: int
    anomaly_score: float
    sudden_changes: list[str]
    drift_alarms: list[str]


class PredictionOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    outcome_id: str
    horizon_days: int
    risk: float
    risk_p10: float
    risk_p90: float
    tier: str
    previous_tier: str
    escalated: bool
    rules_fired: list[str]
    top_contributors: list[dict[str, Any]]
    confidence: float
    confidence_label: str
    model_version: str
    model_artifact_sha256: str


class SimulationOutput(BaseModel):
    ran: bool
    horizon_days: int = 0
    scenarios: dict[str, dict[str, float]] = Field(default_factory=dict)
    disclaimer: str = ""


class EvidenceOutput(BaseModel):
    headline: str
    what_changed: list[str]
    why: str
    compared_with: str
    period: str
    review: list[str]
    references: list[str]
    why_now: str = ""
    readiness: float | None = None
    uncertainty_statements: list[str] = Field(default_factory=list)


class DataQualityOutput(BaseModel):
    completeness_7d: float
    n_flags: int
    flag_kinds: list[str]
    consistency_status: str
    failed_checks: list[str]
    proceed: bool = True
    note: str = ""


class TemporalOutput(BaseModel):
    n_change_points: int
    latest_significant_change_day: int | None
    risk_dynamics: str
    current_cycle: int | None
    cycle_similarity: list[str]
    conflicts_detected: list[str]


class ContextOutput(BaseModel):
    requested_treatment: str
    policy_sections_matched: int
    rationale: str


class ExplanationOutput(BaseModel):
    source: str
    summary: str
    safety_gates_passed: bool
    failed_gates: list[str]
    llm_enabled: bool
    llm_used: bool = False


WM_BUNDLE = "oncotwin_bundle"          # (snapshots, facts, states) for the evaluation day
WM_DRIFT = "oncotwin_drift"
WM_LLM_TRACES = "oncotwin_llm_traces"


def _twin(ctx: AgentContext) -> TwinComputation:
    return ctx.working_memory[WM_KEY]


class _TwinAgent:
    """Shared ClassVars for the deterministic twin agents."""
    parent: ClassVar[str | None] = None
    input_schema: ClassVar[type[BaseModel]] = TwinAgentInput
    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0
    p95_latency_budget_ms: ClassVar[int] = 5_000


class TwinStateAgent(_TwinAgent, Agent[TwinAgentInput, TwinStateOutput]):
    name: ClassVar[str] = "twin_state_agent"
    role: ClassVar[str] = "state_estimation"
    description: ClassVar[str] = (
        "Builds the as-of patient view from FHIR/EHR, labs, treatment events, wearables, PROs and adherence; "
        "estimates the personal baseline, fits the patient's neutrophil (Friberg) twin and inverts the "
        "observation model into latent infection / dehydration / fatigue loads → Patient State Vector."
    )
    output_schema: ClassVar[type[BaseModel]] = TwinStateOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> TwinStateOutput:
        st = stage_state(_twin(ctx))
        ct = st["cancer_treatment_state"]
        return TwinStateOutput(
            as_of_day=st["as_of_day"], care_setting=st["care_setting"],
            baseline_window=st["baseline_state"]["window"], baseline_adequacy=st["baseline_state"]["adequacy"],
            latent_loads={k: v["value"] for k, v in st["physiological_state"]["latent_loads"].items()},
            anc_estimate=ct["neutrophil"]["twin_estimate_today"], in_nadir_window=ct["in_expected_nadir_window"],
            adherence_7d=st["adherence_state"]["supportive_medication_7d"],
            quality_flags=len([f for f in st["data_quality"]["flags"] if f["kind"] != "gap"]),
        )


class TrajectoryIntelligenceAgent(_TwinAgent, Agent[TwinAgentInput, TrajectoryOutput]):
    name: ClassVar[str] = "trajectory_intelligence_agent"
    role: ClassVar[str] = "trajectory_analysis"
    description: ClassVar[str] = (
        "Analyses all signals as ONE multivariate trajectory against the personal baseline: deviation, 3/7-day "
        "rate, persistence, sudden jumps, CUSUM drift, concordance and Mahalanobis anomaly; names the pattern."
    )
    output_schema: ClassVar[type[BaseModel]] = TrajectoryOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> TrajectoryOutput:
        tr = stage_trajectory(_twin(ctx))
        return TrajectoryOutput(
            pattern=tr["pattern"], signals_adverse=tr["signals_adverse"], signals_rising=tr["signals_rising"],
            n_concordant=tr["n_concordant"], anomaly_score=tr["anomaly_score"],
            sudden_changes=tr["sudden_changes"], drift_alarms=tr["drift_alarms"],
        )


class DeteriorationPredictionAgent(_TwinAgent, Agent[TwinAgentInput, PredictionOutput]):
    name: ClassVar[str] = "deterioration_prediction_agent"
    role: ClassVar[str] = "risk_prediction"
    description: ClassVar[str] = (
        "Scores the ONE outcome OT-ACUTE-7 (unplanned ED visit / admission for an OP-35 condition within 7 days) "
        "with the trained model, bootstrap interval and exact per-feature contributions; applies transparent "
        "clinical rules and hysteresis to assign NORMAL / WATCH / EARLY WARNING / HIGH PRIORITY."
    )
    output_schema: ClassVar[type[BaseModel]] = PredictionOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> PredictionOutput:
        p = stage_prediction(_twin(ctx))
        return PredictionOutput(
            outcome_id=p["outcome_id"], horizon_days=p["horizon_days"], risk=p["risk"], risk_p10=p["risk_p10"],
            risk_p90=p["risk_p90"], tier=p["tier"], previous_tier=p["previous_tier"], escalated=p["escalated"],
            rules_fired=[r["rule"] for r in p["rules_fired"]],
            top_contributors=[{"label": g["label"], "logit": g["logit"]} for g in p["contributors"][:5]],
            confidence=p["confidence"]["score"], confidence_label=p["confidence"]["label"],
            model_version=p["model"]["version"], model_artifact_sha256=p["model"]["artifact_sha256"],
        )


class SimulationAgent(_TwinAgent, Agent[TwinAgentInput, SimulationOutput]):
    name: ClassVar[str] = "simulation_agent"
    role: ClassVar[str] = "what_if_simulation"
    description: ClassVar[str] = (
        "Rolls the personalised twin forward under what-if scenarios (current trajectory, early intervention, "
        "improved recovery, reduced adherence, regimen change) by Monte Carlo with common random numbers; "
        "decision-support simulations, never guaranteed outcomes."
    )
    output_schema: ClassVar[type[BaseModel]] = SimulationOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> SimulationOutput:
        sim = stage_simulation(_twin(ctx))
        return SimulationOutput(
            ran=True, horizon_days=sim["horizon_days"], disclaimer=sim["disclaimer"],
            scenarios={k: {"event_probability_7d": v["event_probability_7d"], "risk_day7_median": v["risk_day7_median"]}
                       for k, v in sim["scenarios"].items()},
        )


class ClinicalEvidenceAgent(_TwinAgent, Agent[TwinAgentInput, EvidenceOutput]):
    name: ClassVar[str] = "clinical_evidence_agent"
    role: ClassVar[str] = "explanation"
    description: ClassVar[str] = (
        "Answers what changed, why, against which baseline, over what period, which signals contributed and what "
        "to review; attaches the exact observations and guideline references (reusing ClinCase's NCCN corpus)."
    )
    output_schema: ClassVar[type[BaseModel]] = EvidenceOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> EvidenceOutput:
        c = _twin(ctx)
        ev = stage_evidence(c)
        snapshots, facts, states = ctx.working_memory[WM_BUNDLE]
        stage_intelligence(c, snapshots, facts, states, drift=ctx.working_memory.get(WM_DRIFT))
        return EvidenceOutput(
            headline=ev["headline"], what_changed=[w["text"] for w in ev["what_changed"]], why=ev["why"],
            compared_with=ev["compared_with"], period=ev["period"]["text"], review=ev["review"],
            references=[r["id"] for r in ev["references"]],
            why_now=c.intel["why_now"]["text"], readiness=c.intel["readiness"]["score"],
            uncertainty_statements=c.intel["uncertainty"]["statements"],
        )


class DataQualityAgent(_TwinAgent, Agent[TwinAgentInput, DataQualityOutput]):
    name: ClassVar[str] = "data_quality_agent"
    role: ClassVar[str] = "data_validation"
    description: ClassVar[str] = (
        "First node: builds the as-of view and validates it — implausible values, stuck sensors, source conflicts, "
        "gaps, staleness, duplicate and timestamp checks, and cross-source consistency (treatment vs admissions, "
        "labs kinetics, G-CSF sequence). It never silently fixes data: problems lower Twin Readiness and are shown."
    )
    output_schema: ClassVar[type[BaseModel]] = DataQualityOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> DataQualityOutput:
        c = _twin(ctx)
        stage_validate(c)
        q = stage_quality(c)
        cs = c.intel["consistency_record"]
        failed = [x["id"] for x in cs["checks"] if x["status"] != "pass"]
        return DataQualityOutput(
            completeness_7d=q["completeness_7d"], n_flags=len(q["flags"]),
            flag_kinds=sorted({f["kind"] for f in q["flags"]}), consistency_status=cs["status"], failed_checks=failed,
            note=cs["summary"])


class TemporalIntelligenceAgent(_TwinAgent, Agent[TwinAgentInput, TemporalOutput]):
    name: ClassVar[str] = "temporal_intelligence_agent"
    role: ClassVar[str] = "temporal_analysis"
    description: ClassVar[str] = (
        "Longitudinal reasoning over the whole course: Bayesian online change-point detection, risk-trajectory "
        "dynamics (acceleration, reversal, recovery, failed recovery), Twin Memory (this cycle vs previous cycles, "
        "recovery velocity) and trajectory-conflict detection between sources."
    )
    output_schema: ClassVar[type[BaseModel]] = TemporalOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> TemporalOutput:
        c = _twin(ctx)
        snapshots, facts, _ = ctx.working_memory[WM_BUNDLE]
        out = stage_temporal(c, snapshots, facts)
        cps = [p for p in out["change_points"]["change_points"] if p["significance"] == "significant"]
        return TemporalOutput(
            n_change_points=len(cps), latest_significant_change_day=cps[-1]["day"] if cps else None,
            risk_dynamics=out["dynamics"]["dynamics"], current_cycle=out["memory"]["current_cycle"],
            cycle_similarity=[s["text"] for s in out["memory"]["similarity"]],
            conflicts_detected=[x["id"] for x in out["conflicts"] if x["detected"]])


class ClinicalContextAgent(_TwinAgent, Agent[TwinAgentInput, ContextOutput]):
    name: ClassVar[str] = "clinical_context_agent"
    role: ClassVar[str] = "clinical_context"
    description: ClassVar[str] = (
        "Connects the twin's evidence to treatment context and to ClinCase: which prior-authorisation request the "
        "pattern would support if a clinician accepts, previewed against ClinCase's own policy corpus through "
        "ClinCase's keyword_filter agent. Runs only when the tier is WATCH or higher; submits nothing."
    )
    output_schema: ClassVar[type[BaseModel]] = ContextOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> ContextOutput:
        out = await stage_context(_twin(ctx), input.organization_id)
        return ContextOutput(requested_treatment=out["clincase_request_if_accepted"]["name"],
                             policy_sections_matched=len(out["policy_preview"]), rationale=out["rationale"])


class ExplanationAgent(_TwinAgent, Agent[TwinAgentInput, ExplanationOutput]):
    name: ClassVar[str] = "explanation_agent"
    role: ClassVar[str] = "explanation_synthesis"
    description: ClassVar[str] = (
        "Turns the computed evidence into clinician-readable reasoning. Deterministic by default; optionally an LLM "
        "synthesis under a versioned prompt. Every statement passes schema, evidence, freshness, uncertainty and "
        "safety gates before display — otherwise a non-confident fallback is shown. Never invents medical facts."
    )
    output_schema: ClassVar[type[BaseModel]] = ExplanationOutput

    async def _execute_deterministic(self, input: TwinAgentInput, ctx: AgentContext) -> ExplanationOutput:
        from app.oncotwin.intel.narrative import explain

        c = _twin(ctx)
        _, facts, states = ctx.working_memory[WM_BUNDLE]
        t = c.as_of_day
        intel = {"as_of_day": t, "why_now": c.intel["why_now"], "facts": facts[t - 1], "correlation": c.intel["correlation"],
                 "uncertainty": c.intel["uncertainty"], "trajectory": c.intel["trajectory_dynamics"],
                 "prediction": c.prediction, "change_points": c.intel["change_points"]}
        res = await explain(c.record, intel, model_integrity=c.model.integrity_verified,
                            traces=ctx.working_memory.get(WM_LLM_TRACES))
        c.intel["explanation"] = res
        return ExplanationOutput(
            source=res["source"], summary=res["summary"][:1500], safety_gates_passed=res["safety_gates"]["passed"],
            failed_gates=[g["gate"] for g in res["safety_gates"]["gates"] if not g["passed"]],
            llm_enabled=res["llm"]["enabled"], llm_used=bool(res["llm"].get("used")))


data_quality_agent = DataQualityAgent()
twin_state_agent = TwinStateAgent()
trajectory_intelligence_agent = TrajectoryIntelligenceAgent()
temporal_intelligence_agent = TemporalIntelligenceAgent()
deterioration_prediction_agent = DeteriorationPredictionAgent()
simulation_agent = SimulationAgent()
clinical_evidence_agent = ClinicalEvidenceAgent()
clinical_context_agent = ClinicalContextAgent()
explanation_agent = ExplanationAgent()

ONCOTWIN_AGENTS: list[Agent[Any, Any]] = [
    data_quality_agent, twin_state_agent, trajectory_intelligence_agent, temporal_intelligence_agent,
    deterioration_prediction_agent, simulation_agent, clinical_evidence_agent, clinical_context_agent,
    explanation_agent,
]
