"""The four scripted demo patients — one per archetype. ALL SYNTHETIC.

Each script fixes only the *drivers* (regimen, sensitivity, when an
infection is seeded, adherence behaviour, clinician interventions, injected
data-quality problems). Everything the twin later shows — when signals
deviate, when a warning fires, how large the risk is — is computed, not
scripted.
"""
from __future__ import annotations

from app.oncotwin.simulator.patients import InfectionSeed, QualityIssue, SimScript

_SYNTH = "Synthetic demonstration patient — not a real person. "

DEMO_SCRIPTS: dict[str, SimScript] = {
    s.patient_id: s
    for s in (
        SimScript(
            patient_id="ot-001", label="OT-001", seed=101, archetype="recovery",
            age=52, sex="female",
            cancer="Invasive ductal carcinoma of right breast", icd10="C50.911",
            stage="IIA (cT2 cN0 M0)",
            biomarkers={"HER2": "IHC 3+ (ISH ratio 5.1)", "ER": "negative", "PR": "negative", "Ki-67": "40%"},
            regimen="TCHP", payer_id="aetna", ecog=0, sensitivity=1.6,
            infection_seeds=[InfectionSeed(day=23, size=0.10, virulence=0.2)],
            interventions=[(28, "urgent_eval_abx"), (28, "gcsf"), (28, "gcsf_secondary")],
            extra_lab_days=[21],
            narrative=_SYNTH + (
                "Neoadjuvant TCHP from Day 14. During the cycle-1 neutrophil nadir a low-grade "
                "infection develops; temperature, resting HR and HRV drift from her personal "
                "baseline days before any population threshold is crossed. After the twin's early "
                "warning she is seen urgently on Day 28, started on empiric oral antibiotics and "
                "G-CSF, and recovers; cycle 2 proceeds with pegfilgrastim secondary prophylaxis."
            ),
        ),
        SimScript(
            patient_id="ot-002", label="OT-002", seed=202, archetype="gradual_deterioration",
            age=71, sex="male",
            cancer="Adenocarcinoma of sigmoid colon", icd10="C18.7",
            stage="III (pT3 pN1b M0)",
            biomarkers={"MMR": "proficient (pMMR / MSS)", "KRAS": "G12D", "BRAF": "wild-type"},
            regimen="CAPOX", payer_id="aetna", ecog=1, diabetic=True, gi_sensitivity=1.35,
            comorbidities=[
                {"icd10": "E11.9", "display": "Type 2 diabetes mellitus without complications"},
                {"icd10": "I10", "display": "Essential (primary) hypertension"},
            ],
            adherence_plan=[(1, 0.95), (19, 0.55), (22, 0.25)],
            quality_issues=[QualityIssue(kind="conflict", day=24)],
            narrative=_SYNTH + (
                "Adjuvant CAPOX from Day 14. Capecitabine-associated diarrhea builds while "
                "supportive-medication adherence quietly falls. Weight, blood pressure, activity "
                "and symptoms drift together over a week — a gradual, multi-signal trajectory. "
                "No intervention is recorded in this synthetic history, so it ends in an admission "
                "for dehydration: the twin's what-if simulator shows what earlier action could change."
            ),
        ),
        SimScript(
            patient_id="ot-003", label="OT-003", seed=303, archetype="sudden_deterioration",
            age=59, sex="female",
            cancer="High-grade serous carcinoma of ovary", icd10="C56.9",
            stage="IIIC",
            biomarkers={"BRCA1/2": "wild-type (germline)", "HRD": "negative"},
            regimen="CARBO_PACLI", payer_id="aetna", ecog=1, sensitivity=1.3,
            infection_seeds=[InfectionSeed(day=25, size=0.45, virulence=0.6)],
            narrative=_SYNTH + (
                "Carboplatin/paclitaxel from Day 14. Stable through the early nadir, then an "
                "aggressive infection progresses within ~36 hours. Sudden deterioration leaves "
                "little lead time — an honest limit of any early-warning system."
            ),
        ),
        SimScript(
            patient_id="ot-004", label="OT-004", seed=404, archetype="stable",
            age=64, sex="male",
            cancer="Adenocarcinoma of right upper lobe of lung", icd10="C34.11",
            stage="IVA",
            biomarkers={"PD-L1": "TPS 80%", "EGFR": "negative", "ALK": "negative"},
            regimen="PEMBRO", payer_id="aetna", ecog=1,
            isolated_blips=[(19, {"sleep_hours": -2.6, "resting_hr": 4.0})],
            quality_issues=[
                QualityIssue(kind="gap", day=30, n_days=2),
                QualityIssue(kind="conflict", day=35),
                QualityIssue(kind="stuck", day=40, n_days=4, signal="spo2"),
                QualityIssue(kind="implausible", day=45, signal="resting_hr"),
            ],
            narrative=_SYNTH + (
                "First-line pembrolizumab from Day 14; physiologically stable. One poor night's "
                "sleep (Day 19) is correctly treated as an isolated deviation, not a trajectory. "
                "The record also carries realistic data problems — a 2-day watch gap, a "
                "clinic-vs-home weight conflict, a stuck SpO₂ sensor and an artefactual heart "
                "rate — which the data-quality engine detects and discounts."
            ),
        ),
        # ---- OncoTwin 2.0 archetypes ------------------------------------------------
        SimScript(
            patient_id="ot-005", label="OT-005", seed=505, archetype="closed_loop",
            age=63, sex="male",
            cancer="Adenocarcinoma of left lower lobe of lung", icd10="C34.32", stage="IIIA (pT3 pN1 M0)",
            biomarkers={"EGFR": "negative", "ALK": "negative", "PD-L1": "TPS 5%"},
            regimen="CARBO_PACLI", payer_id="aetna", ecog=1, sensitivity=1.5,
            infection_seeds=[InfectionSeed(day=22, size=0.10, virulence=0.25)],
            extra_lab_days=[21],
            narrative=_SYNTH + (
                "The flagship closed-loop patient. Adjuvant carboplatin/paclitaxel from Day 14. A low-grade infection "
                "starts in the cycle-1 nadir; HRV, sleep and activity fall and symptoms rise against his own baseline. "
                "NO clinician action is scripted: what happens next depends on the intervention the reviewing "
                "clinician records. Without one, the synthetic patient is admitted with febrile neutropenia on Day 28."
            ),
        ),
        SimScript(
            patient_id="ot-006", label="OT-006", seed=606, archetype="delayed_deterioration",
            age=67, sex="female",
            cancer="Adenocarcinoma of rectum", icd10="C20", stage="III (ypT3 ypN1 M0)",
            biomarkers={"MMR": "proficient (pMMR / MSS)", "KRAS": "wild-type", "BRAF": "wild-type"},
            regimen="CAPOX", payer_id="aetna", ecog=1,
            gi_insults=[(38, 0.45, 5)], adherence_plan=[(1, 0.95), (36, 0.4)],
            narrative=_SYNTH + (
                "Adjuvant CAPOX. Cycle 1 is uneventful; in cycle 2 a GI illness and a fall in antidiarrheal "
                "adherence produce a delayed, multi-signal volume-depletion trajectory."
            ),
        ),
        SimScript(
            patient_id="ot-007", label="OT-007", seed=707, archetype="relapse",
            age=47, sex="female",
            cancer="Invasive ductal carcinoma of left breast", icd10="C50.912", stage="IIB (cT2 cN1 M0)",
            biomarkers={"HER2": "IHC 3+ (ISH ratio 4.4)", "ER": "positive", "PR": "negative", "Ki-67": "35%"},
            regimen="TCHP", payer_id="aetna", ecog=0, sensitivity=1.5,
            infection_seeds=[InfectionSeed(day=22, size=0.12, virulence=0.25),
                             InfectionSeed(day=31, size=0.30, virulence=0.7)],
            interventions=[(26, "urgent_eval_abx"), (26, "gcsf")],
            extra_lab_days=[21],
            narrative=_SYNTH + (
                "Neoadjuvant TCHP. A cycle-1 nadir infection is treated on Day 26 and she recovers to baseline — then "
                "a relapse-like deterioration develops in the cycle-2 nadir. Twin Memory compares the two cycles."
            ),
        ),
        SimScript(
            patient_id="ot-008", label="OT-008", seed=808, archetype="noisy_sensor_missing_data",
            age=69, sex="female",
            cancer="High-grade serous carcinoma of ovary", icd10="C56.9", stage="IIIB",
            biomarkers={"BRCA1/2": "wild-type (germline)", "HRD": "positive"},
            regimen="CARBO_PACLI", payer_id="aetna", ecog=1, sensitivity=0.85,
            missing_wear=0.3, missing_temp=0.35, missing_home=0.5, missing_pro=0.55,
            quality_issues=[
                QualityIssue(kind="stuck", day=24, n_days=5, signal="resting_hr"),
                QualityIssue(kind="implausible", day=27, signal="temperature"),
                QualityIssue(kind="gap", day=29, n_days=3),
                QualityIssue(kind="conflict", day=31),
            ],
            narrative=_SYNTH + (
                "Carboplatin/paclitaxel; physiologically stable, but the watch is often off, home readings are sparse, "
                "the heart-rate sensor sticks and a thermometer artefact appears. The twin reports reduced reliability "
                "instead of false reassurance."
            ),
        ),
    )
}

# Twin clock (as-of day) each demo patient starts at, so the hub shows a spread
# of live states. Advancing the clock replays the synthetic feed day by day.
DEMO_START_DAY: dict[str, int] = {"ot-001": 22, "ot-002": 26, "ot-003": 25, "ot-004": 46,
                                  "ot-005": 20, "ot-006": 32, "ot-007": 36, "ot-008": 31}
FLAGSHIP_PATIENT = "ot-005"
