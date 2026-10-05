/**
 * /aquahealth/map — observation locations.
 *
 * The repository ships no mapping library (no Leaflet, Mapbox or react-map-gl),
 * so rather than adding a dependency and a tile-server requirement this view
 * projects the observations into an inline SVG plot with a coordinate grid. It
 * answers the questions the brief asks of the map — where, when, what status,
 * how confident, reviewed or not — and works offline.
 *
 * Selecting a marker shows that observation's summary beside the plot.
 */
import { MapPin, Maximize2 } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  Chip,
  DemoBadge,
  EmptyState,
  ErrorNote,
  LoadingNote,
  PageHeader,
  STATUS_LABEL,
  StatusBadge,
  formatDate,
} from "../aquahealth/panels";
import type { EcosystemStatus, MapPoint, MapView } from "../aquahealth/types";

/** Marker fills. Mirrors the status ramp used everywhere else. */
const STATUS_FILL: Record<EcosystemStatus, string> = {
  critical_signal: "rgb(var(--accent-red))",
  potential_stress: "rgb(var(--accent-amber))",
  watch: "rgb(var(--accent-blue))",
  healthy_signal: "rgb(var(--accent-green))",
  insufficient_data: "rgb(var(--ink-faint))",
};

/** WebGL needs literal colours (CSS variables do not resolve inside three.js). */
const STATUS_HEX: Record<EcosystemStatus, string> = {
  critical_signal: "#ef4444",
  potential_stress: "#f59e0b",
  watch: "#3b82f6",
  healthy_signal: "#22c55e",
  insufficient_data: "#94a3b8",
};

const PAD = 0.12; // fraction of span added as breathing room around the extremes
const ObservationGlobe = lazy(() => import("../globe/ObservationGlobe"));
const AquaHealthMapLibre = lazy(() => import("../globe/AquaHealthMapLibre"));

export default function AquaMap() {
  const [data, setData] = useState<MapView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapPoint | null>(null);
  const [statusFilter, setStatusFilter] = useState<EcosystemStatus | "all">("all");
  const [mapMode, setMapMode] = useState<"street" | "globe">("street");

  useEffect(() => {
    aqua
      .map()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load the map"));
  }, []);

  const points = useMemo(() => {
    const all = data?.points ?? [];
    return statusFilter === "all" ? all : all.filter((p) => p.status === statusFilter);
  }, [data, statusFilter]);
  const selectPoint = useCallback((point: MapPoint) => setSelected(point), []);

  const globeMarkers = useMemo(
    () =>
      points.map((p) => ({
        id: p.observation_id,
        latitude: p.latitude,
        longitude: p.longitude,
        label: `${p.reference} · ${p.waterbody_name}`,
        color: STATUS_HEX[p.status],
      })),
    [points],
  );

  /** Project lat/lon into the 0..1000 x 0..600 viewBox. */
  const project = useCallback(
    (p: MapPoint) => {
      const all = data?.points ?? [];
      if (all.length === 0) return { x: 500, y: 300 };

      const lats = all.map((q) => q.latitude);
      const lons = all.map((q) => q.longitude);
      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      // A single point (or a perfectly aligned row) has zero span; give it one
      // so the projection does not divide by zero and collapse to a corner.
      const latSpan = maxLat - minLat || 0.01;
      const lonSpan = maxLon - minLon || 0.01;
      minLat -= latSpan * PAD;
      maxLat += latSpan * PAD;
      minLon -= lonSpan * PAD;
      maxLon += lonSpan * PAD;

      const x = ((p.longitude - minLon) / (maxLon - minLon)) * 1000;
      // SVG y grows downward; latitude grows north, so invert.
      const y = 600 - ((p.latitude - minLat) / (maxLat - minLat)) * 600;
      return { x, y };
    },
    [data],
  );

  if (error) {
    return (
      <div className="p-6 lg:p-8 max-w-[1400px]">
        <ErrorNote message={error} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 lg:p-8 max-w-[1400px]">
        <LoadingNote label="Loading observation map…" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        eyebrow="AQUAHEALTH · MAP"
        title="Observation locations"
        description="Where each freshwater observation was recorded, coloured by its prototype ecosystem status."
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent-cyan/30 bg-accent-cyan/5 p-4">
        <div>
          <h2 className="text-sm font-semibold text-ink-primary">Related Track 7 tools</h2>
          <p className="mt-1 text-xs text-ink-muted">Explore a synthetic environmental scenario, or open the separate Track 7 workbench for governed mapping and exchange.</p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link to="/oah-bridge" className="text-accent-cyan underline">Context explorer</Link>
          <Link to="/interop" className="text-accent-cyan underline">Track 7 exchange</Link>
        </div>
      </div>

      <section className="mb-4 rounded-2xl border border-surface-border bg-surface-raised p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-sm font-semibold text-ink-primary">Geographic evidence map</h2><p className="mt-1 text-[11px] text-ink-muted">Select a marker to open its AquaHealth observation.</p></div>
          <div className="flex gap-2" role="group" aria-label="Map display">
            <button type="button" aria-pressed={mapMode === "street"} onClick={() => setMapMode("street")} className="rounded-md border border-surface-border px-3 py-1.5 text-xs aria-pressed:border-accent-cyan aria-pressed:text-accent-cyan">Street map</button>
            <button type="button" aria-pressed={mapMode === "globe"} onClick={() => setMapMode("globe")} className="rounded-md border border-surface-border px-3 py-1.5 text-xs aria-pressed:border-accent-cyan aria-pressed:text-accent-cyan">3D globe & optional GPS</button>
          </div>
        </div>
        <Suspense fallback={<div className="h-[360px] animate-pulse rounded-xl bg-surface-bg" role="status">Loading map…</div>}>
          {mapMode === "street" ? <AquaHealthMapLibre points={points} selectedId={selected?.observation_id ?? null} onSelect={selectPoint} /> : <ObservationGlobe markers={globeMarkers} selectedId={selected?.observation_id ?? null} onSelect={(id) => setSelected(data.points.find((p) => p.observation_id === id) ?? null)} />}
        </Suspense>
      </section>

      {data.points.length === 0 ? (
        <EmptyState
          title="No mapped observations yet"
          detail="Observations appear here once they carry coordinates. Add a location when recording one, or load the demonstration dataset."
          action={
            <Link
              to="/aquahealth/observations/new"
              className="rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan"
            >
              New observation
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          {/* Retained relative plot and filters for offline review. */}
          <details className="rounded-2xl border border-surface-border bg-surface-raised p-4">
            <summary className="cursor-pointer text-sm font-semibold text-ink-primary">Offline coordinate plot and status filters</summary>
            <div className="mt-3">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
              <div className="flex items-center gap-2">
                <Maximize2 size={13} className="text-ink-muted" aria-hidden="true" />
                <span className="text-[11px] text-ink-muted">
                  {points.length} of {data.points.length} observation
                  {data.points.length === 1 ? "" : "s"}
                </span>
              </div>
              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(e.target.value as EcosystemStatus | "all")
                }
                className="rounded-md border border-surface-border bg-surface-bg px-2.5 py-1.5 text-[11px] text-ink-body focus:border-accent-cyan focus:outline-none"
                aria-label="Filter map by status"
              >
                <option value="all">All statuses</option>
                {(Object.keys(STATUS_LABEL) as EcosystemStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>

            <svg
              viewBox="0 0 1000 600"
              className="w-full h-auto rounded-xl bg-surface-bg border border-surface-border"
              role="img"
              aria-label="Map of freshwater observation locations"
            >
              <defs>
                <pattern
                  id="aqua-grid"
                  width="100"
                  height="60"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M 100 0 L 0 0 0 60"
                    fill="none"
                    stroke="rgb(var(--surface-border))"
                    strokeWidth="1"
                  />
                </pattern>
              </defs>
              <rect width="1000" height="600" fill="url(#aqua-grid)" />

              {points.map((p) => {
                const { x, y } = project(p);
                const isSelected = selected?.observation_id === p.observation_id;
                return (
                  <g
                    key={p.observation_id}
                    transform={`translate(${x} ${y})`}
                    onClick={() => setSelected(p)}
                    className="cursor-pointer"
                    role="button"
                    tabIndex={0}
                    aria-label={`${p.reference} at ${p.waterbody_name}, status ${STATUS_LABEL[p.status]}`}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") setSelected(p);
                    }}
                  >
                    {isSelected && (
                      <circle r="18" fill={STATUS_FILL[p.status]} opacity="0.2" />
                    )}
                    <circle
                      r={isSelected ? 10 : 7}
                      fill={STATUS_FILL[p.status]}
                      stroke="rgb(var(--surface-bg))"
                      strokeWidth="2"
                    />
                    {p.review_status !== "completed" && (
                      <circle
                        r={isSelected ? 14 : 11}
                        fill="none"
                        stroke={STATUS_FILL[p.status]}
                        strokeWidth="1"
                        strokeDasharray="2 2"
                        opacity="0.7"
                      />
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Legend */}
            <div className="flex items-center gap-3 flex-wrap mt-3">
              {(Object.keys(STATUS_LABEL) as EcosystemStatus[]).map((s) => (
                <span
                  key={s}
                  className="flex items-center gap-1.5 text-[10px] text-ink-muted"
                >
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: STATUS_FILL[s] }}
                    aria-hidden="true"
                  />
                  {STATUS_LABEL[s]}
                </span>
              ))}
              <span className="flex items-center gap-1.5 text-[10px] text-ink-faint ml-auto">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full border border-dashed border-ink-faint"
                  aria-hidden="true"
                />
                Dashed ring = awaiting human review
              </span>
            </div>

            <p className="text-[10px] text-ink-faint mt-2">
              Relative-position plot, not a geographic basemap. Marker spacing
              reflects real coordinates but is scaled to fit the observations
              currently shown.
            </p>
            </div>
          </details>

          {/* Selection */}
          <div className="space-y-3">
            {selected ? (
              <div className="rounded-2xl border border-surface-border bg-surface-raised p-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-mono-tech text-[11px] text-ink-muted">
                    {selected.reference}
                  </span>
                  {selected.is_demo && <DemoBadge />}
                </div>
                <h2 className="text-sm text-ink-primary mt-1">
                  {selected.waterbody_name}
                </h2>

                <div className="mt-3">
                  <StatusBadge status={selected.status} />
                </div>

                <dl className="mt-3 space-y-1.5 text-[11px]">
                  <Row label="Observed" value={formatDate(selected.observed_at)} />
                  <Row label="Confidence" value={selected.confidence} />
                  <Row label="Review" value={selected.review_status.replace(/_/g, " ")} />
                  <Row
                    label="Verification"
                    value={selected.verification.replace(/_/g, " ")}
                  />
                  <Row
                    label="Coordinates"
                    value={`${selected.latitude.toFixed(4)}, ${selected.longitude.toFixed(4)}`}
                  />
                </dl>

                {selected.summary && (
                  <p className="text-[12px] text-ink-muted mt-3 pt-3 border-t border-surface-border">
                    {selected.summary}
                  </p>
                )}

                <Link
                  to={`/aquahealth/observations/${selected.observation_id}`}
                  className="mt-3 inline-block rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-1.5 text-[11px] text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
                >
                  Open full record
                </Link>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-surface-border bg-surface-raised/50 p-6 text-center">
                <MapPin size={20} className="mx-auto text-ink-faint" aria-hidden="true" />
                <p className="text-[12px] text-ink-muted mt-2">
                  Select a marker to see that observation.
                </p>
              </div>
            )}

            {/* Waterbodies */}
            <div className="rounded-2xl border border-surface-border bg-surface-raised p-4">
              <h2 className="text-sm text-ink-primary mb-2">Waterbodies</h2>
              <ul className="space-y-1.5">
                {data.waterbodies.map((w) => (
                  <li
                    key={w.id}
                    className="flex items-center justify-between gap-2 text-[11px]"
                  >
                    <span className="text-ink-body truncate">{w.name}</span>
                    <Chip className="bg-surface-bg text-ink-faint border-surface-border shrink-0">
                      {w.kind}
                    </Chip>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-ink-body text-right">{value}</dd>
    </div>
  );
}
