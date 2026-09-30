"""Reproducible safety evaluation for the AquaHealth Track 3 assessment.

The benchmark is intentionally small and transparent.  It is a collection of
hand-authored boundary cases for the behaviours AquaHealth claims today:

* sparse observations must abstain rather than look healthy;
* adverse signals must be surfaced for review;
* contradictory or implausible inputs must be flagged; and
* the same input must always produce the same result.

It is not an ecological validation study and is never presented as one.  The
cases run through the production assessment functions on every request, so the
reported figures cannot drift away from the code that evaluates observations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.aquahealth import assess
from app.aquahealth.models import (
    Biodiversity,
    EnvironmentalContext,
    Measurements,
    Observation,
    WaterAppearance,
)
from app.aquahealth.vocab import EcosystemStatus, Presence

YES = Presence.OBSERVED
NO = Presence.NOT_OBSERVED
UNK = Presence.UNKNOWN

CONCERNING = {
    EcosystemStatus.WATCH,
    EcosystemStatus.POTENTIAL_STRESS,
    EcosystemStatus.CRITICAL_SIGNAL,
}


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    title: str
    category: str
    expected_status: EcosystemStatus
    observation: Observation
    expected_validation_issue: bool = False


def _observation(
    case_id: str,
    *,
    appearance: WaterAppearance | None = None,
    biodiversity: Biodiversity | None = None,
    context: EnvironmentalContext | None = None,
    measurements: Measurements | None = None,
) -> Observation:
    return Observation(
        id=f"eval-{case_id}",
        reference=f"EVAL-{case_id.upper()}",
        organization_id="aquahealth-evaluation",
        waterbody_id="eval-waterbody",
        waterbody_name="Synthetic benchmark stream",
        observed_at=datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
        appearance=appearance or WaterAppearance(),
        biodiversity=biodiversity or Biodiversity(),
        context=context or EnvironmentalContext(),
        measurements=measurements or Measurements(),
        is_demo=True,
    )


def benchmark_cases() -> list[BenchmarkCase]:
    """Return the versioned, synthetic Track 3 boundary-case benchmark."""
    clean = {
        "floating_waste": NO,
        "foam": NO,
        "algae": NO,
        "oily_film": NO,
        "unusual_colour": NO,
        "unusual_odour": NO,
    }
    return [
        BenchmarkCase(
            "sparse-empty",
            "Empty qualitative observation abstains",
            "abstention",
            EcosystemStatus.INSUFFICIENT_DATA,
            _observation("sparse-empty"),
            True,
        ),
        BenchmarkCase(
            "sparse-one-signal",
            "One concerning answer still abstains",
            "abstention",
            EcosystemStatus.INSUFFICIENT_DATA,
            _observation("sparse-one-signal", appearance=WaterAppearance(foam=YES)),
            True,
        ),
        BenchmarkCase(
            "unknown-is-not-absence",
            "Unknown answers are not treated as reassuring",
            "abstention",
            EcosystemStatus.INSUFFICIENT_DATA,
            _observation(
                "unknown-is-not-absence",
                appearance=WaterAppearance(
                    floating_waste=UNK,
                    foam=UNK,
                    algae=UNK,
                    oily_film=UNK,
                ),
            ),
            True,
        ),
        BenchmarkCase(
            "clean-visual-check",
            "Six checked-and-absent visual signals",
            "baseline",
            EcosystemStatus.HEALTHY_SIGNAL,
            _observation("clean-visual-check", appearance=WaterAppearance(**clean)),
        ),
        BenchmarkCase(
            "biodiversity-present",
            "Multiple biodiversity groups observed",
            "baseline",
            EcosystemStatus.HEALTHY_SIGNAL,
            _observation(
                "biodiversity-present",
                biodiversity=Biodiversity(
                    fish=YES,
                    birds=YES,
                    insects=YES,
                    aquatic_plants=YES,
                    dead_organisms=NO,
                ),
            ),
        ),
        BenchmarkCase(
            "single-foam",
            "One adverse visual signal enters watch",
            "concern-detection",
            EcosystemStatus.WATCH,
            _observation(
                "single-foam",
                appearance=WaterAppearance(**{**clean, "foam": YES}),
            ),
        ),
        BenchmarkCase(
            "high-turbidity",
            "High turbidity enters watch",
            "concern-detection",
            EcosystemStatus.WATCH,
            _observation(
                "high-turbidity",
                appearance=WaterAppearance(**clean),
                measurements=Measurements(turbidity_ntu=150),
            ),
        ),
        BenchmarkCase(
            "three-adverse-signals",
            "Three visual signals indicate potential stress",
            "concern-detection",
            EcosystemStatus.POTENTIAL_STRESS,
            _observation(
                "three-adverse-signals",
                appearance=WaterAppearance(
                    **{
                        **clean,
                        "foam": YES,
                        "oily_film": YES,
                        "unusual_colour": YES,
                    }
                ),
            ),
        ),
        BenchmarkCase(
            "dead-organisms",
            "Dead organisms trigger the conservative critical gate",
            "concern-detection",
            EcosystemStatus.CRITICAL_SIGNAL,
            _observation(
                "dead-organisms",
                appearance=WaterAppearance(**clean),
                biodiversity=Biodiversity(dead_organisms=YES),
            ),
        ),
        BenchmarkCase(
            "acute-combination",
            "Dead organisms plus visual signals is critical",
            "concern-detection",
            EcosystemStatus.CRITICAL_SIGNAL,
            _observation(
                "acute-combination",
                appearance=WaterAppearance(**{**clean, "foam": YES, "oily_film": YES}),
                biodiversity=Biodiversity(dead_organisms=YES),
            ),
        ),
        BenchmarkCase(
            "critical-oxygen",
            "Critical dissolved oxygen is surfaced",
            "concern-detection",
            EcosystemStatus.POTENTIAL_STRESS,
            _observation(
                "critical-oxygen",
                appearance=WaterAppearance(**clean),
                measurements=Measurements(dissolved_oxygen_mgl=2.1),
            ),
        ),
        BenchmarkCase(
            "live-and-dead-fish",
            "Live fish and dead organisms are flagged for confirmation",
            "validation",
            EcosystemStatus.CRITICAL_SIGNAL,
            _observation(
                "live-and-dead-fish",
                appearance=WaterAppearance(**clean),
                biodiversity=Biodiversity(fish=YES, dead_organisms=YES),
            ),
            True,
        ),
        BenchmarkCase(
            "flood-and-drought",
            "Flooding and drought contradiction is flagged",
            "validation",
            EcosystemStatus.HEALTHY_SIGNAL,
            _observation(
                "flood-and-drought",
                appearance=WaterAppearance(**clean),
                context=EnvironmentalContext(flooding=YES, drought=YES),
            ),
            True,
        ),
        BenchmarkCase(
            "implausible-ph",
            "Implausible pH is flagged rather than discarded",
            "validation",
            EcosystemStatus.WATCH,
            _observation(
                "implausible-ph",
                appearance=WaterAppearance(**clean),
                measurements=Measurements(ph=2.5),
            ),
            True,
        ),
    ]


def run_benchmark() -> dict[str, Any]:
    """Execute the current production rules and calculate transparent metrics."""
    rows: list[dict[str, Any]] = []
    exact = 0
    expected_concerning = 0
    detected_concerning = 0
    expected_abstentions = 0
    correct_abstentions = 0
    false_reassurance = 0
    validation_correct = 0

    for case in benchmark_cases():
        predicted, reason, confidence = assess.derive_status(case.observation)
        validation = assess.validate_observation(case.observation)
        validation_issue = bool(validation.evidence) or validation.finding.startswith(
            "Data-quality issues found"
        )
        passed = predicted == case.expected_status
        exact += int(passed)

        if case.expected_status in CONCERNING:
            expected_concerning += 1
            detected_concerning += int(predicted in CONCERNING)
        if case.expected_status == EcosystemStatus.INSUFFICIENT_DATA:
            expected_abstentions += 1
            correct_abstentions += int(predicted == EcosystemStatus.INSUFFICIENT_DATA)
            false_reassurance += int(predicted == EcosystemStatus.HEALTHY_SIGNAL)
        validation_correct += int(validation_issue == case.expected_validation_issue)

        rows.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "category": case.category,
                "expected_status": case.expected_status.value,
                "predicted_status": predicted.value,
                "confidence": confidence.value,
                "status_reason": reason,
                "expected_validation_issue": case.expected_validation_issue,
                "validation_issue_detected": validation_issue,
                "validation_finding": validation.finding,
                "passed": passed and validation_issue == case.expected_validation_issue,
            }
        )

    total = len(rows)
    return {
        "benchmark": "aquahealth.track3.boundary-cases",
        "version": "1.0.0",
        "generated_from": "production assessment functions",
        "synthetic": True,
        "case_count": total,
        "metrics": {
            "exact_status_accuracy": round(exact / total, 4),
            "concern_detection_recall": round(
                detected_concerning / expected_concerning, 4
            ),
            "insufficient_data_abstention_rate": round(
                correct_abstentions / expected_abstentions, 4
            ),
            "validation_check_accuracy": round(validation_correct / total, 4),
            "false_healthy_on_insufficient_count": false_reassurance,
        },
        "counts": {
            "exact_status_matches": exact,
            "expected_concerning": expected_concerning,
            "detected_concerning": detected_concerning,
            "expected_abstentions": expected_abstentions,
            "correct_abstentions": correct_abstentions,
            "validation_expectations_met": validation_correct,
        },
        "limitations": [
            "Synthetic boundary cases test software behaviour, not ecological validity.",
            "Expected labels are developer-authored and have not been independently expert adjudicated.",
            "No metric here establishes safety, diagnostic performance, or public-health validity.",
            "Prospective field evaluation and domain-expert review are required before operational use.",
        ],
        "cases": rows,
    }


def main() -> None:
    """Print a CI- and reviewer-friendly JSON report."""
    print(json.dumps(run_benchmark(), indent=2))


if __name__ == "__main__":
    main()
