"""AquaHealth controlled vocabulary — the shared terms for every layer.

One module owns the enums so the API, the agents, the FHIR-style export and
the frontend all speak the same words. Nothing here is clinical: this is the
OneAquaHealth freshwater-ecosystem extension and it is deliberately kept
separate from ClinCase's clinical vocabulary.

The most important type here is `Presence`. The OneAquaHealth citizen-science
brief is explicit that a volunteer must never be forced to invent data, so
EVERY qualitative observation field is a four-state Presence rather than a
boolean:

    observed      — the citizen saw it
    not_observed  — the citizen looked and it was absent  (real information!)
    unknown       — the citizen could not tell
    not_available — the citizen did not or could not check

`not_observed` and `unknown` are different facts and the assessment agents
treat them differently: "looked, saw no fish" is evidence, "did not look" is
a data gap. Collapsing them into a boolean would silently manufacture data,
so the distinction is preserved end-to-end.
"""
from __future__ import annotations

from enum import StrEnum


class Presence(StrEnum):
    """Four-state answer for every qualitative observation field."""

    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"
    UNKNOWN = "unknown"
    NOT_AVAILABLE = "not_available"

    @property
    def is_informative(self) -> bool:
        """True when the citizen actually looked (either outcome is evidence)."""
        return self in (Presence.OBSERVED, Presence.NOT_OBSERVED)

    @property
    def is_gap(self) -> bool:
        """True when this field contributes nothing but a data gap."""
        return not self.is_informative


class EcosystemStatus(StrEnum):
    """Prototype Ecosystem Observation Status.

    Deliberately NOT called an index or a score. This is a prototype
    triage signal derived from a handful of citizen observations, not a
    validated environmental index such as WFD ecological status. The UI
    always renders it under the "Prototype Ecosystem Observation Status"
    label with the observations that produced it.
    """

    HEALTHY_SIGNAL = "healthy_signal"
    WATCH = "watch"
    POTENTIAL_STRESS = "potential_stress"
    CRITICAL_SIGNAL = "critical_signal"
    INSUFFICIENT_DATA = "insufficient_data"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataQuality(StrEnum):
    GOOD = "good"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class DataSource(StrEnum):
    """Provenance of an observation. Rendered on every record in the UI."""

    CITIZEN = "citizen_observation"
    SENSOR = "sensor"
    IMPORTED = "imported_dataset"
    DEMO = "demonstration_data"


class VerificationState(StrEnum):
    """How much human scrutiny a record has had."""

    UNVERIFIED = "unverified"
    AI_ASSISTED = "ai_assisted"
    HUMAN_REVIEWED = "human_reviewed"
    VERIFIED = "verified"


class ReviewDecision(StrEnum):
    """Outcome of the human-in-the-loop environmental review."""

    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    MORE_INFO = "more_info_requested"


class ReviewStatus(StrEnum):
    PENDING = "pending_review"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"


# --- Field catalogues --------------------------------------------------------
# These drive both the observation form and the agents, so the form can never
# drift from what the assessment logic actually reads.

WATER_APPEARANCE_FIELDS: tuple[tuple[str, str], ...] = (
    ("floating_waste", "Floating waste or litter"),
    ("foam", "Foam or froth"),
    ("algae", "Algal bloom or green scum"),
    ("oily_film", "Oil-like film or sheen"),
    ("unusual_colour", "Unusual water colour"),
    ("unusual_odour", "Unusual or strong odour"),
)

BIODIVERSITY_FIELDS: tuple[tuple[str, str], ...] = (
    ("fish", "Fish"),
    ("birds", "Water birds"),
    ("insects", "Insects above the water"),
    ("aquatic_plants", "Aquatic plants"),
    ("macroinvertebrates", "Macroinvertebrates (snails, larvae, shrimp)"),
    ("dead_organisms", "Dead fish or other dead organisms"),
    ("unusual_organisms", "Unusual or unfamiliar organisms"),
)

CONTEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("recent_rainfall", "Heavy rainfall in the last 48 hours"),
    ("flooding", "Flooding"),
    ("drought", "Drought or unusually low water"),
    ("construction", "Construction work nearby"),
    ("waste_accumulation", "Waste accumulation on the bank"),
    ("suspected_discharge", "Suspected discharge or outflow pipe"),
    ("unusual_activity", "Other unusual human activity"),
)

#: Fields where OBSERVED is the concerning direction (a pollution-style signal).
ADVERSE_WHEN_OBSERVED: frozenset[str] = frozenset({
    "floating_waste", "foam", "algae", "oily_film", "unusual_colour",
    "unusual_odour", "dead_organisms", "waste_accumulation",
    "suspected_discharge",
})

#: Fields where OBSERVED is a positive/healthy sign (life is present).
POSITIVE_WHEN_OBSERVED: frozenset[str] = frozenset({
    "fish", "birds", "insects", "aquatic_plants", "macroinvertebrates",
})

ALL_QUALITATIVE_FIELDS: tuple[tuple[str, str], ...] = (
    WATER_APPEARANCE_FIELDS + BIODIVERSITY_FIELDS + CONTEXT_FIELDS
)

FIELD_LABELS: dict[str, str] = dict(ALL_QUALITATIVE_FIELDS)
