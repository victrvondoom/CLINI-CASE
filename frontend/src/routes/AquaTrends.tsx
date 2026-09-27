/**
 * /aquahealth/trends — observations over time.
 *
 * The one rule this page enforces above all: when there is not enough history
 * it says so in plain words and draws nothing. A chart through two points
 * would look authoritative and mean nothing, which is precisely the failure
 * the brief warns against.
 */
import { TrendingUp } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  ErrorNote,
  LoadingNote,
  PageHeader,
  StatusBadge,
  formatDate,
} from "../aquahealth/panels";
import type { TrendPoint, TrendsResponse, WaterbodyRow } from "../aquahealth/types";

const selectClass =
  "rounded-md border border-surface-border bg-surface-bg px-2.5 py-1.5 text-[11px] text-ink-body focus:border-accent-cyan focus:outline-none transition-colors";

export default function AquaTrends() {
  const [data, setData] = useState<TrendsResponse | null>(null);
  const [waterbodies, setWaterbodies] = useState<WaterbodyRow[]>([]);
  const [waterbodyId, setWaterbodyId] = useState("all");
  const [days, setDays] = useState(90);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      setData(await aqua.trends(waterbodyId === "all" ? undefined : waterbodyId, days));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load trends");
    } finally {
      setLoading(false);
    }
  }, [waterbodyId, days]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    aqua
      .waterbodies()
      .then((r) => setWaterbodies(r.waterbodies))
      .catch(() => {
        /* selector stays on "all" */
      });
  }, []);

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        eyebrow="AQUAHEALTH · TRENDS"
        title="Observations over time"
        description="How signals at these waterbodies have changed across the observation record."
      />

      <div className="space-y-4">
        {/* Controls */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-4 flex gap-3 flex-wrap items-center">
          <select
            value={waterbodyId}
            onChange={(e) => setWaterbodyId(e.target.value)}
            className={selectClass}
            aria-label="Select waterbody"
          >
            <option value="all">All waterbodies</option>
            {waterbodies.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>

          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className={selectClass}
            aria-label="Select time window"
          >
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
            <option value={365}>Last year</option>
          </select>

          {data && (
            <span className="text-[11px] text-ink-muted ml-auto">
              {data.observation_count} observation
              {data.observation_count === 1 ? "" : "s"} in window
            </span>
          )}
        </div>

        {error && <ErrorNote message={error} />}
        {loading && <LoadingNote label="Loading trends…" />}

        {/* Insufficient data — the honest path */}
        {!loading && data && !data.sufficient && (
          <div className="rounded-2xl border border-surface-border bg-surface-raised p-8 text-center">
            <TrendingUp size={24} className="mx-auto text-ink-faint" aria-hidden="true" />
            <h2 className="text-sm text-ink-primary mt-3">
              Insufficient historical observations to determine a trend.
            </h2>
            <p className="text-[12px] text-ink-muted mt-2 max-w-md mx-auto">
              {data.message}
            </p>
            <p className="text-[11px] text-ink-faint mt-3 max-w-md mx-auto">
              A trend line drawn through too few observations would look
              authoritative while meaning nothing, so none is shown.
            </p>
            <Link
              to="/aquahealth/observations/new"
              className="mt-4 inline-block rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan"
            >
              Record an observation
            </Link>
          </div>
        )}

        {/* Series */}
        {!loading && data?.sufficient && (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <ChartCard
                title="Adverse signals per visit"
                subtitle="Higher means more concerning observations were reported"
                series={data.series}
                pick={(p) => p.adverse_signals}
                colour="rgb(var(--accent-amber))"
              />
              <ChartCard
                title="Biodiversity groups observed"
                subtitle="Higher means more life was seen"
                series={data.series}
                pick={(p) => p.biodiversity_positives}
                colour="rgb(var(--accent-green))"
              />
              <ChartCard
                title="Dissolved oxygen (mg/L)"
                subtitle="Only days where a measurement was supplied"
                series={data.series}
                pick={(p) => p.mean_dissolved_oxygen_mgl}
                colour="rgb(var(--accent-blue))"
              />
              <ChartCard
                title="Turbidity (NTU)"
                subtitle="Only days where a measurement was supplied"
                series={data.series}
                pick={(p) => p.mean_turbidity_ntu}
                colour="rgb(var(--accent-violet))"
              />
            </div>

            {/* Status history */}
            <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
              <h2 className="text-sm text-ink-primary mb-3">Ecosystem status history</h2>
              <ul className="space-y-1.5 max-h-80 overflow-y-auto">
                {[...data.status_history].reverse().map((h, i) => (
                  <li
                    key={`${h.reference}-${i}`}
                    className="flex items-center justify-between gap-3 py-1.5 border-b border-surface-border last:border-0"
                  >
                    <span className="min-w-0 flex items-center gap-2">
                      <span className="text-mono-tech text-[10px] text-ink-faint shrink-0">
                        {formatDate(h.date)}
                      </span>
                      <span className="text-[12px] text-ink-body truncate">
                        {h.waterbody_name}
                      </span>
                    </span>
                    <StatusBadge status={h.status} size="sm" />
                  </li>
                ))}
              </ul>
            </section>

            {data.note && <p className="text-[11px] text-ink-faint">{data.note}</p>}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Small inline line/area chart.
 *
 * Days with no measurement are skipped rather than plotted as zero — a missing
 * reading is not a reading of nothing.
 */
function ChartCard({
  title,
  subtitle,
  series,
  pick,
  colour,
}: {
  title: string;
  subtitle: string;
  series: TrendPoint[];
  pick: (p: TrendPoint) => number | null;
  colour: string;
}) {
  const pts = series
    .map((p) => ({ date: p.date, value: pick(p) }))
    .filter((p): p is { date: string; value: number } => p.value !== null);

  if (pts.length < 2) {
    return (
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5">
        <h3 className="text-sm text-ink-primary">{title}</h3>
        <p className="text-[10px] text-compact text-ink-faint mt-0.5">{subtitle}</p>
        <p className="text-[12px] text-ink-muted mt-4">
          Not enough measurements in this window to plot a line.
        </p>
      </div>
    );
  }

  const W = 600;
  const H = 160;
  const values = pts.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const coords = pts.map((p, idx) => {
    const x = (idx / (pts.length - 1)) * W;
    const y = H - ((p.value - min) / span) * (H - 20) - 10;
    return { x, y, ...p };
  });

  const line = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const area = `${line} L ${W} ${H} L 0 ${H} Z`;

  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm text-ink-primary">{title}</h3>
          <p className="text-[10px] text-compact text-ink-faint mt-0.5">{subtitle}</p>
        </div>
        <span className="text-data-numeric text-lg text-ink-primary nums-tabular">
          {values[values.length - 1]}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto mt-3"
        role="img"
        aria-label={`${title}: ${pts.length} points from ${pts[0].date} to ${pts[pts.length - 1].date}`}
      >
        <path d={area} fill={colour} opacity="0.08" />
        <path d={line} fill="none" stroke={colour} strokeWidth="2" />
        {coords.map((c) => (
          <circle key={c.date} cx={c.x} cy={c.y} r="3" fill={colour}>
            <title>
              {c.date}: {c.value}
            </title>
          </circle>
        ))}
      </svg>

      <div className="flex justify-between text-[10px] text-ink-faint mt-1">
        <span>{formatDate(pts[0].date)}</span>
        <span>{formatDate(pts[pts.length - 1].date)}</span>
      </div>
    </div>
  );
}
