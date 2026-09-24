"""Treatment regimens used by the synthetic cohort and the twin's treatment context.

The numeric fields (`myelotox`, `emeto`, `diarrhea`, `fatigue`) are SIMULATION
PARAMETERS on a relative scale — they shape the synthetic physiology. The
`myelo_tier` label is likewise a simulation tier, NOT a restatement of any
guideline's febrile-neutropenia risk category; a real deployment must map
each regimen to the institution's regimen library and the current NCCN
Hematopoietic Growth Factors guideline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"


@dataclass(frozen=True)
class Drug:
    name: str
    rxnorm: str
    route: str = "IV"


@dataclass(frozen=True)
class Regimen:
    code: str
    name: str
    cycle_days: int
    drugs: tuple[Drug, ...]
    myelotox: float          # relative myelosuppressive intensity (simulation)
    emeto: float             # relative emetogenic load (simulation)
    diarrhea: float          # relative diarrhea load (simulation)
    fatigue: float           # relative fatigue load (simulation)
    myelo_tier: str          # "high" | "intermediate" | "low"  (simulation tier)
    oral_days: int = 0       # days of oral agent per cycle (e.g. capecitabine d1-14)
    steroid_premed: bool = True
    tumor_types: tuple[str, ...] = field(default_factory=tuple)

    @property
    def myelo_tier_value(self) -> float:
        return {"high": 1.0, "intermediate": 0.5, "low": 0.0}[self.myelo_tier]


REGIMENS: dict[str, Regimen] = {
    r.code: r
    for r in (
        Regimen(
            code="TCHP", name="Docetaxel + carboplatin + trastuzumab + pertuzumab, q21d",
            cycle_days=21,
            drugs=(Drug("docetaxel", "72962"), Drug("carboplatin", "40048"),
                   Drug("trastuzumab", "224905"), Drug("pertuzumab", "1298944")),
            myelotox=1.0, emeto=0.55, diarrhea=0.35, fatigue=1.0, myelo_tier="intermediate",
            tumor_types=("breast",),
        ),
        Regimen(
            code="DDAC", name="Dose-dense doxorubicin + cyclophosphamide, q14d",
            cycle_days=14,
            drugs=(Drug("doxorubicin", "3639"), Drug("cyclophosphamide", "3002")),
            myelotox=1.35, emeto=0.9, diarrhea=0.1, fatigue=1.1, myelo_tier="high",
            tumor_types=("breast",),
        ),
        Regimen(
            code="CARBO_PACLI", name="Carboplatin + paclitaxel, q21d",
            cycle_days=21,
            drugs=(Drug("carboplatin", "40048"), Drug("paclitaxel", "56946")),
            myelotox=0.85, emeto=0.5, diarrhea=0.1, fatigue=0.9, myelo_tier="intermediate",
            tumor_types=("ovarian", "lung"),
        ),
        Regimen(
            code="CAPOX", name="Capecitabine (d1–14) + oxaliplatin, q21d",
            cycle_days=21,
            drugs=(Drug("oxaliplatin", "32592"), Drug("capecitabine", "194000", route="PO")),
            myelotox=0.35, emeto=0.5, diarrhea=0.9, fatigue=0.8, myelo_tier="low",
            oral_days=14, tumor_types=("colon",),
        ),
        Regimen(
            code="PEMBRO", name="Pembrolizumab monotherapy, q21d",
            cycle_days=21,
            drugs=(Drug("pembrolizumab", "1547545"),),
            myelotox=0.02, emeto=0.05, diarrhea=0.08, fatigue=0.35, myelo_tier="low",
            steroid_premed=False, tumor_types=("lung", "melanoma"),
        ),
    )
}

# Supportive-care drugs referenced by the simulator, interventions and handoff.
SUPPORTIVE: dict[str, Drug] = {
    "ondansetron": Drug("ondansetron", "26225", route="PO"),
    "dexamethasone": Drug("dexamethasone", "3264", route="PO"),
    "pegfilgrastim": Drug("pegfilgrastim", "338036", route="SC"),
    "amoxicillin_clavulanate": Drug("amoxicillin + clavulanate", "19711", route="PO"),
    "ciprofloxacin": Drug("ciprofloxacin", "2551", route="PO"),
    "loperamide": Drug("loperamide", "6468", route="PO"),
    "iv_fluids": Drug("sodium chloride 0.9% (IV fluids)", "313002", route="IV"),
}
