import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import CesiumGlobe, { type CityPin } from "../globe/CesiumGlobe";
import ObservationGlobe, { type GlobeWeather } from "../globe/ObservationGlobe";
import CityMatrix, { SCENARIO_COUNTRY, keyInputText, outcomeText } from "../oahbridge/CityMatrix";
import LivePipeline from "../oahbridge/LivePipeline";
import LiveWeatherPanel, { type WeatherPoint } from "../oahbridge/LiveWeatherPanel";
import SystemMonitor from "../oahbridge/SystemMonitor";
import { oahBridge } from "../oahbridge/api";
import { EPISTEMIC_HEX, EPISTEMIC_LABEL, humanize, riskHex } from "../oahbridge/format";
import type { CdsResponse, DemoRunResponse, ScenarioSummary } from "../oahbridge/types";

const card = "rounded-xl border border-surface-border bg-surface-raised p-4";

export default function OahBridge() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [run, setRun] = useState<DemoRunResponse | null>(null);
  const [cds, setCds] = useState<CdsResponse | null>(null);
  const [weatherPoint, setWeatherPoint] = useState<WeatherPoint | null>(null);
  const [globeWeather, setGlobeWeather] = useState<GlobeWeather | null>(null);
  const [running, setRunning] = useState(false);
  const [monitorKey, setMonitorKey] = useState(0);
  const [zoneTick, setZoneTick] = useState(0);
  const [focusMode, setFocusMode] = useState<"overview" | "city">("overview");
  const [focusKey, setFocusKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    oahBridge.scenarios().then((items) => {
      setScenarios(items);
      if (items[0]) setScenarioId(items[0].id);
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load scenarios"));
  }, []);

  useEffect(() => {
    if (!scenarioId) return;
    let current = true;
    setBusy(true);
    setError(null);
    setCds(null);
    oahBridge.run(scenarioId).then((value) => {
      if (current) setRun(value);
    }).catch((e: unknown) => {
      if (current) setError(e instanceof Error ? e.message : "Could not run the evidence chain");
    }).finally(() => { if (current) setBusy(false); });
    return () => { current = false; };
  }, [scenarioId]);

  const selected = scenarios.find((item) => item.id === scenarioId);
  const markers = useMemo(() => selected ? [
    { id: selected.site.id, latitude: selected.site.centroid.latitude, longitude: selected.site.centroid.longitude, label: selected.site.name, color: "#22d3ee" },
    ...selected.citizen_points.map((point) => ({ id: point.id, latitude: point.latitude, longitude: point.longitude, label: point.sighting, color: "#f59e0b" })),
  ] : [], [selected]);

  // A new scenario resets the weather point to its site and flies the globe there.
  useEffect(() => {
    if (!selected) return;
    setZoneTick(0);
    setWeatherPoint({
      latitude: selected.site.centroid.latitude,
      longitude: selected.site.centroid.longitude,
      label: selected.site.name,
      source: "scenario",
    });
  }, [selected]);

  const focus = useMemo(
    () =>
      selected
        ? {
            latitude: selected.site.centroid.latitude,
            longitude: selected.site.centroid.longitude,
            key: `${selected.id}-${zoneTick}`,
            distance: zoneTick > 0 ? 1.006 : 1.9,
          }
        : undefined,
    [selected, zoneTick],
  );
  const zones = useMemo(
    () => (selected ? [{ id: selected.site.id, ring: selected.site.polygon, color: "#22d3ee" }] : []),
    [selected],
  );
  const sunDate = useMemo(
    () => (globeWeather?.atUtc ? new Date(globeWeather.atUtc) : null),
    [globeWeather?.atUtc],
  );

  // Every research city on the realistic globe, with its matrix row.
  const pins = useMemo<CityPin[]>(
    () =>
      scenarios.map((s) => ({
        id: s.id,
        name: s.city.split(" / ")[0],
        basin: s.river_system,
        country: SCENARIO_COUNTRY[s.id] ?? "",
        latitude: s.site.centroid.latitude,
        longitude: s.site.centroid.longitude,
        color: EPISTEMIC_HEX[s.epistemic_status],
        hazard: s.hazard_display,
        status: s.is_lab_confirmed ? "Lab-confirmed (lab override)" : EPISTEMIC_LABEL[s.epistemic_status],
        score: s.evidence_score,
        sub: {
          cs: s.sub_scores?.sensor_corroboration ?? 0,
          cc: s.sub_scores?.citizen_agreement ?? 0,
          ct: s.sub_scores?.temporal_consistency ?? 0,
        },
        cohort: `~${s.site.estimated_exposed_population.toLocaleString("en-GB")} people · ${humanize(s.site.recreational_use_category)} · FHIR Group (actual = false)`,
        outcome: `SNOMED CT ${outcomeText(s)}`,
        inputs: (s.key_inputs ?? []).map(keyInputText),
        zone: s.site.polygon,
        reports: s.citizen_points.map((p) => ({
          id: p.id,
          latitude: p.latitude,
          longitude: p.longitude,
          label: `Citizen report: ${humanize(p.sighting)} (severity ${p.severity}/5)`,
        })),
        labelSide: s.id === "mondego-storm-surge" ? ("left" as const) : ("right" as const),
      })),
    [scenarios],
  );

  const selectCity = useCallback((id: string) => {
    setScenarioId(id);
    setFocusMode("city");
    setFocusKey((k) => k + 1);
  }, []);

  const onRun = useCallback((value: DemoRunResponse) => {
    setRun(value);
    setMonitorKey((k) => k + 1);
  }, []);
  const onDeviceLocation = useCallback((latitude: number, longitude: number, source: "gps" | "manual") => {
    setWeatherPoint({ latitude, longitude, label: source === "gps" ? "your location" : "the typed location", source });
  }, []);
  const onSurfaceSelect = useCallback((latitude: number, longitude: number) => {
    setWeatherPoint({
      latitude: Math.round(latitude * 100) / 100,
      longitude: Math.round(longitude * 100) / 100,
      label: "the picked point",
      source: "globe",
    });
  }, []);
  const onMarkerSelect = useCallback(
    (id: string) => {
      if (!selected) return;
      const point = selected.citizen_points.find((p) => p.id === id);
      setWeatherPoint(
        point
          ? { latitude: point.latitude, longitude: point.longitude, label: `report ${point.id}`, source: "scenario" }
          : {
              latitude: selected.site.centroid.latitude,
              longitude: selected.site.centroid.longitude,
              label: selected.site.name,
              source: "scenario",
            },
      );
    },
    [selected],
  );

  async function evaluate() {
    if (!scenarioId) return;
    setError(null);
    try { setCds(await oahBridge.evaluateExposure(scenarioId)); }
    catch (e) { setError(e instanceof Error ? e.message : "CDS evaluation failed"); }
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-5 p-5 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-accent-cyan">OneAquaHealth · Track 7</p>
          <h1 className="mt-2">One Health context explorer</h1>
          <p className="mt-2 max-w-3xl text-sm text-ink-muted">Step 1 · Inspect a synthetic environmental scenario, its location, weather context, evidence classification, and generated FHIR resources.</p>
        </div>
        <Link to="/aquahealth/map" className="text-sm text-accent-cyan underline">Open AquaHealth map</Link>
      </header>

      <section aria-label="Select scenario" className={`${card} flex flex-wrap items-center gap-3`}>
        <label htmlFor="oah-scenario" className="text-sm text-ink-muted">Synthetic scenario</label>
        <select id="oah-scenario" value={scenarioId} onChange={(e) => selectCity(e.target.value)} className="min-w-64 rounded-md border border-surface-border bg-surface-bg px-3 py-2 text-sm">
          {scenarios.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.city}</option>)}
        </select>
        {selected && <span className="text-xs text-ink-muted">{selected.grounding_statement}</span>}
      </section>

      {error && <div role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}
      {selected && <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,.6fr)]">
        <section className={card}>
          <h2 className="mb-3 text-sm font-semibold text-ink-primary">1 · Real-world view: OneAquaHealth research cities</h2>
          <CesiumGlobe
            pins={pins}
            selectedId={scenarioId}
            onSelect={selectCity}
            focusMode={focusMode}
            focusKey={focusKey}
            weather={globeWeather}
            time={sunDate}
            onSurfaceSelect={onSurfaceSelect}
            onDeviceLocation={onDeviceLocation}
            fallback={
              <ObservationGlobe
                markers={markers}
                selectedId={selected.site.id}
                onSelect={onMarkerSelect}
                focus={focus}
                zones={zones}
                weather={globeWeather}
                sunDate={sunDate}
                pulseId={running ? selected.site.id : null}
                onDeviceLocation={onDeviceLocation}
                onSurfaceSelect={onSurfaceSelect}
              />
            }
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setZoneTick((t) => t + 1);
                setFocusMode("city");
                setFocusKey((k) => k + 1);
              }}
              className="rounded-md border border-accent-cyan/40 bg-accent-cyan/15 px-3 py-1.5 text-[11px] text-accent-cyan hover:bg-accent-cyan/25"
            >
              Fly to {selected.city.split(" / ")[0]} exposure zone
            </button>
            <button
              type="button"
              onClick={() => {
                setZoneTick(0);
                setFocusMode("overview");
                setFocusKey((k) => k + 1);
              }}
              className="rounded-md border border-surface-border px-3 py-1.5 text-[11px] text-ink-body hover:border-accent-cyan"
            >
              All cities
            </button>
            <span className="text-[11px] text-ink-muted">Click a city beacon for its matrix card · click anywhere else to get weather there.</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">Scenario sites and community reports are synthetic. Location context supports review; it does not establish exposure or diagnosis.</p>
        </section>
        <section className={card}>
          <h2 className="text-sm font-semibold text-ink-primary">2 · Evidence classification</h2>
          {run ? <>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full px-3 py-1 text-xs" style={{ color: riskHex(run.scenario.qualitative_risk), background: `${riskHex(run.scenario.qualitative_risk)}22` }}>{run.scenario.qualitative_risk} contextual risk</span>
              <span className="rounded-full border border-surface-border px-3 py-1 text-xs">{EPISTEMIC_LABEL[run.scenario.epistemic_status]}</span>
              {run.scenario.synthetic && <span className="rounded-full border border-amber-500/40 px-3 py-1 text-xs text-amber-300">Synthetic data</span>}
            </div>
            <p className="mt-3 text-sm text-ink-muted">{run.scenario.risk_summary}</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <Metric label="Evidence score" value={run.scenario.evidence_score.toFixed(2)} />
              <Metric label="Laboratory status" value={run.scenario.is_lab_confirmed ? "Reference assay reported" : "Not lab confirmed"} />
              <Metric label="Sensor reports" value={String(run.scenario.sensor_readings.length)} />
              <Metric label="Community reports" value={String(run.scenario.citizen_reports.length)} />
            </dl>
          </> : <p className="mt-3 text-sm text-ink-muted">{busy ? "Building evidence chain…" : "Select a scenario to inspect its evidence."}</p>}
        </section>
      </div>}

      {scenarios.length > 0 && <section className={card}>
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-ink-primary">Multi-city demonstration matrix</h2>
          <p className="mt-1 text-xs text-ink-muted">Three OneAquaHealth research cities, computed live by the engine. Click a row to fly the globe there.</p>
        </div>
        <CityMatrix scenarios={scenarios} selectedId={scenarioId} onSelect={selectCity} />
      </section>}

      {selected && <section className={card}>
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-ink-primary">3 · Temporal and weather context</h2>
          <p className="mt-1 text-xs text-ink-muted">Context only. Time or location overlap does not establish causation.</p>
        </div>
        <LiveWeatherPanel point={weatherPoint} onGlobeWeather={setGlobeWeather} />
      </section>}

      {selected && <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,.7fr)]">
        <div className={card}>
          <LivePipeline scenarioId={scenarioId} run={run} onRun={onRun} onRunningChange={setRunning} />
        </div>
        <div className={card}>
          <SystemMonitor refreshKey={monitorKey} />
        </div>
      </section>}

      {run && <>
        <section className={card}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><h2 className="text-sm font-semibold text-ink-primary">4 · Six-tier standards validation</h2><p className="mt-1 text-xs text-ink-muted">Deterministic synthetic analysis · {run.run.engine} · {run.run.total_ms.toFixed(2)} ms</p></div>
            <span className={`rounded-full px-3 py-1 text-xs ${run.validation_report.all_passed ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>{run.validation_report.summary.passed_checks}/{run.validation_report.summary.total_checks} checks passed</span>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(run.validation_report.tiers).map(([key, tier]) => {
              const passed = tier.checks.filter((c) => c.passed).length;
              return (
                <details key={key} className="rounded-lg border border-surface-border bg-surface-bg p-3 text-xs">
                  <summary className="cursor-pointer text-ink-primary">
                    <span style={{ color: tier.passed ? "#22c55e" : "#ef4444" }}>{tier.passed ? "✓" : "✗"}</span> {tier.name} · {passed}/{tier.checks.length}
                  </summary>
                  <ul className="mt-2 space-y-1 text-ink-muted">
                    {tier.checks.map((check, i) => <li key={`${check.name}-${i}`}><span style={{ color: check.passed ? "#22c55e" : "#ef4444" }}>{check.passed ? "✓" : "✗"}</span> {check.name}</li>)}
                  </ul>
                </details>
              );
            })}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <div className={card}>
            <div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold text-ink-primary">5 · Standards preview</h2><p className="mt-1 text-xs text-ink-muted">FHIR R4 collection Bundle · {run.bundle.entry.length} resources</p></div><a className="text-xs text-accent-cyan underline" href="/api/v1/oah-bridge/fhir/metadata" target="_blank" rel="noreferrer">CapabilityStatement</a></div>
            <div className="mt-3 flex flex-wrap gap-2">{run.bundle.entry.map(({ resource }) => <span key={`${resource.resourceType}/${resource.id}`} className="rounded border border-surface-border px-2 py-1 text-[11px]">{resource.resourceType}/{resource.id}</span>)}</div>
            <p className="mt-3 text-xs text-ink-muted">Application-level pinned checks only. This is not official HL7 or OAH certification.</p>
          </div>
          <div className={card}>
            <h2 className="text-sm font-semibold text-ink-primary">6 · Informational clinical context</h2>
            <p className="mt-1 text-xs text-ink-muted">CDS Hooks response is informational and does not diagnose or recommend treatment.</p>
            <button type="button" onClick={evaluate} disabled={busy} className="mt-3 rounded-md border border-accent-cyan/50 bg-accent-cyan/10 px-3 py-2 text-xs text-accent-cyan disabled:opacity-50">Evaluate synthetic demo context</button>
            {cds && <div className="mt-3 space-y-2" aria-live="polite">{cds.cards.map((item, i) => <article key={`${item.summary}-${i}`} className="rounded-lg border border-surface-border p-3"><p className="text-sm text-ink-primary">{item.summary}</p><p className="mt-1 text-xs text-ink-muted">{item.detail}</p></article>)}<p className="text-[10px] text-ink-faint">Location source: {cds.location_source}</p></div>}
          </div>
        </section>
      </>}
      <section className={`${card} flex flex-wrap items-center justify-between gap-4 border-accent-cyan/30`}>
        <div><h2 className="text-sm font-semibold text-ink-primary">Continue to the governed exchange</h2><p className="mt-1 max-w-3xl text-xs text-ink-muted">This scenario explorer is an illustrative context step. It does not write its scenario into an exchange job. The Track 7 workbench runs the separate end-to-end flow: semantic mapping, human approval, validation, System B transfer, return, round-trip proof, and Evidence Passport.</p></div>
        <Link to="/interop" className="shrink-0 rounded-md bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-bg">Open Track 7 exchange →</Link>
      </section>
      <p className="text-[11px] text-ink-faint">Synthetic demonstration only. Environmental signals are not patient diagnoses; possible associations remain subject to human review.</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-surface-bg p-3"><dt className="text-ink-faint">{label}</dt><dd className="mt-1 text-ink-primary">{value}</dd></div>;
}
