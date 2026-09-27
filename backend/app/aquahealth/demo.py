"""AquaHealth demonstration dataset — synthetic, clearly labelled, separable.

Every record this module creates carries `is_demo=True` and
`source=DataSource.DEMO`, so the UI can badge it "DEMO DATA" everywhere and
`OrgAquaStore.clear_demo_data()` can remove exactly these rows without
touching a single real citizen contribution.

The data is invented. It is shaped to make the dashboard, map and trends
meaningful — one recovering site, one stable healthy site, one deteriorating
site whose repeated-signal pattern legitimately triggers the prototype early
warning, and one sparse site that correctly resolves to INSUFFICIENT_DATA.
That last one is deliberate: a demo where every record produces a confident
verdict would misrepresent how the system behaves on real, patchy citizen data.

Coordinates are real urban freshwater locations so the map looks plausible,
but no measurement here was ever taken from those waters.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.aquahealth import service, store
from app.aquahealth.models import (
    Biodiversity,
    EnvironmentalContext,
    Measurements,
    ObservationCreate,
    PhotoAILabel,
    PhotoEvidence,
    WaterAppearance,
)
from app.aquahealth.vocab import Confidence, DataSource, Presence

# Short aliases keep the observation script below readable as a table.
YES = Presence.OBSERVED
NO = Presence.NOT_OBSERVED
UNK = Presence.UNKNOWN
SKIP = Presence.NOT_AVAILABLE

DEMO_BANNER = (
    "DEMO DATA — synthetic observations generated for demonstration. These are "
    "not real environmental measurements and must never be cited as such."
)


def _days_ago(days: int, hour: int = 9) -> datetime:
    return (datetime.now(UTC) - timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


#: Four demo sites. `slug` is only used to build the seed script below.
DEMO_WATERBODIES: tuple[dict[str, Any], ...] = (
    {
        "slug": "riverside-brook",
        "name": "Riverside Brook (DEMO)",
        "kind": "stream",
        "locality": "Riverside district",
        "latitude": 45.7640,
        "longitude": 4.8357,
    },
    {
        "slug": "city-park-pond",
        "name": "City Park Pond (DEMO)",
        "kind": "pond",
        "locality": "Central park",
        "latitude": 45.7702,
        "longitude": 4.8590,
    },
    {
        "slug": "mill-canal",
        "name": "Old Mill Canal (DEMO)",
        "kind": "canal",
        "locality": "Industrial quarter",
        "latitude": 45.7515,
        "longitude": 4.8420,
    },
    {
        "slug": "north-wetland",
        "name": "North Wetland Edge (DEMO)",
        "kind": "wetland",
        "locality": "Northern fringe",
        "latitude": 45.7889,
        "longitude": 4.8175,
    },
)

_WB_BY_SLUG = {w["slug"]: w for w in DEMO_WATERBODIES}


def _obs(
    slug: str,
    days: int,
    *,
    appearance: WaterAppearance,
    biodiversity: Biodiversity,
    context: EnvironmentalContext | None = None,
    measurements: Measurements | None = None,
    note: str | None = None,
    photos: list[PhotoEvidence] | None = None,
) -> ObservationCreate:
    wb = _WB_BY_SLUG[slug]
    return ObservationCreate(
        waterbody_name=wb["name"],
        waterbody_kind=wb["kind"],
        locality=wb["locality"],
        latitude=wb["latitude"],
        longitude=wb["longitude"],
        observed_at=_days_ago(days),
        observer_note=note,
        appearance=appearance,
        biodiversity=biodiversity,
        context=context or EnvironmentalContext(),
        measurements=measurements or Measurements(),
        photos=photos or [],
        source=DataSource.DEMO,
    )


def _demo_photo(
    filename: str, caption: str, labels: list[tuple[str, Confidence]]
) -> PhotoEvidence:
    """A photo record with AI-assisted candidate labels and no image bytes.

    `uri` stays None: the demo ships metadata only, so nothing here can be
    mistaken for a real photograph of a real waterbody.
    """
    return PhotoEvidence(
        filename=filename,
        caption=caption,
        size_bytes=0,
        uri=None,
        ai_labels=[
            PhotoAILabel(
                label=label,
                confidence=conf,
                note="Candidate label from image interpretation; not confirmed.",
            )
            for label, conf in labels
        ],
        human_confirmed=None,
    )


def _build_script() -> list[ObservationCreate]:
    """The demo observation script.

    Site narratives:
      • Old Mill Canal — deteriorating: repeated adverse observations build to
        a fish-kill report, which drives the early-warning panel.
      • Riverside Brook — recovering: early litter/foam signals fade as
        biodiversity returns.
      • City Park Pond — stable and healthy, with instrument readings.
      • North Wetland Edge — a single sparse drive-by observation, which must
        resolve to INSUFFICIENT_DATA rather than "healthy".
    """
    script: list[ObservationCreate] = []

    # --- Riverside Brook: recovering -------------------------------------
    script += [
        _obs(
            "riverside-brook", 68,
            appearance=WaterAppearance(
                floating_waste=YES, foam=YES, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=YES, clarity="cloudy",
            ),
            biodiversity=Biodiversity(
                fish=NO, birds=YES, insects=NO, aquatic_plants=YES,
                macroinvertebrates=NO, dead_organisms=NO,
            ),
            context=EnvironmentalContext(
                recent_rainfall=YES, waste_accumulation=YES, construction=NO,
            ),
            measurements=Measurements(ph=7.9, turbidity_ntu=48, dissolved_oxygen_mgl=5.4),
            note="Litter caught on the bank after the weekend. Water looked murky.",
        ),
        _obs(
            "riverside-brook", 47,
            appearance=WaterAppearance(
                floating_waste=YES, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="slightly_cloudy",
            ),
            biodiversity=Biodiversity(
                fish=NO, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=NO, dead_organisms=NO,
            ),
            context=EnvironmentalContext(waste_accumulation=YES, recent_rainfall=NO),
            measurements=Measurements(ph=7.6, turbidity_ntu=22, dissolved_oxygen_mgl=6.2),
            note="Council cleared part of the bank. Fewer bottles than last month.",
        ),
        _obs(
            "riverside-brook", 24,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="clear",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO, unusual_organisms=NO,
            ),
            context=EnvironmentalContext(recent_rainfall=NO, waste_accumulation=NO),
            measurements=Measurements(
                ph=7.4, water_temperature_c=14.5, turbidity_ntu=9, dissolved_oxygen_mgl=8.4
            ),
            note="Small fish visible near the footbridge. Best it has looked all year.",
        ),
        _obs(
            "riverside-brook", 6,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="clear",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO, unusual_organisms=NO,
            ),
            context=EnvironmentalContext(
                recent_rainfall=NO, construction=NO, waste_accumulation=NO, drought=NO,
            ),
            measurements=Measurements(
                ph=7.5, water_temperature_c=15.1, turbidity_ntu=7, dissolved_oxygen_mgl=8.8
            ),
            note="Clear water, plenty of insect activity.",
        ),
    ]

    # --- City Park Pond: stable and healthy ------------------------------
    script += [
        _obs(
            "city-park-pond", 55,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="clear",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO,
            ),
            context=EnvironmentalContext(recent_rainfall=NO, drought=NO, construction=NO),
            measurements=Measurements(
                ph=7.3, water_temperature_c=16.0, turbidity_ntu=6, dissolved_oxygen_mgl=8.9
            ),
            note="Ducks and dragonflies as usual.",
        ),
        _obs(
            "city-park-pond", 33,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="clear",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO, unusual_organisms=NO,
            ),
            measurements=Measurements(
                ph=7.4, water_temperature_c=18.4, turbidity_ntu=8, dissolved_oxygen_mgl=8.1
            ),
        ),
        _obs(
            "city-park-pond", 17,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=YES, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="slightly_cloudy",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO,
            ),
            context=EnvironmentalContext(recent_rainfall=NO, drought=YES),
            measurements=Measurements(
                ph=7.7, water_temperature_c=24.2, turbidity_ntu=14, dissolved_oxygen_mgl=6.6
            ),
            note="Some green film in the shallow corner during the warm spell.",
            photos=[
                _demo_photo(
                    "pond-corner.jpg",
                    "Green film at the shallow edge (DEMO — no image attached)",
                    [("visible algae", Confidence.MEDIUM), ("aquatic vegetation", Confidence.LOW)],
                )
            ],
        ),
        _obs(
            "city-park-pond", 4,
            appearance=WaterAppearance(
                floating_waste=NO, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="clear",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=YES,
                macroinvertebrates=YES, dead_organisms=NO,
            ),
            measurements=Measurements(
                ph=7.3, water_temperature_c=17.1, turbidity_ntu=7, dissolved_oxygen_mgl=8.6
            ),
            note="Algae cleared after the cooler week.",
        ),
    ]

    # --- Old Mill Canal: deteriorating -> early warning -------------------
    script += [
        _obs(
            "mill-canal", 40,
            appearance=WaterAppearance(
                floating_waste=YES, foam=NO, algae=NO, oily_film=NO,
                unusual_colour=NO, unusual_odour=NO, clarity="slightly_cloudy",
            ),
            biodiversity=Biodiversity(
                fish=YES, birds=YES, insects=YES, aquatic_plants=NO, dead_organisms=NO,
            ),
            context=EnvironmentalContext(construction=YES, waste_accumulation=NO),
            measurements=Measurements(ph=7.5, turbidity_ntu=18, dissolved_oxygen_mgl=7.2),
            note="Building work started on the far bank.",
        ),
        _obs(
            "mill-canal", 26,
            appearance=WaterAppearance(
                floating_waste=YES, foam=YES, algae=NO, oily_film=NO,
                unusual_colour=YES, unusual_odour=NO, clarity="cloudy",
            ),
            biodiversity=Biodiversity(
                fish=NO, birds=YES, insects=YES, aquatic_plants=NO,
                macroinvertebrates=NO, dead_organisms=NO,
            ),
            context=EnvironmentalContext(
                construction=YES, waste_accumulation=YES, recent_rainfall=YES,
            ),
            measurements=Measurements(ph=7.8, turbidity_ntu=76, dissolved_oxygen_mgl=5.6),
            note="Water looks browner than usual and there is foam by the lock.",
        ),
        _obs(
            "mill-canal", 14,
            appearance=WaterAppearance(
                floating_waste=YES, foam=YES, algae=YES, oily_film=YES,
                unusual_colour=YES, unusual_odour=YES, clarity="opaque",
            ),
            biodiversity=Biodiversity(
                fish=NO, birds=NO, insects=NO, aquatic_plants=NO,
                macroinvertebrates=NO, dead_organisms=NO, unusual_organisms=NO,
            ),
            context=EnvironmentalContext(
                construction=YES, waste_accumulation=YES, suspected_discharge=YES,
                recent_rainfall=NO,
            ),
            measurements=Measurements(
                ph=8.9, water_temperature_c=21.0, turbidity_ntu=140, dissolved_oxygen_mgl=4.1
            ),
            note="Strong smell near the outflow pipe. No birds on the water today.",
            photos=[
                _demo_photo(
                    "canal-outflow.jpg",
                    "Discolouration near the outflow (DEMO — no image attached)",
                    [
                        ("foam", Confidence.HIGH),
                        ("unusual water colour", Confidence.MEDIUM),
                        ("oil-like sheen", Confidence.LOW),
                    ],
                )
            ],
        ),
        _obs(
            "mill-canal", 3,
            appearance=WaterAppearance(
                floating_waste=YES, foam=YES, algae=YES, oily_film=YES,
                unusual_colour=YES, unusual_odour=YES, clarity="opaque",
            ),
            biodiversity=Biodiversity(
                fish=NO, birds=NO, insects=NO, aquatic_plants=NO,
                macroinvertebrates=NO, dead_organisms=YES, unusual_organisms=NO,
            ),
            context=EnvironmentalContext(
                construction=YES, waste_accumulation=YES, suspected_discharge=YES,
                recent_rainfall=NO, unusual_activity=YES,
            ),
            measurements=Measurements(
                ph=9.2, water_temperature_c=22.4, turbidity_ntu=190, dissolved_oxygen_mgl=2.6
            ),
            note="Several dead fish near the bank. Smell much stronger than before.",
            photos=[
                _demo_photo(
                    "canal-bank.jpg",
                    "Dead fish near the bank (DEMO — no image attached)",
                    [("dead organisms", Confidence.HIGH), ("foam", Confidence.MEDIUM)],
                )
            ],
        ),
    ]

    # --- North Wetland Edge: deliberately sparse --------------------------
    script.append(
        _obs(
            "north-wetland", 9,
            appearance=WaterAppearance(
                floating_waste=UNK, foam=SKIP, algae=UNK, oily_film=SKIP,
                unusual_colour=SKIP, unusual_odour=SKIP, clarity="unknown",
            ),
            biodiversity=Biodiversity(birds=YES),
            note="Walked past quickly, only had time to note the herons.",
        )
    )

    return script


async def seed_demo_data(
    org_store: store.OrgAquaStore,
    *,
    observer_id: str | None = "demo_observer",
    observer_label: str | None = "Demo Citizen Observer",
    force: bool = False,
) -> dict[str, Any]:
    """Seed the demo dataset into one organisation's store.

    Idempotent by default: if demo rows already exist it returns without
    duplicating them. `force=True` clears the existing demo rows first, which
    still never touches real observations.
    """
    if org_store.demo_seeded and not force:
        existing = [o for o in org_store.observations() if o.is_demo]
        return {
            "seeded": False,
            "reason": "Demo data already present.",
            "observations": len(existing),
            "waterbodies": len([w for w in org_store.waterbodies() if w.is_demo]),
            "banner": DEMO_BANNER,
        }

    if force:
        org_store.clear_demo_data()

    created = 0
    for payload in _build_script():
        await service.create_observation(
            org_store,
            payload,
            observer_id=observer_id,
            observer_label=observer_label,
            is_demo=True,
        )
        created += 1

    org_store.demo_seeded = True
    return {
        "seeded": True,
        "observations": created,
        "waterbodies": len([w for w in org_store.waterbodies() if w.is_demo]),
        "banner": DEMO_BANNER,
    }


def clear_demo_data(org_store: store.OrgAquaStore) -> dict[str, Any]:
    """Remove every demo row, leaving real citizen observations untouched."""
    removed = org_store.clear_demo_data()
    return {"cleared": True, "observations_removed": removed}
