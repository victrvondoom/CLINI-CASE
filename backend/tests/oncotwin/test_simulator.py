"""Synthetic simulator: determinism, archetype behaviour, and past-data invariance."""
from __future__ import annotations

import copy

from app.oncotwin.simulator.archetypes import DEMO_SCRIPTS
from app.oncotwin.simulator.cohort import cohort_script, generate_cohort
from app.oncotwin.simulator.patients import InfectionSeed, simulate


def test_simulation_is_deterministic():
    a = simulate(DEMO_SCRIPTS["ot-001"])
    b = simulate(DEMO_SCRIPTS["ot-001"])
    assert [(o.id, o.value) for o in a.record.observations] == [(o.id, o.value) for o in b.record.observations]
    assert a.truth.event_onsets == b.truth.event_onsets


def test_archetypes_follow_their_stories(demo_sims):
    onsets = {pid: [e["condition"] for e in s.truth.event_onsets] for pid, s in demo_sims.items()}
    assert onsets["ot-001"] == []                              # recovery: intervention averts admission
    assert onsets["ot-002"] == ["dehydration"]                 # gradual deterioration
    assert onsets["ot-003"] == ["febrile_neutropenia"]         # sudden deterioration
    assert onsets["ot-004"] == []                              # stable


def test_intervention_is_what_averts_the_recovery_patients_admission():
    script = copy.deepcopy(DEMO_SCRIPTS["ot-001"])
    script.interventions = []
    counterfactual = simulate(script)
    assert [e["condition"] for e in counterfactual.truth.event_onsets] == ["febrile_neutropenia"]


def test_changing_the_future_never_changes_the_past():
    base = DEMO_SCRIPTS["ot-004"]
    modified = copy.deepcopy(base)
    modified.infection_seeds.append(InfectionSeed(day=40, size=0.3, virulence=0.9))
    a, b = simulate(base).record, simulate(modified).record

    def past(rec):
        return [(o.id, o.value) for o in rec.observations if o.day < 40]

    assert past(a) == past(b)
    assert [(o.id, o.value) for o in a.observations if o.day >= 42] != [(o.id, o.value) for o in b.observations if o.day >= 42]


def test_every_demo_patient_is_labelled_synthetic(demo_sims):
    for sim in demo_sims.values():
        assert sim.record.profile.synthetic is True
        assert "Synthetic" in sim.record.profile.narrative


def test_cohort_generation_is_seeded_and_contains_events():
    a = generate_cohort(25, seed=11)
    b = generate_cohort(25, seed=11)
    assert [s.record.profile.patient_id for s in a] == [s.record.profile.patient_id for s in b]
    assert cohort_script(3, 11).regimen == cohort_script(3, 11).regimen
    assert sum(len(s.truth.event_onsets) for s in generate_cohort(120, seed=5)) > 0
