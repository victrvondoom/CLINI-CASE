"""Weather context: live → cached → unavailable, privacy rounding, and the pure summariser.

Open-Meteo is never called; `_fetch_upstream` is replaced with a fake.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.oahbridge import weather


def _open_meteo_payload(*, rain_per_hour: float = 0.0, temperature: float = 22.0) -> dict:
    """An Open-Meteo-shaped response like the real request (past_days=7, forecast_days=3), local times."""
    now_local = datetime(2026, 10, 4, 18, 30)
    start = datetime(2026, 9, 27, 0, 0)
    hours = [start + timedelta(hours=i) for i in range(24 * 10)]
    return {
        "latitude": 40.2,
        "longitude": -8.43,
        "elevation": 40.0,
        "timezone": "Europe/Lisbon",
        "timezone_abbreviation": "WEST",
        "utc_offset_seconds": 3600,
        "current": {
            "time": now_local.strftime("%Y-%m-%dT%H:%M"),
            "temperature_2m": temperature,
            "relative_humidity_2m": 60,
            "apparent_temperature": temperature,
            "precipitation": 0.0,
            "rain": 0.0,
            "weather_code": 3,
            "cloud_cover": 90,
            "wind_speed_10m": 12.0,
            "wind_direction_10m": 270,
            "is_day": 1,
        },
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
            "temperature_2m": [temperature] * len(hours),
            "precipitation": [rain_per_hour] * len(hours),
            "precipitation_probability": [30] * len(hours),
            "weather_code": [61 if rain_per_hour else 3] * len(hours),
            "cloud_cover": [90] * len(hours),
            "wind_speed_10m": [12.0] * len(hours),
            "wind_direction_10m": [270] * len(hours),
            "is_day": [1] * len(hours),
        },
        "daily": {
            "time": ["2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06"],
            "weather_code": [3, 3, 61, 3],
            "temperature_2m_max": [24, 25, 21, 23],
            "temperature_2m_min": [14, 15, 13, 14],
            "precipitation_sum": [0, 0, 4.2, 0],
        },
    }


@pytest.fixture(autouse=True)
def _clean_weather_state():
    weather.reset_for_tests()
    yield
    weather.reset_for_tests()


def _fake_upstream(monkeypatch, payload=None, exc: Exception | None = None):
    calls: list[tuple[float, float]] = []

    async def fake(lat, lon):
        calls.append((lat, lon))
        if exc is not None:
            raise exc
        return payload

    monkeypatch.setattr(weather, "_fetch_upstream", fake)
    return calls


# --- coordinates and privacy ------------------------------------------------


def test_coordinates_are_rounded_to_about_one_kilometre():
    assert weather.round_coords(40.203512, -8.428549) == (40.2, -8.43)


@pytest.mark.parametrize("lat,lon", [(91, 0), (0, 181), (float("nan"), 0), ("north", 0), (None, 0)])
def test_invalid_coordinates_are_rejected(lat, lon):
    with pytest.raises(weather.InvalidCoordinatesError):
        weather.round_coords(lat, lon)


async def test_only_rounded_coordinates_reach_the_upstream(monkeypatch):
    calls = _fake_upstream(monkeypatch, _open_meteo_payload())
    result = await weather.get_weather(40.203512, -8.428549)
    assert calls == [(40.2, -8.43)]
    assert result["request"] == {"latitude": 40.2, "longitude": -8.43, "precision": "0.01° (~1 km)"}


# --- live → cached → unavailable -------------------------------------------


async def test_first_call_is_live_and_second_is_labelled_cached(monkeypatch):
    calls = _fake_upstream(monkeypatch, _open_meteo_payload())
    first = await weather.get_weather(40.2, -8.43)
    second = await weather.get_weather(40.2, -8.43)
    assert first["mode"] == "live"
    assert first["age_seconds"] == 0
    assert second["mode"] == "cached"
    assert second["stale"] is False
    assert len(calls) == 1
    assert weather.weather_status()["status"] == "ok"


async def test_upstream_failure_serves_last_good_response_marked_stale(monkeypatch):
    _fake_upstream(monkeypatch, _open_meteo_payload())
    await weather.get_weather(40.2, -8.43)
    # Expire the fresh window without waiting.
    key = (40.2, -8.43)
    t, fetched_at, summary = weather._cache[key]
    weather._cache[key] = (t - weather.FRESH_TTL_S - 1, fetched_at, summary)

    _fake_upstream(monkeypatch, exc=httpx.ConnectError("boom"))
    result = await weather.get_weather(40.2, -8.43)
    assert result["mode"] == "cached"
    assert result["stale"] is True
    assert "last good response" in result["note"]
    assert result["current"]["summary"] == "Overcast"
    assert weather.weather_status()["status"] == "degraded"


async def test_upstream_failure_with_no_cache_is_unavailable_not_invented(monkeypatch):
    _fake_upstream(monkeypatch, exc=httpx.ReadTimeout("slow"))
    result = await weather.get_weather(40.2, -8.43)
    assert result["mode"] == "unavailable"
    assert "current" not in result
    assert "forecast_hourly" not in result
    assert weather.weather_status()["upstream_failures"] == 1


async def test_malformed_upstream_payload_degrades_cleanly(monkeypatch):
    _fake_upstream(monkeypatch, exc=ValueError("unexpected Open-Meteo response"))
    result = await weather.get_weather(40.2, -8.43)
    assert result["mode"] == "unavailable"


async def test_stale_cache_older_than_limit_is_not_served(monkeypatch):
    _fake_upstream(monkeypatch, _open_meteo_payload())
    await weather.get_weather(40.2, -8.43)
    key = (40.2, -8.43)
    t, fetched_at, summary = weather._cache[key]
    weather._cache[key] = (t - weather.STALE_MAX_S - 1, fetched_at, summary)
    _fake_upstream(monkeypatch, exc=httpx.ConnectError("down"))
    assert (await weather.get_weather(40.2, -8.43))["mode"] == "unavailable"


# --- summariser -------------------------------------------------------------


def test_summary_carries_iana_timezone_and_utc_times():
    summary = weather.summarise(_open_meteo_payload())
    assert summary["location"]["timezone"] == "Europe/Lisbon"
    assert summary["location"]["utc_offset_seconds"] == 3600
    assert summary["current"]["time_local"] == "2026-10-04T18:30:00"
    assert summary["current"]["time_utc"] == "2026-10-04T17:30:00+00:00"


def test_rainfall_windows_are_summed_from_hourly_history():
    summary = weather.summarise(_open_meteo_payload(rain_per_hour=0.5))
    assert summary["rainfall"]["last_24h_mm"] == 12.0
    assert summary["rainfall"]["last_72h_mm"] == 36.0
    assert summary["rainfall"]["last_7d_mm"] == 84.0


def test_forecast_starts_at_the_current_hour_and_is_capped():
    summary = weather.summarise(_open_meteo_payload())
    hours = summary["forecast_hourly"]
    assert hours[0]["time_local"] == "2026-10-04T18:00:00"
    assert len(hours) == weather.FORECAST_HOURS
    assert hours[0]["summary"] == "Overcast"
    assert [d["date"] for d in summary["forecast_daily"]] == ["2026-10-04", "2026-10-05", "2026-10-06"]


def test_unknown_weather_code_is_described_honestly():
    assert weather.describe(1234) == "Unknown conditions"
    assert weather.describe(None) == "Unknown conditions"


# --- context signals --------------------------------------------------------


def test_heavy_rain_signal_points_at_enteropathogen_hazard():
    signals = weather.context_signals(18.0, rain_24h=25.0, rain_7d=40.0)
    heavy = [s for s in signals if s["code"] == "heavy-rain-24h"][0]
    assert heavy["relevant_hazards"] == ["enteropathogen-surge"]


def test_warm_dry_spell_points_at_cyanobacteria():
    codes = {s["code"] for s in weather.context_signals(27.0, rain_24h=0.0, rain_7d=1.0)}
    assert codes == {"warm-dry-spell"}


def test_warm_after_rain_points_at_vectors():
    codes = {s["code"] for s in weather.context_signals(22.0, rain_24h=1.0, rain_7d=12.0)}
    assert codes == {"warm-after-rain"}


def test_every_signal_is_context_with_a_caveat():
    for signal in weather.context_signals(30.0, rain_24h=30.0, rain_7d=1.0):
        assert signal["epistemic_state"] == "context"
        assert "not evidence" in signal["caveat"]


def test_no_signal_without_data():
    assert weather.context_signals(None, None, None) == []
