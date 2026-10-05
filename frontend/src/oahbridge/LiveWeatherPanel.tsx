/**
 * Live weather for the point the globe is looking at: a scenario site, the user's GPS
 * position, a typed location or a point picked on the globe.
 *
 * Data comes from Open-Meteo through our backend, with its freshness stated (LIVE, CACHED,
 * STALE, UNAVAILABLE); nothing is invented when the lookup fails. "Play" steps through the
 * 48-hour forecast and hands each hour to the globe, which redraws rain, cloud, wind and the
 * day/night terminator for that hour. Weather is context, never evidence of a hazard.
 */
import { CloudRain, Pause, Play, RefreshCw, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { formatInZone } from "../globe/geo";
import type { GlobeWeather } from "../globe/weatherLayers";
import { oahBridge } from "./api";
import {
  type FreshnessLabel,
  compass,
  formatAge,
  formatInstant,
  formatLocalHour,
  weatherFreshness,
} from "./format";
import type { WeatherHour, WeatherResponse } from "./types";

export interface WeatherPoint {
  latitude: number;
  longitude: number;
  label: string;
  source: "scenario" | "gps" | "manual" | "globe";
}

interface Props {
  point: WeatherPoint | null;
  /** The weather the globe should draw (current conditions, or the forecast hour being played). */
  onGlobeWeather?: (weather: GlobeWeather | null) => void;
}

const FRESHNESS_STYLE: Record<FreshnessLabel, string> = {
  LIVE: "border-emerald-400/50 bg-emerald-400/10 text-emerald-300",
  CACHED: "border-surface-border bg-surface-bg text-ink-body",
  STALE: "border-amber-400/50 bg-amber-400/10 text-amber-300",
  UNAVAILABLE: "border-red-400/50 bg-red-400/10 text-red-300",
};

const SOURCE_LABEL: Record<WeatherPoint["source"], string> = {
  scenario: "Scenario site",
  gps: "Your GPS location (coarsened to ~1 km)",
  manual: "Typed location (coarsened to ~1 km)",
  globe: "Point picked on the globe",
};

const STEP_MS = 650;

function num(value: number | null | undefined, digits = 1): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

export default function LiveWeatherPanel({ point, onGlobeWeather }: Props) {
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hour, setHour] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [reloadKey, setReloadKey] = useState(0);

  const lat = point?.latitude;
  const lon = point?.longitude;

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (lat == null || lon == null) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setHour(null);
    setPlaying(false);
    oahBridge
      .weather(lat, lon, controller.signal)
      .then((w) => {
        if (!controller.signal.aborted) setWeather(w);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setWeather(null);
        setError(e instanceof Error ? e.message : "Weather lookup failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [lat, lon, reloadKey]);

  const hours: WeatherHour[] = useMemo(() => weather?.forecast_hourly ?? [], [weather]);

  // Forecast playback: advance one hour every STEP_MS, stop at the end.
  useEffect(() => {
    if (!playing) return;
    if (hours.length === 0 || (hour != null && hour >= hours.length - 1)) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setHour((h) => (h == null ? 0 : Math.min(h + 1, hours.length - 1))), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, hour, hours.length]);

  const selected = hour == null ? null : (hours[hour] ?? null);

  const globeWeather = useMemo<GlobeWeather | null>(() => {
    if (!weather || weather.mode === "unavailable" || lat == null || lon == null) return null;
    if (selected) {
      return {
        latitude: lat,
        longitude: lon,
        atUtc: selected.time_utc,
        precipitationMm: selected.precipitation_mm ?? 0,
        windSpeedKmh: selected.wind_speed_kmh ?? 0,
        windDirectionDeg: selected.wind_direction_deg ?? 0,
        cloudCover: selected.cloud_cover ?? 0,
        temperatureC: selected.temperature_c,
      };
    }
    const c = weather.current;
    if (!c) return null;
    return {
      latitude: lat,
      longitude: lon,
      atUtc: null,
      precipitationMm: c.precipitation_mm ?? 0,
      windSpeedKmh: c.wind_speed_kmh ?? 0,
      windDirectionDeg: c.wind_direction_deg ?? 0,
      cloudCover: c.cloud_cover ?? 0,
      temperatureC: c.temperature_c,
    };
  }, [weather, selected, lat, lon]);

  useEffect(() => {
    onGlobeWeather?.(globeWeather);
  }, [globeWeather, onGlobeWeather]);

  if (!point) {
    return <p className="text-xs text-ink-muted">Pick a scenario, share your location or click the globe to see weather there.</p>;
  }

  const freshness = weather ? weatherFreshness(weather) : null;
  const tz = weather?.location?.timezone;
  const current = weather?.current;
  const maxRain = Math.max(1, ...hours.map((h) => h.precipitation_mm ?? 0));
  const temps = hours.map((h) => h.temperature_c).filter((t): t is number => t != null);
  const tMin = temps.length ? Math.min(...temps) : 0;
  const tMax = temps.length ? Math.max(...temps) : 1;
  const tempPath = hours
    .map((h, i) => {
      if (h.temperature_c == null) return null;
      const x = i * 10 + 5;
      const y = 8 + (1 - (h.temperature_c - tMin) / Math.max(1, tMax - tMin)) * 30;
      return `${x},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <div className="space-y-3" data-testid="live-weather">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-sm text-ink-primary">
            <CloudRain size={14} aria-hidden="true" /> Weather at {point.label}
          </div>
          <p className="mt-0.5 text-[11px] text-ink-muted">
            {SOURCE_LABEL[point.source]} · {point.latitude.toFixed(2)}, {point.longitude.toFixed(2)}
            {tz && (
              <>
                {" "}· {tz} · local time <span className="text-ink-body">{formatInZone(now, tz)}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {freshness && (
            <span
              className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wider ${FRESHNESS_STYLE[freshness]}`}
              title={weather?.note ?? undefined}
            >
              {freshness === "LIVE" && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300 align-middle" />}
              {freshness}
            </span>
          )}
          <button
            type="button"
            aria-label="Refresh weather"
            onClick={() => setReloadKey((k) => k + 1)}
            className="rounded-md border border-surface-border p-1.5 text-ink-body hover:border-accent-cyan"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {error && <p role="alert" className="text-xs text-red-300">Weather lookup failed: {error}</p>}
      {loading && !weather && <p className="text-xs text-ink-muted">Fetching live weather…</p>}
      {weather?.mode === "unavailable" && (
        <p className="text-xs text-ink-muted">{weather.note ?? "Weather is unavailable for this point right now."}</p>
      )}

      {current && (
        <>
          <div className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-5">
            <Tile label="Now" value={`${num(current.temperature_c)} °C`} hint={`${current.summary} · feels ${num(current.apparent_temperature_c)} °C`} />
            <Tile
              label="Wind"
              value={`${num(current.wind_speed_kmh, 0)} km/h`}
              hint={`from ${compass(current.wind_direction_deg)}`}
              arrow={current.wind_direction_deg}
            />
            <Tile label="Humidity" value={`${num(current.relative_humidity, 0)} %`} hint={`cloud ${num(current.cloud_cover, 0)} %`} />
            <Tile label="Rain now" value={`${num(current.precipitation_mm)} mm`} hint="last 15 min to 1 h" />
            <Tile
              label="Rainfall"
              value={`${num(weather?.rainfall?.last_24h_mm)} mm`}
              hint={`24 h · 72 h ${num(weather?.rainfall?.last_72h_mm)} · 7 d ${num(weather?.rainfall?.last_7d_mm)}`}
            />
          </div>

          {hours.length > 0 && (
            <div className="rounded-xl border border-surface-border bg-surface-bg p-3">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (!playing && hour != null && hour >= hours.length - 1) setHour(0);
                    setPlaying((p) => !p);
                  }}
                  aria-pressed={playing}
                  className="flex items-center gap-1.5 rounded-md border border-accent-cyan/40 bg-accent-cyan/15 px-2.5 py-1.5 text-[11px] text-accent-cyan hover:bg-accent-cyan/25"
                >
                  {playing ? <Pause size={12} /> : <Play size={12} />}
                  {playing ? "Pause" : `Play ${hours.length} h forecast`}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPlaying(false);
                    setHour(null);
                  }}
                  className="flex items-center gap-1 rounded-md border border-surface-border px-2 py-1.5 text-[11px] text-ink-body hover:border-accent-cyan"
                >
                  <RotateCcw size={11} /> Now
                </button>
                <input
                  type="range"
                  min={0}
                  max={hours.length - 1}
                  value={hour ?? 0}
                  aria-label="Forecast hour"
                  onChange={(e) => {
                    setPlaying(false);
                    setHour(Number(e.target.value));
                  }}
                  className="min-w-[140px] flex-1 accent-cyan-400"
                />
              </div>
              <p className="mt-2 text-[11px] text-ink-body" aria-live="polite">
                {selected
                  ? `${formatLocalHour(selected.time_local)} local · ${selected.summary} · ${num(selected.temperature_c)} °C · ${num(selected.precipitation_mm)} mm (${num(selected.precipitation_probability, 0)} %) · wind ${num(selected.wind_speed_kmh, 0)} km/h from ${compass(selected.wind_direction_deg)}`
                  : "Showing current conditions. Play the forecast to watch rain, cloud, wind and daylight move on the globe."}
              </p>
              <svg viewBox={`0 0 ${hours.length * 10} 70`} className="mt-2 h-16 w-full" role="img" aria-label="48-hour precipitation and temperature forecast">
                {hours.map((h, i) => {
                  const mm = h.precipitation_mm ?? 0;
                  const height = mm > 0 ? Math.max(2, (mm / maxRain) * 26) : 0;
                  return (
                    <g key={h.time_local} onClick={() => { setPlaying(false); setHour(i); }} className="cursor-pointer">
                      <rect x={i * 10} y={0} width={10} height={70} fill={i === hour ? "rgba(34,211,238,0.18)" : "transparent"} />
                      {height > 0 && <rect x={i * 10 + 2} y={68 - height} width={6} height={height} fill="#38bdf8" rx={1} />}
                    </g>
                  );
                })}
                {tempPath && <polyline points={tempPath} fill="none" stroke="#fbbf24" strokeWidth={1.5} />}
              </svg>
              <p className="text-[10px] text-ink-faint">Bars: precipitation (mm/h) · line: air temperature · click an hour to inspect.</p>
            </div>
          )}

          {(weather?.forecast_daily?.length ?? 0) > 0 && (
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              {weather!.forecast_daily!.map((d) => (
                <div key={d.date} className="rounded-lg border border-surface-border bg-surface-bg p-2">
                  <div className="text-ink-muted">{formatLocalHour(`${d.date}T00:00`).split(" ")[0]} {d.date.slice(5)}</div>
                  <div className="text-ink-primary">{num(d.temperature_min_c, 0)}–{num(d.temperature_max_c, 0)} °C</div>
                  <div className="text-ink-muted">{d.summary} · {num(d.precipitation_sum_mm)} mm</div>
                </div>
              ))}
            </div>
          )}

          {weather?.context_signals?.map((signal) => (
            <div key={signal.code} className="rounded-lg border border-amber-400/30 bg-amber-400/5 p-2 text-[11px]">
              <span className="text-amber-300">Context signal: {signal.label}.</span>{" "}
              <span className="text-ink-body">{signal.detail}</span>
              <div className="mt-0.5 text-ink-faint">{signal.caveat}</div>
            </div>
          ))}
        </>
      )}

      {weather && (
        <p className="text-[10px] text-ink-faint">
          {weather.attribution} · fetched {formatInstant(weather.fetched_at, tz)} ({formatAge(weather.age_seconds)})
          {weather.note ? ` · ${weather.note}` : ""}
        </p>
      )}
    </div>
  );
}

function Tile({ label, value, hint, arrow }: { label: string; value: string; hint: string; arrow?: number | null }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-bg p-2">
      <div className="flex items-center justify-between text-ink-faint">
        {label}
        {arrow != null && (
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ transform: `rotate(${arrow + 180}deg)` }}>
            <path d="M7 1 L11 11 L7 8.5 L3 11 Z" fill="currentColor" />
          </svg>
        )}
      </div>
      <div className="mt-0.5 text-sm text-ink-primary">{value}</div>
      <div className="truncate text-ink-muted" title={hint}>{hint}</div>
    </div>
  );
}
