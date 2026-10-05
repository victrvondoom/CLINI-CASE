import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LivePipeline from "../src/oahbridge/LivePipeline";
import LiveWeatherPanel from "../src/oahbridge/LiveWeatherPanel";
import SystemMonitor from "../src/oahbridge/SystemMonitor";
import { oahBridge } from "../src/oahbridge/api";
import type { DemoRunResponse, MonitorSnapshot, WeatherResponse } from "../src/oahbridge/types";

vi.mock("../src/oahbridge/api", () => ({
  oahBridge: { weather: vi.fn(), monitor: vi.fn(), run: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

const hour = (h: number, mm: number) => ({
  time_local: `2026-10-04T${String(h).padStart(2, "0")}:00:00`,
  time_utc: `2026-10-04T${String(h - 1).padStart(2, "0")}:00:00+00:00`,
  temperature_c: 20 + h / 10,
  precipitation_mm: mm,
  precipitation_probability: 40,
  weather_code: mm ? 61 : 3,
  summary: mm ? "Slight rain" : "Overcast",
  cloud_cover: 90,
  wind_speed_kmh: 12,
  wind_direction_deg: 225,
  is_day: 1,
});

const LIVE: WeatherResponse = {
  mode: "live",
  stale: false,
  source: "Open-Meteo Forecast API (open-meteo.com)",
  attribution: "Weather data by Open-Meteo.com (CC BY 4.0)",
  fetched_at: "2026-10-04T17:30:00+00:00",
  age_seconds: 0,
  request: { latitude: 40.2, longitude: -8.43, precision: "0.01° (~1 km)" },
  note: null,
  location: { latitude: 40.2, longitude: -8.43, elevation_m: 40, timezone: "Europe/Lisbon", timezone_abbreviation: "WEST", utc_offset_seconds: 3600 },
  current: {
    time_local: "2026-10-04T18:30:00",
    time_utc: "2026-10-04T17:30:00+00:00",
    temperature_c: 25.1,
    apparent_temperature_c: 24.9,
    relative_humidity: 61,
    precipitation_mm: 0,
    rain_mm: 0,
    weather_code: 3,
    summary: "Overcast",
    cloud_cover: 100,
    wind_speed_kmh: 4,
    wind_direction_deg: 354,
    is_day: 1,
  },
  rainfall: { last_24h_mm: 1.2, last_72h_mm: 3.7, last_7d_mm: 7.5 },
  forecast_hourly: [hour(18, 0), hour(19, 0.6), hour(20, 1.2)],
  forecast_daily: [{ date: "2026-10-04", weather_code: 3, summary: "Overcast", temperature_max_c: 25, temperature_min_c: 15, precipitation_sum_mm: 0 }],
  context_signals: [
    {
      code: "warm-after-rain",
      label: "Warm weather after recent rain",
      detail: "Air temperature 25.1 °C after 7.5 mm of rain over 7 days.",
      relevant_hazards: ["diptera-vector-surge"],
      epistemic_state: "context",
      caveat: "Context only: not evidence of a hazard, an exposure or an illness.",
    },
  ],
};

const POINT = { latitude: 40.2043, longitude: -8.4281, label: "Parque Verde do Mondego Reach", source: "scenario" as const };

describe("LiveWeatherPanel", () => {
  it("shows live weather with its freshness, IANA time zone and context caveat", async () => {
    vi.mocked(oahBridge.weather).mockResolvedValue(LIVE);
    const onGlobeWeather = vi.fn();
    render(<LiveWeatherPanel point={POINT} onGlobeWeather={onGlobeWeather} />);

    await waitFor(() => expect(screen.getByText("LIVE")).toBeTruthy());
    expect(vi.mocked(oahBridge.weather).mock.calls[0].slice(0, 2)).toEqual([40.2043, -8.4281]);
    expect(screen.getByTestId("live-weather").textContent).toContain("Europe/Lisbon");
    expect(screen.getByText("25.1 °C")).toBeTruthy();
    expect(screen.getByTestId("live-weather").textContent).toContain("not evidence of a hazard");
    await waitFor(() => expect(onGlobeWeather).toHaveBeenLastCalledWith(expect.objectContaining({ temperatureC: 25.1, atUtc: null })));
  });

  it("scrubbing the forecast hands that hour to the globe", async () => {
    vi.mocked(oahBridge.weather).mockResolvedValue(LIVE);
    const onGlobeWeather = vi.fn();
    render(<LiveWeatherPanel point={POINT} onGlobeWeather={onGlobeWeather} />);
    await waitFor(() => expect(screen.getByLabelText("Forecast hour")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Forecast hour"), { target: { value: "2" } });
    await waitFor(() =>
      expect(onGlobeWeather).toHaveBeenLastCalledWith(
        expect.objectContaining({ precipitationMm: 1.2, atUtc: "2026-10-04T19:00:00+00:00" }),
      ),
    );
    expect(screen.getByRole("button", { name: /Play 3 h forecast/ }).getAttribute("aria-pressed")).toBe("false");
  });

  it("says weather is unavailable instead of inventing it", async () => {
    vi.mocked(oahBridge.weather).mockResolvedValue({
      mode: "unavailable",
      stale: false,
      source: LIVE.source,
      attribution: LIVE.attribution,
      fetched_at: null,
      age_seconds: null,
      request: LIVE.request,
      note: "Open-Meteo did not respond and nothing is cached for this point.",
    });
    const onGlobeWeather = vi.fn();
    render(<LiveWeatherPanel point={POINT} onGlobeWeather={onGlobeWeather} />);
    await waitFor(() => expect(screen.getByText("UNAVAILABLE")).toBeTruthy());
    expect(screen.getByTestId("live-weather").textContent).toContain("nothing is cached");
    expect(screen.queryByText(/°C/)).toBeNull();
    expect(onGlobeWeather).toHaveBeenLastCalledWith(null);
  });
});

const MONITOR: MonitorSnapshot = {
  status: "operational",
  server_time_utc: "2026-10-04T17:30:00+00:00",
  engine: "OAH-Bridge engine v0.1",
  components: [
    { id: "engine", label: "Corroboration engine", status: "ok", detail: "3 scenarios" },
    { id: "weather", label: "Open-Meteo weather", status: "degraded", detail: "Last upstream fetch failed (ConnectError)" },
  ],
  self_test: { ran_at: "2026-10-04T17:30:00+00:00", duration_ms: 3.2, passed: true, results: [{ scenario: "coimbra-cyanobacteria", passed: true, checks: "44/44" }], error: null },
  weather: { status: "degraded", detail: "", cached_points: 1, upstream_calls: 4, upstream_failures: 1, cache_hits: 2, last_ok_at: null, last_error: "ConnectError", last_error_at: null },
  scope_note: "Counters are process-local: they reset on restart and are per worker.",
  started_at: "2026-10-04T17:00:00+00:00",
  uptime_seconds: 1800,
  counters: { pipeline_runs: 7, pipeline_runs_passed: 7, pipeline_runs_failed: 0, cds_evaluations: 3, cds_cards_issued: 2 },
  recent_runs: [{ id: "run-1", scenario: "toulouse-diptera", ran_at: "2026-10-04T17:29:00+00:00", total_ms: 2.4, passed: true, checks: "44/44" }],
};

describe("SystemMonitor", () => {
  it("renders component health, counters and the self-test", async () => {
    vi.mocked(oahBridge.monitor).mockResolvedValue(MONITOR);
    render(<SystemMonitor />);
    await waitFor(() => expect(screen.getByText("Corroboration engine")).toBeTruthy());
    const text = screen.getByTestId("system-monitor").textContent ?? "";
    expect(text).toContain("Operational");
    expect(text).toContain("Degraded");
    expect(text).toContain("7 passed");
    expect(text).toContain("coimbra-cyanobacteria · 44/44");
    expect(text).toContain("process-local");
  });
});

function demoRun(): DemoRunResponse {
  const stages = ["ingest", "corroborate", "corroborate", "compose", "compose", "compose", "compose", "validate"] as const;
  return {
    run: { id: "run-abc", ran_at: "2026-10-04T17:30:00+00:00", engine: "engine", timings_ms: { ingest: 0.03, corroborate: 0.04, compose: 0.1, validate: 1.4 }, total_ms: 1.6 },
    scenario: {} as DemoRunResponse["scenario"],
    steps: stages.map((stage, i) => ({ step: i + 1, stage, title: `Step title ${i + 1}`, detail: `detail ${i + 1}`, status: i === 7 ? "PASSED" : "COMPLETED" })),
    validation_report: { all_passed: true, tiers: {}, summary: { total_checks: 44, passed_checks: 44, failed_checks: 0 } },
    bundle: { resourceType: "Bundle", type: "collection", total: 0, entry: [] },
  };
}

describe("LivePipeline", () => {
  it("runs on the server, replays every step, then hands the run to the page", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(oahBridge.run).mockResolvedValue(demoRun());
    const onRun = vi.fn();
    const onRunningChange = vi.fn();
    render(<LivePipeline scenarioId="coimbra-cyanobacteria" run={null} onRun={onRun} onRunningChange={onRunningChange} />);

    fireEvent.click(screen.getByRole("button", { name: /Run chain live/ }));
    await waitFor(() => expect(oahBridge.run).toHaveBeenCalledWith("coimbra-cyanobacteria"));
    await waitFor(() => expect(screen.getAllByText(/Step title/).length).toBe(8));

    // Each step's timer is scheduled by an effect after the previous reveal, so advance step by step.
    for (let i = 0; i < 12; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(600);
      });
    }
    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    expect(onRunningChange).toHaveBeenCalledWith(true);
    expect(onRunningChange).toHaveBeenLastCalledWith(false);
  });
});
