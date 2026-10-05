"""Live weather context for the globe: Open-Meteo forecast API (keyless, CC BY 4.0).

Weather is *context*, never evidence of a hazard, an exposure or an illness. Every response
says where it came from and how fresh it is, in this order of preference:

    live         fetched from Open-Meteo for this request
    cached       served from the in-process cache (age stated; `stale` when upstream failed)
    unavailable  upstream failed and nothing usable is cached

Nothing is ever synthesised and presented as live.

Privacy: the browser coarsens coordinates to about 1 km before sending them, the router
takes them in a POST body (so they stay out of access logs), they are rounded again to
0.01 degrees before reaching Open-Meteo, and this module never logs them.
"""

from __future__ import annotations

import ssl
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import certifi
import httpx
import structlog

log = structlog.get_logger()

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE = "Open-Meteo Forecast API (open-meteo.com)"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
TIMEOUT_S = 6.0
FRESH_TTL_S = 600.0  # serve from cache without calling upstream
STALE_MAX_S = 6 * 3600.0  # on upstream failure, serve cached data up to this age, flagged stale
MAX_CACHE_ENTRIES = 256
FORECAST_HOURS = 48

CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,"
    "weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,is_day"
)
HOURLY_VARS = (
    "temperature_2m,precipitation,precipitation_probability,weather_code,"
    "cloud_cover,wind_speed_10m,wind_direction_10m,is_day"
)
DAILY_VARS = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"

# Context thresholds. Heuristics for surfacing context next to evidence, not alert rules.
HEAVY_RAIN_24H_MM = 20.0
WARM_AIR_C = 25.0
DRY_7D_MM = 5.0
MILD_AIR_C = 20.0

CONTEXT_CAVEAT = (
    "Context only: not evidence of a hazard, an exposure or an illness. "
    "Uses air temperature, not water temperature."
)

# WMO weather interpretation codes, as documented by Open-Meteo.
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class InvalidCoordinatesError(ValueError):
    """Latitude/longitude missing, non-finite or out of range."""


def round_coords(lat: float, lon: float) -> tuple[float, float]:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError) as exc:
        raise InvalidCoordinatesError("latitude and longitude must be numbers") from exc
    if not (lat_f == lat_f and lon_f == lon_f) or abs(lat_f) > 90 or abs(lon_f) > 180:
        raise InvalidCoordinatesError("latitude must be within ±90 and longitude within ±180")
    return round(lat_f, 2), round(lon_f, 2)


def describe(code: Any) -> str:
    try:
        return WMO_CODES.get(int(code), "Unknown conditions")
    except (TypeError, ValueError):
        return "Unknown conditions"


def _parse_local(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _utc_iso(local: datetime | None, offset_s: int) -> str | None:
    if local is None:
        return None
    return (local - timedelta(seconds=offset_s)).replace(tzinfo=UTC).isoformat()


def _at(series: dict[str, Any], key: str, i: int) -> Any:
    values = series.get(key) or []
    return values[i] if i < len(values) else None


def context_signals(
    temperature_c: float | None, rain_24h: float | None, rain_7d: float | None
) -> list[dict[str, Any]]:
    """Weather patterns worth showing next to environmental evidence. Never alerts."""
    signals: list[dict[str, Any]] = []
    if rain_24h is not None and rain_24h >= HEAVY_RAIN_24H_MM:
        signals.append(
            {
                "code": "heavy-rain-24h",
                "label": "Heavy rainfall in the last 24 h",
                "detail": f"{rain_24h:.1f} mm fell in the last 24 h. Heavy rain can drive urban runoff and combined-sewer overflow into receiving waters.",
                "relevant_hazards": ["enteropathogen-surge"],
            }
        )
    if (
        temperature_c is not None
        and rain_7d is not None
        and temperature_c >= WARM_AIR_C
        and rain_7d < DRY_7D_MM
    ):
        signals.append(
            {
                "code": "warm-dry-spell",
                "label": "Warm, dry spell",
                "detail": f"Air temperature {temperature_c:.1f} °C with {rain_7d:.1f} mm of rain over 7 days. Warm, still conditions favour cyanobacterial growth in slow-moving water.",
                "relevant_hazards": ["cyanobacteria-proliferation"],
            }
        )
    if (
        temperature_c is not None
        and rain_7d is not None
        and temperature_c >= MILD_AIR_C
        and rain_7d >= DRY_7D_MM
    ):
        signals.append(
            {
                "code": "warm-after-rain",
                "label": "Warm weather after recent rain",
                "detail": f"Air temperature {temperature_c:.1f} °C after {rain_7d:.1f} mm of rain over 7 days. Standing water left by rain can support mosquito breeding.",
                "relevant_hazards": ["diptera-vector-surge"],
            }
        )
    for signal in signals:
        signal["epistemic_state"] = "context"
        signal["caveat"] = CONTEXT_CAVEAT
    return signals


def summarise(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduce an Open-Meteo forecast response to what the globe shows. Pure; no I/O."""
    offset = int(raw.get("utc_offset_seconds") or 0)
    current = raw.get("current") or {}
    hourly = raw.get("hourly") or {}
    daily = raw.get("daily") or {}

    anchor = _parse_local(current.get("time"))
    if anchor is None:
        anchor = (datetime.now(UTC) + timedelta(seconds=offset)).replace(tzinfo=None)

    times = [_parse_local(t) for t in hourly.get("time") or []]
    precipitation = hourly.get("precipitation") or []

    def rain_over(hours: int) -> float | None:
        window_start = anchor - timedelta(hours=hours)
        values = [
            p
            for t, p in zip(times, precipitation, strict=False)
            if t is not None and p is not None and window_start < t <= anchor
        ]
        return round(sum(values), 1) if values else None

    rain_24h, rain_72h, rain_7d = rain_over(24), rain_over(72), rain_over(24 * 7)

    hour_start = anchor.replace(minute=0, second=0, microsecond=0)
    forecast: list[dict[str, Any]] = []
    for i, t in enumerate(times):
        if t is None or t < hour_start:
            continue
        code = _at(hourly, "weather_code", i)
        forecast.append(
            {
                "time_local": t.isoformat(),
                "time_utc": _utc_iso(t, offset),
                "temperature_c": _at(hourly, "temperature_2m", i),
                "precipitation_mm": _at(hourly, "precipitation", i),
                "precipitation_probability": _at(hourly, "precipitation_probability", i),
                "weather_code": code,
                "summary": describe(code),
                "cloud_cover": _at(hourly, "cloud_cover", i),
                "wind_speed_kmh": _at(hourly, "wind_speed_10m", i),
                "wind_direction_deg": _at(hourly, "wind_direction_10m", i),
                "is_day": _at(hourly, "is_day", i),
            }
        )
        if len(forecast) >= FORECAST_HOURS:
            break

    days: list[dict[str, Any]] = []
    for i, day in enumerate(daily.get("time") or []):
        code = _at(daily, "weather_code", i)
        days.append(
            {
                "date": day,
                "weather_code": code,
                "summary": describe(code),
                "temperature_max_c": _at(daily, "temperature_2m_max", i),
                "temperature_min_c": _at(daily, "temperature_2m_min", i),
                "precipitation_sum_mm": _at(daily, "precipitation_sum", i),
            }
        )
    today = anchor.date().isoformat()
    days = [d for d in days if isinstance(d["date"], str) and d["date"] >= today]

    temperature = current.get("temperature_2m")
    code = current.get("weather_code")
    return {
        "location": {
            "latitude": raw.get("latitude"),
            "longitude": raw.get("longitude"),
            "elevation_m": raw.get("elevation"),
            "timezone": raw.get("timezone") or "GMT",
            "timezone_abbreviation": raw.get("timezone_abbreviation"),
            "utc_offset_seconds": offset,
        },
        "current": {
            "time_local": anchor.isoformat(),
            "time_utc": _utc_iso(anchor, offset),
            "temperature_c": temperature,
            "apparent_temperature_c": current.get("apparent_temperature"),
            "relative_humidity": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "rain_mm": current.get("rain"),
            "weather_code": code,
            "summary": describe(code),
            "cloud_cover": current.get("cloud_cover"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "is_day": current.get("is_day"),
        },
        "rainfall": {
            "last_24h_mm": rain_24h,
            "last_72h_mm": rain_72h,
            "last_7d_mm": rain_7d,
        },
        "forecast_hourly": forecast,
        "forecast_daily": days,
        "context_signals": context_signals(temperature, rain_24h, rain_7d),
    }


# ---------------------------------------------------------------------------
# Upstream access with cache and degraded mode
# ---------------------------------------------------------------------------

# key -> (monotonic time fetched, ISO time fetched, summary)
_cache: dict[tuple[float, float], tuple[float, str, dict[str, Any]]] = {}
_stats: dict[str, Any] = {
    "upstream_calls": 0,
    "upstream_failures": 0,
    "cache_hits": 0,
    "last_ok_at": None,
    "last_error": None,
    "last_error_at": None,
    "last_outcome": None,
}


_tls_context: ssl.SSLContext | None = None


def _tls() -> ssl.SSLContext:
    """Verify against the OS trust store plus certifi.

    httpx defaults to certifi alone, which fails behind TLS-inspecting proxies or antivirus
    whose root is installed in the OS store (browsers and curl accept those). Verification
    stays on: expired, self-signed and mismatched certificates are still rejected.
    """
    global _tls_context
    if _tls_context is None:
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(certifi.where())
        _tls_context = ctx
    return _tls_context


async def _fetch_upstream(lat: float, lon: float) -> dict[str, Any]:
    """One Open-Meteo call. Module-level so tests can replace it."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": CURRENT_VARS,
        "hourly": HOURLY_VARS,
        "daily": DAILY_VARS,
        "past_days": 7,
        "forecast_days": 3,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False, verify=_tls()) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("unexpected Open-Meteo response")
    return data


def _envelope(
    summary: dict[str, Any],
    *,
    mode: str,
    key: tuple[float, float],
    fetched_at: str,
    age_s: float,
    stale: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "stale": stale,
        "source": SOURCE,
        "attribution": ATTRIBUTION,
        "fetched_at": fetched_at,
        "age_seconds": int(age_s),
        "request": {"latitude": key[0], "longitude": key[1], "precision": "0.01° (~1 km)"},
        "note": note,
        **summary,
    }


def _remember(key: tuple[float, float], fetched_at: str, summary: dict[str, Any]) -> None:
    if key not in _cache and len(_cache) >= MAX_CACHE_ENTRIES:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    _cache[key] = (time.monotonic(), fetched_at, summary)


async def get_weather(lat: float, lon: float) -> dict[str, Any]:
    key = round_coords(lat, lon)
    cached = _cache.get(key)
    now = time.monotonic()

    if cached is not None and now - cached[0] < FRESH_TTL_S:
        _stats["cache_hits"] += 1
        return _envelope(cached[2], mode="cached", key=key, fetched_at=cached[1], age_s=now - cached[0])

    _stats["upstream_calls"] += 1
    try:
        raw = await _fetch_upstream(*key)
        summary = summarise(raw)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        _stats["upstream_failures"] += 1
        _stats["last_error"] = type(exc).__name__
        _stats["last_error_at"] = datetime.now(UTC).isoformat()
        _stats["last_outcome"] = "error"
        log.warning("oahbridge.weather.upstream_failed", error=type(exc).__name__)
        if cached is not None and now - cached[0] < STALE_MAX_S:
            return _envelope(
                cached[2],
                mode="cached",
                key=key,
                fetched_at=cached[1],
                age_s=now - cached[0],
                stale=True,
                note="Open-Meteo did not respond; showing the last good response.",
            )
        return {
            "mode": "unavailable",
            "stale": False,
            "source": SOURCE,
            "attribution": ATTRIBUTION,
            "fetched_at": None,
            "age_seconds": None,
            "request": {"latitude": key[0], "longitude": key[1], "precision": "0.01° (~1 km)"},
            "note": "Open-Meteo did not respond and nothing is cached for this point. No weather is shown rather than an estimate.",
        }

    fetched_at = datetime.now(UTC).isoformat()
    _remember(key, fetched_at, summary)
    _stats["last_ok_at"] = fetched_at
    _stats["last_outcome"] = "ok"
    return _envelope(summary, mode="live", key=key, fetched_at=fetched_at, age_s=0)


def weather_status() -> dict[str, Any]:
    outcome = _stats["last_outcome"]
    if outcome is None:
        status, detail = "idle", "No lookups yet; fetched on demand per point"
    elif outcome == "ok":
        status, detail = "ok", f"Last upstream fetch OK · {len(_cache)} points cached"
    else:
        status = "degraded"
        detail = f"Last upstream fetch failed ({_stats['last_error']}); serving cache where possible"
    return {"status": status, "detail": detail, "cached_points": len(_cache), **_stats}


def reset_for_tests() -> None:
    _cache.clear()
    for k in _stats:
        _stats[k] = 0 if k in ("upstream_calls", "upstream_failures", "cache_hits") else None
