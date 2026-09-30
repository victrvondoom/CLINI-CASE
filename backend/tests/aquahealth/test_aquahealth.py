"""AquaHealth module tests.

These cover the behaviours that make the module trustworthy rather than merely
functional. The assertions that matter most are the negative ones: sparse data
must not produce a confident verdict, a trend must not appear before there is
history, and a non-answer must never become evidence.

Everything here runs without a database or LLM credentials — the module is
deterministic and the store falls back to in-process state, matching how
ClinCase itself boots in DB-less mode.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.aquahealth import assess, demo, evaluation, service, store
from app.aquahealth.fhir import mapping
from app.aquahealth.models import (
    Biodiversity,
    EnvironmentalContext,
    Measurements,
    Observation,
    ObservationCreate,
    ReviewRequest,
    WaterAppearance,
)
from app.aquahealth.vocab import (
    Confidence,
    DataQuality,
    DataSource,
    EcosystemStatus,
    Presence,
    ReviewDecision,
    ReviewStatus,
    VerificationState,
)

# Short aliases keep the observation fixtures readable.
YES = Presence.OBSERVED
NO = Presence.NOT_OBSERVED
UNK = Presence.UNKNOWN
SKIP = Presence.NOT_AVAILABLE


@pytest.fixture(autouse=True)
def _clean_stores():
    """Each test gets a fresh in-process store registry."""
    store.reset_stores()
    yield
    store.reset_stores()


def _obs(**kw) -> Observation:
    """Build an Observation directly, bypassing the service."""
    defaults = {
        "reference": "AQUA-000001",
        "organization_id": "org_test",
        "waterbody_id": "wb_test",
        "waterbody_name": "Test Brook",
        "observed_at": datetime.now(UTC),
    }
    defaults.update(kw)
    return Observation(**defaults)


# =============================================================================
# Presence semantics — the core modelling decision
# =============================================================================


def test_presence_distinguishes_absence_from_ignorance():
    """`not_observed` is evidence; `unknown` / `not_available` are gaps."""
    assert Presence.OBSERVED.is_informative
    assert Presence.NOT_OBSERVED.is_informative
    assert not Presence.UNKNOWN.is_informative
    assert not Presence.NOT_AVAILABLE.is_informative
    assert Presence.UNKNOWN.is_gap
    assert Presence.NOT_AVAILABLE.is_gap


def test_unanswered_fields_never_become_evidence():
    """An all-unknown observation must produce no evidence at all."""
    obs = _obs(
        appearance=WaterAppearance(
            floating_waste=UNK,
            foam=UNK,
            algae=UNK,
            oily_film=UNK,
            unusual_colour=UNK,
            unusual_odour=UNK,
        ),
        biodiversity=Biodiversity(fish=SKIP, birds=SKIP, insects=SKIP),
    )
    for finding in (
        assess.assess_water_quality(obs),
        assess.assess_biodiversity(obs),
        assess.assess_context(obs),
    ):
        assert finding.evidence == [], f"{finding.agent} invented evidence from non-answers"


# =============================================================================
# Status derivation — the honesty guarantees
# =============================================================================


def test_sparse_observation_is_insufficient_not_healthy():
    """The dangerous failure would be reading 'no data' as 'no problem'."""
    obs = _obs(biodiversity=Biodiversity(birds=YES))
    status, reason, confidence = assess.derive_status(obs)

    assert status is EcosystemStatus.INSUFFICIENT_DATA
    assert status is not EcosystemStatus.HEALTHY_SIGNAL
    assert confidence is Confidence.LOW
    assert "at least" in reason


def test_clean_well_answered_observation_is_healthy():
    obs = _obs(
        appearance=WaterAppearance(
            floating_waste=NO,
            foam=NO,
            algae=NO,
            oily_film=NO,
            unusual_colour=NO,
            unusual_odour=NO,
            clarity="clear",
        ),
        biodiversity=Biodiversity(
            fish=YES,
            birds=YES,
            insects=YES,
            aquatic_plants=YES,
            macroinvertebrates=YES,
            dead_organisms=NO,
        ),
        measurements=Measurements(ph=7.4, dissolved_oxygen_mgl=8.5, turbidity_ntu=6),
    )
    status, _reason, _conf = assess.derive_status(obs)
    assert status is EcosystemStatus.HEALTHY_SIGNAL


def test_fish_kill_with_multiple_signals_is_critical():
    obs = _obs(
        appearance=WaterAppearance(
            floating_waste=YES,
            foam=YES,
            algae=YES,
            oily_film=YES,
            unusual_colour=YES,
            unusual_odour=YES,
            clarity="opaque",
        ),
        biodiversity=Biodiversity(fish=NO, birds=NO, insects=NO, dead_organisms=YES),
        measurements=Measurements(dissolved_oxygen_mgl=2.2),
    )
    status, reason, _conf = assess.derive_status(obs)
    assert status is EcosystemStatus.CRITICAL_SIGNAL
    assert "dead organisms" in reason


def test_confidence_is_capped_by_data_quality():
    """Sparse data must never yield a HIGH-confidence finding."""
    thin = _obs(
        appearance=WaterAppearance(algae=YES, foam=YES),
        biodiversity=Biodiversity(fish=NO),
    )
    finding = assess.assess_water_quality(thin)
    assert finding.confidence is not Confidence.HIGH
    assert assess.data_quality(thin) is DataQuality.INSUFFICIENT


# =============================================================================
# Trend — never fabricated
# =============================================================================


def test_trend_refuses_below_threshold():
    obs = _obs()
    finding = assess.assess_trend(obs, history=[])
    assert "Insufficient historical observations" in finding.finding
    assert finding.data_quality is DataQuality.INSUFFICIENT
    assert finding.evidence == []


def test_trend_reports_once_history_exists():
    now = datetime.now(UTC)
    history = [
        _obs(
            reference=f"AQUA-00000{i}",
            observed_at=now - timedelta(days=30 - i * 5),
            appearance=WaterAppearance(floating_waste=NO, foam=NO, algae=NO),
        )
        for i in range(1, 4)
    ]
    current = _obs(
        reference="AQUA-000009",
        appearance=WaterAppearance(
            floating_waste=YES,
            foam=YES,
            algae=YES,
            oily_film=YES,
            unusual_odour=YES,
        ),
    )
    finding = assess.assess_trend(current, history=history)
    assert "Insufficient" not in finding.finding
    assert finding.evidence, "a reported trend must cite its history"
    assert "higher than" in finding.finding


# =============================================================================
# One Health — cautious language
# =============================================================================


def test_one_health_never_diagnoses():
    obs = _obs(
        appearance=WaterAppearance(algae=YES, foam=YES, unusual_odour=YES),
        biodiversity=Biodiversity(dead_organisms=YES),
        context=EnvironmentalContext(suspected_discharge=YES),
    )
    finding = assess.assess_one_health(obs)

    assert "Potential relevance" in finding.finding
    assert finding.uncertainty and "not a diagnosis" in finding.uncertainty
    lowered = finding.finding.lower()
    for forbidden in ("causes", "will cause", "diagnos", "outbreak confirmed"):
        assert forbidden not in lowered


def test_one_health_silent_without_a_pathway():
    obs = _obs(
        appearance=WaterAppearance(
            algae=NO,
            foam=NO,
            oily_film=NO,
            unusual_odour=NO,
            floating_waste=NO,
        ),
        biodiversity=Biodiversity(fish=YES, birds=YES, dead_organisms=NO),
    )
    finding = assess.assess_one_health(obs)
    assert "No observation" in finding.finding
    assert finding.uncertainty
    assert "not evidence that no pathway exists" in finding.uncertainty


# =============================================================================
# Validation agent
# =============================================================================


def test_validation_flags_contradiction():
    obs = _obs(
        biodiversity=Biodiversity(fish=YES, dead_organisms=YES, birds=YES, insects=YES),
        appearance=WaterAppearance(algae=NO, foam=NO),
    )
    finding = assess.validate_observation(obs)
    assert "Data-quality issues" in finding.finding
    assert any(e.field == "dead_organisms" for e in finding.evidence)


def test_validation_flags_implausible_ph():
    obs = _obs(
        appearance=WaterAppearance(algae=NO, foam=NO, oily_film=NO, unusual_odour=NO),
        biodiversity=Biodiversity(fish=YES),
        measurements=Measurements(ph=13.8),
    )
    finding = assess.validate_observation(obs)
    assert "plausible field range" in finding.finding


# =============================================================================
# Service: pipeline, review, aggregates
# =============================================================================


async def test_create_observation_runs_all_agents():
    st = store.get_store("org_pipeline")
    obs = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="Pipeline Brook",
            appearance=WaterAppearance(
                algae=YES,
                foam=NO,
                floating_waste=YES,
                unusual_odour=NO,
            ),
            biodiversity=Biodiversity(fish=NO, birds=YES, dead_organisms=NO),
        ),
        observer_id="u1",
        observer_label="Citizen A",
    )

    assert obs.reference.startswith("AQUA-")
    assert obs.assessment is not None
    assert obs.verification is VerificationState.AI_ASSISTED
    assert obs.review_status is ReviewStatus.PENDING

    agents = {f.agent for f in obs.assessment.findings}
    assert agents == {
        "environmental_validation",
        "water_quality",
        "biodiversity",
        "environmental_context",
        "trend",
        "one_health",
    }


async def test_reviewer_modification_overrides_ai_status():
    st = store.get_store("org_review")
    obs = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="Review Brook",
            appearance=WaterAppearance(
                algae=YES,
                foam=YES,
                floating_waste=YES,
                unusual_odour=YES,
                oily_film=YES,
            ),
            biodiversity=Biodiversity(fish=NO, dead_organisms=YES, birds=NO),
        ),
        observer_id="u1",
        observer_label="Citizen A",
    )
    ai_status = obs.assessment.status
    assert ai_status in (
        EcosystemStatus.CRITICAL_SIGNAL,
        EcosystemStatus.POTENTIAL_STRESS,
    )

    updated = await service.apply_review(
        st,
        obs,
        ReviewRequest(
            decision=ReviewDecision.MODIFIED,
            corrected_status=EcosystemStatus.WATCH,
            comment="Field check: algae confirmed, no kill observed.",
        ),
        reviewer_id="r1",
        reviewer_label="Reviewer B",
    )

    # The reviewer wins everywhere a status is reported.
    assert updated.effective_status is EcosystemStatus.WATCH
    assert updated.assessment.status is ai_status  # AI's original call is preserved
    assert updated.verification is VerificationState.HUMAN_REVIEWED
    assert updated.review_status is ReviewStatus.COMPLETED

    overview = service.dashboard(st)
    assert overview.status_distribution.get("watch") == 1
    assert overview.awaiting_review == 0


async def test_request_more_info_keeps_observation_open():
    st = store.get_store("org_moreinfo")
    obs = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="Open Brook",
            appearance=WaterAppearance(algae=YES, foam=NO),
        ),
        observer_id="u1",
        observer_label="Citizen A",
    )
    updated = await service.apply_review(
        st,
        obs,
        ReviewRequest(
            decision=ReviewDecision.MORE_INFO,
            comment="Please photograph the outflow on your next visit.",
        ),
        reviewer_id="r1",
        reviewer_label="Reviewer B",
    )
    assert updated.review_status is ReviewStatus.IN_REVIEW
    assert updated.assessment.human_verification == "required"


async def test_repeat_visits_group_under_one_waterbody():
    """Same name must not create a duplicate site, or history never accrues."""
    st = store.get_store("org_group")
    for _ in range(3):
        await service.create_observation(
            st,
            ObservationCreate(
                waterbody_name="Same Brook",
                appearance=WaterAppearance(algae=NO, foam=NO),
            ),
            observer_id="u1",
            observer_label="Citizen A",
        )
    assert len(st.waterbodies()) == 1
    assert len(st.observations()) == 3


async def test_community_stats_never_touch_assessment():
    """Badges are participation-only; the assessment must be identical."""
    st = store.get_store("org_badges")
    payload = ObservationCreate(
        waterbody_name="Badge Brook",
        appearance=WaterAppearance(algae=YES, foam=NO, floating_waste=NO, unusual_odour=NO),
        biodiversity=Biodiversity(fish=YES, birds=YES, insects=YES),
    )
    first = await service.create_observation(
        st, payload, observer_id="u1", observer_label="Citizen A"
    )
    for _ in range(5):
        await service.create_observation(st, payload, observer_id="u1", observer_label="Citizen A")

    stats = service.community_stats(st, observer_id="u1")
    assert stats.observations_contributed == 6
    assert any(b.code == "water_watcher" and b.earned for b in stats.badges)

    # The sixth observation is assessed exactly like the first.
    latest = st.observations()[0]
    assert latest.assessment.status is first.assessment.status
    assert latest.assessment.confidence is first.assessment.confidence


# =============================================================================
# Demo data
# =============================================================================


async def test_demo_data_is_labelled_and_separable():
    st = store.get_store("org_demo_test")
    result = await demo.seed_demo_data(st)
    assert result["seeded"] is True
    assert result["observations"] > 0

    rows = st.observations()
    assert all(o.is_demo for o in rows)
    assert all(o.source is DataSource.DEMO for o in rows)

    # A real contribution alongside the demo set.
    real = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="Real Brook",
            appearance=WaterAppearance(algae=NO, foam=NO),
        ),
        observer_id="u_real",
        observer_label="Real Citizen",
        is_demo=False,
    )

    removed = st.clear_demo_data()
    assert removed == result["observations"]

    remaining = st.observations()
    assert len(remaining) == 1
    assert remaining[0].id == real.id, "clearing demo data destroyed a real observation"


async def test_demo_seed_is_idempotent():
    st = store.get_store("org_demo_idem")
    first = await demo.seed_demo_data(st)
    second = await demo.seed_demo_data(st)
    assert second["seeded"] is False
    assert len(st.observations()) == first["observations"]


async def test_demo_dataset_spans_statuses_including_insufficient():
    """A demo where everything is confident would misrepresent the system."""
    st = store.get_store("org_demo_spread")
    await demo.seed_demo_data(st)
    statuses = {o.effective_status for o in st.observations()}

    assert EcosystemStatus.INSUFFICIENT_DATA in statuses
    assert EcosystemStatus.HEALTHY_SIGNAL in statuses
    assert len(statuses) >= 3


async def test_demo_triggers_early_warning_on_deteriorating_site():
    st = store.get_store("org_demo_warn")
    await demo.seed_demo_data(st)
    warned = [
        o
        for o in st.observations()
        if o.assessment and o.assessment.early_warning and o.assessment.early_warning.active
    ]
    assert warned, "the deteriorating demo site should raise a prototype warning"
    assert all(
        "not a real-time emergency alert" in o.assessment.early_warning.notice for o in warned
    )


# =============================================================================
# Interoperability
# =============================================================================


async def test_fhir_export_is_structurally_valid_and_honestly_labelled():
    st = store.get_store("org_fhir")
    obs = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="FHIR Brook",
            latitude=45.76,
            longitude=4.83,
            appearance=WaterAppearance(algae=YES, foam=NO, floating_waste=NO),
            biodiversity=Biodiversity(fish=YES, birds=NO),
            measurements=Measurements(ph=7.4, dissolved_oxygen_mgl=8.1),
        ),
        observer_id="u1",
        observer_label="Citizen A",
    )

    resource = mapping.to_fhir_observation(obs)
    assert resource["resourceType"] == "Observation"
    assert resource["status"] in ("preliminary", "final")
    assert resource["effectiveDateTime"]
    assert resource["component"], "measurements and presence fields should map"

    # UCUM units on quantities.
    quantities = [c for c in resource["component"] if "valueQuantity" in c]
    assert quantities
    assert all(q["valueQuantity"]["system"] == "http://unitsofmeasure.org" for q in quantities)

    # The standards claim must be explicit about what this is not.
    tags = [t["display"] for t in resource["meta"]["tag"]]
    assert any("not an official HL7 FHIR profile" in t for t in tags)

    bundle = mapping.to_fhir_bundle([obs])
    assert bundle["resourceType"] == "Bundle"
    assert bundle["total"] == 1


async def test_prototype_export_omits_unanswered_fields():
    st = store.get_store("org_proto")
    obs = await service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="Proto Brook",
            appearance=WaterAppearance(algae=YES, foam=UNK, oily_film=SKIP),
            biodiversity=Biodiversity(fish=NO),
        ),
        observer_id="u1",
        observer_label="Citizen A",
    )
    record = mapping.to_prototype_record(obs)

    codes = {e["code"] for e in record["waterAppearance"]}
    assert "algae" in codes
    assert "foam" not in codes, "an unknown answer was exported as data"
    assert "oily_film" not in codes

    assert record["observationId"] == obs.reference
    assert record["caseType"] == "ENVIRONMENTAL_OBSERVATION"
    assert "not a standard" in record["note"]


# =============================================================================
# Track 3 safety evaluation
# =============================================================================


def test_track3_benchmark_runs_production_logic_and_is_fail_closed():
    report = evaluation.run_benchmark()

    assert report["synthetic"] is True
    assert report["case_count"] >= 12
    assert report["generated_from"] == "production assessment functions"
    assert report["metrics"]["exact_status_accuracy"] == 1.0
    assert report["metrics"]["concern_detection_recall"] == 1.0
    assert report["metrics"]["insufficient_data_abstention_rate"] == 1.0
    assert report["metrics"]["validation_check_accuracy"] == 1.0
    assert report["metrics"]["false_healthy_on_insufficient_count"] == 0
    assert all(case["passed"] for case in report["cases"])


def test_track3_benchmark_discloses_scope_and_limitations():
    report = evaluation.run_benchmark()

    limitations = " ".join(report["limitations"]).lower()
    assert "synthetic" in limitations
    assert "not ecological validity" in limitations
    assert "expert" in limitations
    assert "public-health" in limitations


# =============================================================================
# Coexistence with ClinCase
# =============================================================================


def test_aquahealth_agents_are_not_in_the_clincase_manifest():
    """ClinCase's 7-agent manifest must be unchanged by this module."""
    from app.agents.manifest import AGENT_MANIFEST

    clincase_names = {a["name"] for a in AGENT_MANIFEST}
    aqua_names = {
        "environmental_validation",
        "water_quality",
        "biodiversity",
        "environmental_context",
        "trend",
        "one_health",
        "explanation",
    }
    assert clincase_names.isdisjoint(aqua_names)


def test_aquahealth_routes_do_not_shadow_clincase_routes():
    from app.main import app

    paths = [r.path for r in app.routes if hasattr(r, "path")]
    aqua = [p for p in paths if "/aquahealth" in p]
    assert aqua, "AquaHealth routes should be mounted"
    assert all(p.startswith("/api/v1/aquahealth") for p in aqua)
    assert "/api/v1/aquahealth/evaluation" in aqua

    # The ClinCase surfaces AquaHealth must not disturb.
    for required in ("/api/v1/cases", "/api/v1/agents/manifest", "/api/v1/auth/login"):
        assert any(p.startswith(required) for p in paths), f"{required} disappeared"
