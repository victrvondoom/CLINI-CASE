/**
 * /aquahealth — AquaHealth overview dashboard.
 *
 * Additive: ClinCase's own /dashboard is untouched. This page covers the
 * OneAquaHealth data-to-insight track — counts, ecosystem-status distribution,
 * data-confidence summary, the prototype early-warning panel, recent
 * observations, and the "why this matters" storytelling section.
 */
import {
  AlertTriangle,
  ArrowRight,
  Database,
  Droplets,
  Fish,
  Gauge,
  Leaf,
  Plus,
  Recycle,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  DemoBadge,
  ErrorNote,
  LoadingNote,
  PageHeader,
  PrototypeNotice,
  STATUS_LABEL,
  SourceChip,
  StatusBadge,
  VerificationStateChip,
  formatDate,
} from "../aquahealth/panels";
import type {
  AquaMeta,
  DashboardOverview,
  EcosystemStatus,
  ObservationSummary,
} from "../aquahealth/types";
import { useAuth } from "../components/AuthContext";

const STATUS_ORDER: EcosystemStatus[] = [
  "critical_signal",
  "potential_stress",
  "watch",
  "healthy_signal",
  "insufficient_data",
];

const STATUS_BAR: Record<EcosystemStatus, string> = {
  critical_signal: "bg-accent-red",
  potential_stress: "bg-accent-amber",
  watch: "bg-accent-blue",
  healthy_signal: "bg-accent-green",
  insufficient_data: "bg-surface-border-hi",
};

export default function AquaDashboard() {
  const { user } = useAuth();
  const canSeed = user?.role === "reviewer" || user?.role === "admin";

  const [data, setData] = useState<DashboardOverview | null>(null);
  const [meta, setMeta] = useState<AquaMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [overview, m] = await Promise.all([aqua.overview(), aqua.meta()]);
      setData(overview);
      setMeta(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load AquaHealth overview");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function seed() {
    setBusy(true);
    try {
      await aqua.seedDemo();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to seed demonstration data");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        eyebrow="AQUAHEALTH · ONEAQUAHEALTH MODULE"
        title="Freshwater ecosystem overview"
        description={
          meta?.summary ??
          "Urban freshwater monitoring built on citizen observations, with AI-assisted assessment and human verification."
        }
        actions={
          <>
            {canSeed && (
              <button
                type="button"
                onClick={seed}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 hover:text-ink-primary disabled:opacity-50 transition-colors"
              >
                <Database size={13} aria-hidden="true" />
                {busy ? "Seeding…" : "Load demo data"}
              </button>
            )}
            <Link
              to="/aquahealth/observations/new"
              className="inline-flex items-center gap-1.5 rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
            >
              <Plus size={13} aria-hidden="true" />
              New observation
            </Link>
          </>
        }
      />

      <div className="space-y-6">
        <PrototypeNotice />

        {error && <ErrorNote message={error} />}
        {!data && !error && <LoadingNote label="Loading freshwater overview…" />}

        {data && (
          <>
            {data.observation_count === 0 ? (
              <div className="rounded-2xl border border-dashed border-surface-border bg-surface-raised/50 p-10 text-center">
                <Droplets size={28} className="mx-auto text-ink-faint" aria-hidden="true" />
                <div className="text-ink-primary text-sm mt-3">
                  No freshwater observations yet
                </div>
                <p className="text-ink-muted text-[12px] mt-1.5 max-w-md mx-auto">
                  Submit a citizen observation to begin, or load the clearly-labelled
                  demonstration dataset to explore the dashboard, map and trends.
                </p>
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Link
                    to="/aquahealth/observations/new"
                    className="rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan"
                  >
                    New observation
                  </Link>
                  {canSeed && (
                    <button
                      type="button"
                      onClick={seed}
                      disabled={busy}
                      className="rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body disabled:opacity-50"
                    >
                      {busy ? "Seeding…" : "Load demo data"}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <>
                {/* KPI row */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Tile
                    eyebrow="Waterbodies"
                    value={String(data.waterbody_count)}
                    hint="Freshwater features under observation"
                    icon={<Droplets size={14} />}
                  />
                  <Tile
                    eyebrow="Observations"
                    value={String(data.observation_count)}
                    hint={
                      data.demo_observation_count > 0
                        ? `${data.demo_observation_count} are demonstration data`
                        : "All from real contributors"
                    }
                    icon={<Leaf size={14} />}
                  />
                  <Tile
                    eyebrow="Awaiting review"
                    value={String(data.awaiting_review)}
                    hint="Human verification still required"
                    icon={<Users size={14} />}
                    accent={data.awaiting_review > 0 ? "text-accent-amber" : undefined}
                  />
                  <Tile
                    eyebrow="Active signals"
                    value={String(data.active_warnings.length)}
                    hint="Prototype early-warning signals"
                    icon={<AlertTriangle size={14} />}
                    accent={
                      data.active_warnings.length > 0 ? "text-accent-red" : undefined
                    }
                  />
                </div>

                {/* Early warning */}
                {data.active_warnings.length > 0 && (
                  <section className="rounded-2xl border border-accent-red/30 bg-accent-red/5 p-5">
                    <div className="flex items-center gap-2">
                      <AlertTriangle
                        size={15}
                        className="text-accent-red"
                        aria-hidden="true"
                      />
                      <h2 className="text-sm text-ink-primary">
                        Potential environmental signal
                      </h2>
                    </div>
                    <p className="text-[11px] text-ink-muted mt-1.5">
                      Informational prototype signals — not real-time monitoring and
                      not an autonomous emergency alert. Each recommends human field
                      verification.
                    </p>
                    <ul className="mt-3 space-y-2">
                      {data.active_warnings.map((o) => (
                        <li key={o.id}>
                          <Link
                            to={`/aquahealth/observations/${o.id}`}
                            className="flex items-center justify-between gap-3 rounded-lg border border-surface-border bg-surface-panel px-3 py-2 hover:border-accent-red/40 transition-colors"
                          >
                            <span className="min-w-0">
                              <span className="text-mono-tech text-[11px] text-ink-muted">
                                {o.reference}
                              </span>
                              <span className="text-sm text-ink-primary ml-2">
                                {o.waterbody_name}
                              </span>
                              {o.is_demo && <DemoBadge className="ml-2" />}
                            </span>
                            <span className="flex items-center gap-2 shrink-0">
                              <StatusBadge status={o.status} size="sm" />
                              <ArrowRight
                                size={13}
                                className="text-ink-faint"
                                aria-hidden="true"
                              />
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Distributions */}
                <div className="grid gap-4 lg:grid-cols-3">
                  <Panel
                    title="Ecosystem status"
                    subtitle="Prototype Ecosystem Observation Status"
                  >
                    <Distribution
                      dist={data.status_distribution}
                      order={STATUS_ORDER}
                      labels={STATUS_LABEL}
                      bars={STATUS_BAR}
                      total={data.observation_count}
                    />
                  </Panel>

                  <Panel title="Data confidence" subtitle="How sure the assessment is">
                    <SimpleBars
                      dist={data.confidence_distribution}
                      order={["high", "medium", "low"]}
                      colors={{
                        high: "bg-accent-violet",
                        medium: "bg-accent-blue",
                        low: "bg-surface-border-hi",
                      }}
                      total={data.observation_count}
                    />
                    <div className="mt-4 pt-3 border-t border-surface-border">
                      <div className="text-compact text-[10px] text-ink-faint mb-2">
                        Data quality
                      </div>
                      <SimpleBars
                        dist={data.data_quality_distribution}
                        order={["good", "limited", "insufficient"]}
                        colors={{
                          good: "bg-accent-green",
                          limited: "bg-accent-amber",
                          insufficient: "bg-accent-red",
                        }}
                        total={data.observation_count}
                      />
                    </div>
                  </Panel>

                  <Panel title="Data sources" subtitle="Where each record came from">
                    <SimpleBars
                      dist={data.source_distribution}
                      order={[
                        "citizen_observation",
                        "sensor",
                        "imported_dataset",
                        "demonstration_data",
                      ]}
                      labels={{
                        citizen_observation: "Citizen observation",
                        sensor: "Sensor",
                        imported_dataset: "Imported dataset",
                        demonstration_data: "Demonstration data",
                      }}
                      colors={{
                        citizen_observation: "bg-accent-cyan",
                        sensor: "bg-accent-blue",
                        imported_dataset: "bg-accent-violet",
                        demonstration_data: "bg-accent-amber",
                      }}
                      total={data.observation_count}
                    />
                  </Panel>
                </div>

                {/* Key panels */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <LinkPanel
                    to="/aquahealth/map"
                    icon={<Droplets size={15} />}
                    title="Map"
                    detail="Observation locations with status, confidence and review state."
                  />
                  <LinkPanel
                    to="/aquahealth/trends"
                    icon={<Gauge size={15} />}
                    title="Trends"
                    detail="Observations over time. Reports insufficient data rather than guessing."
                  />
                  <LinkPanel
                    to="/aquahealth/one-health"
                    icon={<Fish size={15} />}
                    title="One Health"
                    detail="Ecosystem to biodiversity to community-health relevance."
                  />
                  <LinkPanel
                    to="/aquahealth/review"
                    icon={<Users size={15} />}
                    title="Review queue"
                    detail={`${data.awaiting_review} observation(s) awaiting human verification.`}
                  />
                  <LinkPanel
                    to="/aquahealth/observations"
                    icon={<Leaf size={15} />}
                    title="All observations"
                    detail="Every record with its source and verification state."
                  />
                  <LinkPanel
                    to="/aquahealth/community"
                    icon={<Recycle size={15} />}
                    title="Community"
                    detail="Participation, contributions and badges."
                  />
                </div>

                {/* Recent */}
                <Panel
                  title="Recent observations"
                  subtitle="Newest citizen contributions first"
                  action={
                    <Link
                      to="/aquahealth/observations"
                      className="text-[11px] text-accent-cyan hover:underline"
                    >
                      View all
                    </Link>
                  }
                >
                  <ul className="divide-y divide-surface-border">
                    {data.recent.map((o) => (
                      <RecentRow key={o.id} obs={o} />
                    ))}
                  </ul>
                </Panel>
              </>
            )}

            {/* Why this matters — awareness / storytelling track */}
            <section className="rounded-2xl border border-surface-border bg-surface-raised p-6">
              <div className="text-compact text-[10px] text-accent-cyan">
                WHY THIS MATTERS
              </div>
              <h2 className="text-display text-lg text-ink-primary mt-1">
                Healthy water, healthy ecosystem, healthy communities
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <Because
                  icon={<Droplets size={16} />}
                  title="Healthy water"
                  detail="Urban streams, canals and ponds are the first place pollution, runoff and discharge become visible — often long before any monitoring station registers it."
                />
                <Because
                  icon={<Fish size={16} />}
                  title="Healthy ecosystem"
                  detail="The fish, insects and plants living in that water are a continuous, sensitive record of its condition. Their absence is as informative as their presence."
                />
                <Because
                  icon={<Users size={16} />}
                  title="Healthy communities"
                  detail="People walk, play and fish beside these waters. An ecosystem signal is an early, actionable hint about where to look for community relevance."
                />
              </div>
              <p className="text-[11px] text-ink-faint mt-4 pt-3 border-t border-surface-border">
                Residents notice change first. AquaHealth turns those observations into
                structured, explainable evidence a human expert can act on — while
                being explicit about what the data cannot yet support.
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Local components
// =============================================================================

function Tile({
  eyebrow,
  value,
  hint,
  icon,
  accent,
}: {
  eyebrow: string;
  value: string;
  hint: string;
  icon: ReactNode;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 hover:border-accent-cyan/30 transition-colors">
      <div className="flex items-center justify-between">
        <div className="text-compact text-[10px] text-ink-muted">{eyebrow}</div>
        <span className="text-ink-faint" aria-hidden="true">
          {icon}
        </span>
      </div>
      <div
        className={`text-data-numeric text-3xl mt-2 nums-tabular ${accent ?? "text-ink-primary"}`}
      >
        {value}
      </div>
      <div className="text-[11px] text-ink-muted mt-1">{hint}</div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm text-ink-primary">{title}</h2>
          {subtitle && (
            <p className="text-[10px] text-compact text-ink-faint mt-0.5">{subtitle}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function LinkPanel({
  to,
  icon,
  title,
  detail,
}: {
  to: string;
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <Link
      to={to}
      className="group rounded-2xl border border-surface-border bg-surface-raised p-5 hover:border-accent-cyan/40 transition-colors"
    >
      <div className="flex items-center gap-2 text-accent-cyan">
        {icon}
        <span className="text-sm text-ink-primary group-hover:text-accent-cyan transition-colors">
          {title}
        </span>
      </div>
      <p className="text-[12px] text-ink-muted mt-2">{detail}</p>
      <div className="mt-3 flex items-center gap-1 text-[11px] text-accent-cyan opacity-0 group-hover:opacity-100 transition-opacity">
        Open <ArrowRight size={11} aria-hidden="true" />
      </div>
    </Link>
  );
}

function Distribution({
  dist,
  order,
  labels,
  bars,
  total,
}: {
  dist: Record<string, number>;
  order: EcosystemStatus[];
  labels: Record<EcosystemStatus, string>;
  bars: Record<EcosystemStatus, string>;
  total: number;
}) {
  return (
    <ul className="space-y-2.5">
      {order.map((k) => {
        const n = dist[k] ?? 0;
        const pct = total > 0 ? Math.round((n / total) * 100) : 0;
        return (
          <li key={k}>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-ink-body">{labels[k]}</span>
              <span className="text-mono-tech text-ink-muted nums-tabular">
                {n} · {pct}%
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-surface-border overflow-hidden">
              <div
                className={`h-full rounded-full ${bars[k]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function SimpleBars({
  dist,
  order,
  labels,
  colors,
  total,
}: {
  dist: Record<string, number>;
  order: string[];
  labels?: Record<string, string>;
  colors: Record<string, string>;
  total: number;
}) {
  const shown = order.filter((k) => (dist[k] ?? 0) > 0);
  if (shown.length === 0) {
    return <p className="text-[11px] text-ink-faint">No data yet.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {shown.map((k) => {
        const n = dist[k] ?? 0;
        const pct = total > 0 ? Math.round((n / total) * 100) : 0;
        return (
          <li key={k}>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-ink-body capitalize">
                {labels?.[k] ?? k.replace(/_/g, " ")}
              </span>
              <span className="text-mono-tech text-ink-muted nums-tabular">{n}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-surface-border overflow-hidden">
              <div
                className={`h-full rounded-full ${colors[k] ?? "bg-surface-border-hi"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function RecentRow({ obs }: { obs: ObservationSummary }) {
  return (
    <li className="py-2.5 first:pt-0 last:pb-0">
      <Link
        to={`/aquahealth/observations/${obs.id}`}
        className="flex items-start justify-between gap-3 group"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-mono-tech text-[11px] text-ink-muted">
              {obs.reference}
            </span>
            <span className="text-sm text-ink-primary group-hover:text-accent-cyan transition-colors">
              {obs.waterbody_name}
            </span>
            {obs.is_demo && <DemoBadge />}
          </div>
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <SourceChip source={obs.source} />
            <VerificationStateChip verification={obs.verification} />
            <span className="text-[10px] text-ink-faint">
              {formatDate(obs.observed_at)}
            </span>
          </div>
          {obs.headline && (
            <p className="text-[11px] text-ink-muted mt-1.5 line-clamp-1">
              {obs.headline}
            </p>
          )}
        </div>
        <div className="shrink-0">
          <StatusBadge status={obs.status} size="sm" />
        </div>
      </Link>
    </li>
  );
}

function Because({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-panel p-4">
      <div className="flex items-center gap-2 text-accent-cyan">
        {icon}
        <span className="text-sm text-ink-primary">{title}</span>
      </div>
      <p className="text-[12px] text-ink-muted mt-2">{detail}</p>
    </div>
  );
}
