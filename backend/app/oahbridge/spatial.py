"""
Spatial Exposure & Definitional Cohort Engine.
Computes geographic exposure boundaries, buffers, and cohort eligibility criteria.
Note: The semantic bridge performs the GIS computation; FHIR Group (actual=false)
represents the resulting definitional cohort.
"""

from typing import Any

from .models import SpatialExposureZone


def point_in_polygon(point: tuple[float, float], polygon_coords: list[list[float]]) -> bool:
    """
    Standard Ray Casting algorithm for 2D point-in-polygon test.
    point: (longitude, latitude)
    polygon_coords: [[lon1, lat1], [lon2, lat2], ...]
    """
    x, y = point
    inside = False
    n = len(polygon_coords)
    p1x, p1y = polygon_coords[0]

    for i in range(n + 1):
        p2x, p2y = polygon_coords[i % n]
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or x <= xinters:
                inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def evaluate_patient_exposure_intersection(
    patient_coords: tuple[float, float],
    zone: SpatialExposureZone
) -> dict[str, Any]:
    """
    Evaluates whether a patient's authorized location context intersects
    with an active environmental exposure zone.
    """
    coords = zone.geojson_polygon["coordinates"][0]
    intersects = point_in_polygon(patient_coords, coords)

    return {
        "intersects": intersects,
        "site_id": zone.site_id,
        "site_name": zone.site_name,
        "city": zone.city,
        "river_system": zone.river_system,
        "recreational_use_category": zone.recreational_use_category,
        "patient_coordinates": patient_coords
    }


def build_definitional_cohort_characteristics(zone: SpatialExposureZone) -> list[dict[str, Any]]:
    """
    Generates FHIR Group.characteristic criteria for a definitional cohort (actual = false).
    Criteria include:
    1. Geographic boundary reference (Location)
    2. Environmental exposure pathway (Recreational Water Contact)
    """
    return [
        {
            "code": {
                "coding": [
                    {
                        "system": "http://oneaquahealth.eu/fhir/cs/semantic-component",
                        "code": "spatial-exposure-zone",
                        "display": "Spatial Exposure Zone"
                    }
                ]
            },
            "valueReference": {
                "reference": f"Location/{zone.site_id}",
                "display": f"{zone.site_name} Exposure Zone ({zone.city})"
            },
            "exclude": False
        },
        {
            "code": {
                "coding": [
                    {
                        "system": "http://oneaquahealth.eu/fhir/cs/exposure-pathway",
                        "code": "recreational-contact",
                        "display": "Recreational Water Contact"
                    }
                ]
            },
            "valueCodeableConcept": {
                "coding": [
                    {
                        "system": "http://oneaquahealth.eu/fhir/cs/exposure-pathway",
                        "code": "recreational-contact",
                        "display": "Primary or Secondary Recreational Water Contact"
                    }
                ]
            },
            "exclude": False
        }
    ]
