"""OAH-Bridge API — the OneAquaHealth semantic decision layer behind the globe page.

Mounted at /api/v1/oah-bridge. Purely additive: its own module (app/oahbridge) and its own
routes; no existing route changes. It serves:

  • the synthetic demonstration scenarios and their exposure zones (globe pins);
  • the 8-step decision chain with real per-stage timings and the 6-tier validation;
  • FHIR R4 search over the composed Bundle, with the OAH custom search parameters;
  • CDS Hooks 1.0 discovery and the informational patient-view exposure advisory;
  • the conformance pack and the pinned SNOMED CT terminology manifest;
  • live weather context for a point (Open-Meteo, proxied, cached, freshness-labelled;
    coordinates arrive in a POST body so they stay out of access logs);
  • a live system monitor.

Every route requires a signed-in user, like AquaHealth, so the weather proxy is not an
open relay. The engine and conformance pack are ported from OneAquaHealth-Bridge
(MIT; see app/oahbridge/LICENSE-OAH-BRIDGE).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import get_current_user
from app.oahbridge import service, weather

router = APIRouter(
    prefix="/oah-bridge",
    tags=["oah-bridge"],
    dependencies=[Depends(get_current_user)],
)

SCENARIO_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
RESOURCE_TYPE_PATTERN = r"^[A-Z][A-Za-z]{1,40}$"
FHIR_JSON = "application/fhir+json"


def _fhir_base(request: Request) -> str:
    """Absolute base of this router's FHIR endpoints, wherever the router is mounted."""
    return str(request.url_for("oahbridge_fhir_metadata")).rsplit("/metadata", 1)[0]


def _unknown(scenario_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"Unknown scenario '{scenario_id}'. Available: {', '.join(service.SCENARIOS)}.",
    )


# ---------------------------------------------------------------------------
# Scenarios and the decision chain
# ---------------------------------------------------------------------------


@router.get("/scenarios")
async def list_scenarios() -> list[dict[str, Any]]:
    return service.list_scenarios()


class RunRequest(BaseModel):
    scenario: str = Field(default=service.DEFAULT_SCENARIO, pattern=SCENARIO_PATTERN)


def _run(scenario_id: str, request: Request) -> dict[str, Any]:
    try:
        return service.run_pipeline(scenario_id, fhir_base=_fhir_base(request))
    except service.UnknownScenarioError:
        raise _unknown(scenario_id) from None


@router.get("/demo/run")
async def demo_run(
    request: Request,
    scenario: str = Query(default=service.DEFAULT_SCENARIO, pattern=SCENARIO_PATTERN),
) -> dict[str, Any]:
    return _run(scenario, request)


@router.post("/demo/run")
async def demo_run_post(request: Request, body: RunRequest | None = None) -> dict[str, Any]:
    return _run((body or RunRequest()).scenario, request)


# ---------------------------------------------------------------------------
# FHIR R4
# ---------------------------------------------------------------------------


@router.get("/fhir/metadata", name="oahbridge_fhir_metadata")
async def capability_statement(request: Request) -> JSONResponse:
    return JSONResponse(service.capability_statement(fhir_base=_fhir_base(request)), media_type=FHIR_JSON)


@router.get("/fhir/{resource_type}")
async def fhir_search(
    request: Request,
    resource_type: str = Path(pattern=RESOURCE_TYPE_PATTERN),
    scenario: str = Query(default=service.DEFAULT_SCENARIO, pattern=SCENARIO_PATTERN),
    oah_hazard: str | None = Query(default=None, alias="oah-hazard", max_length=80),
    oah_location: str | None = Query(default=None, alias="oah-location", max_length=120),
) -> JSONResponse:
    try:
        result = service.fhir_search(
            resource_type,
            scenario,
            hazard=oah_hazard,
            location=oah_location,
            fhir_base=_fhir_base(request),
        )
    except service.UnknownScenarioError:
        raise _unknown(scenario) from None
    return JSONResponse(result, media_type=FHIR_JSON)


# ---------------------------------------------------------------------------
# CDS Hooks 1.0 (patient-view; informational, never diagnostic)
# ---------------------------------------------------------------------------


class CdsContext(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # CDS Hooks field names are camelCase on the wire.
    patient_id: str | None = Field(default=None, alias="patientId", max_length=128)
    user_id: str | None = Field(default=None, alias="userId", max_length=128)
    # OAH-Bridge extension: the patient's authorised location context, [longitude, latitude].
    coordinates: list[float] | None = None

    @field_validator("coordinates")
    @classmethod
    def _valid_coordinates(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 2:
            raise ValueError("coordinates must be [longitude, latitude]")
        lon, lat = value
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("coordinates out of range: longitude ±180, latitude ±90")
        return value


class CdsRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    hook: str = Field(default="patient-view", max_length=64)
    hook_instance: str | None = Field(default=None, alias="hookInstance", max_length=128)
    scenario: str = Field(default=service.DEFAULT_SCENARIO, pattern=SCENARIO_PATTERN)
    context: CdsContext = Field(default_factory=CdsContext)

    @field_validator("hook")
    @classmethod
    def _patient_view_only(cls, value: str) -> str:
        if value != "patient-view":
            raise ValueError("this service is registered for the patient-view hook only")
        return value


@router.get("/cds-services")
async def cds_discovery() -> dict[str, Any]:
    return service.cds_discovery()


@router.post("/cds-services/oah-exposure-advisory")
async def cds_exposure_advisory(request: Request, body: CdsRequest | None = None) -> dict[str, Any]:
    payload = body or CdsRequest()
    coords = payload.context.coordinates
    try:
        return service.evaluate_exposure_advisory(
            payload.scenario,
            (coords[0], coords[1]) if coords is not None else None,
            fhir_base=_fhir_base(request),
        )
    except service.UnknownScenarioError:
        raise _unknown(payload.scenario) from None


# ---------------------------------------------------------------------------
# Conformance, terminology, weather, monitor
# ---------------------------------------------------------------------------


@router.get("/conformance")
async def conformance() -> dict[str, Any]:
    return service.conformance_items()


@router.get("/terminology")
async def terminology() -> dict[str, Any]:
    return service.terminology_manifest()


class WeatherRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@router.post("/weather")
async def weather_context(body: WeatherRequest) -> dict[str, Any]:
    """Weather context for a point.

    POST rather than GET so the coordinates travel in the body and stay out of web-server
    access logs. They are rounded to ~1 km before reaching Open-Meteo.
    """
    try:
        return await weather.get_weather(body.latitude, body.longitude)
    except weather.InvalidCoordinatesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/monitor")
async def monitor() -> dict[str, Any]:
    return service.monitor_snapshot()
