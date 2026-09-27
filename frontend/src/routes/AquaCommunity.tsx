/**
 * /aquahealth/community — participation and badges.
 *
 * Gamification is useful for sustaining citizen participation and dangerous if
 * it leaks into the science. It does not leak here: the backend computes
 * badges in `service.community_stats`, which `assess.py` never reads, so a
 * prolific contributor's observation is assessed by exactly the same rules as
 * a first-timer's. The page states that rather than leaving it implicit.
 */
import { Award, Droplets, Lock, Trophy, Users } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import { ErrorNote, LoadingNote, PageHeader } from "../aquahealth/panels";
import type { Badge, CommunityStats } from "../aquahealth/types";

export default function AquaCommunity() {
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    aqua
      .community()
      .then(setStats)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load community stats"),
      );
  }, []);

  if (error) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl">
        <ErrorNote message={error} />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl">
        <LoadingNote label="Loading community participation…" />
      </div>
    );
  }

  const earned = stats.badges.filter((b) => b.earned).length;

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <PageHeader
        eyebrow="AQUAHEALTH · COMMUNITY"
        title="Your contribution"
        description="Freshwater monitoring at city scale only works if people keep coming back. Here is what you and the wider community have contributed."
        actions={
          <Link
            to="/aquahealth/observations/new"
            className="rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
          >
            Record an observation
          </Link>
        }
      />

      <div className="space-y-5">
        {/* Your numbers */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            icon={<Droplets size={14} />}
            label="Observations contributed"
            value={stats.observations_contributed}
          />
          <Stat
            icon={<Droplets size={14} />}
            label="Waterbodies explored"
            value={stats.waterbodies_explored}
          />
          <Stat
            icon={<Award size={14} />}
            label="Reviewed contributions"
            value={stats.reviewed_contributions}
          />
          <Stat
            icon={<Trophy size={14} />}
            label="Badges earned"
            value={earned}
            suffix={` / ${stats.badges.length}`}
          />
        </div>

        {/* Badges */}
        <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
          <h2 className="text-sm text-ink-primary mb-1">Badges</h2>
          <p className="text-[11px] text-ink-muted mb-4">
            Recognition for sustained participation.
          </p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {stats.badges.map((b) => (
              <BadgeCard key={b.code} badge={b} />
            ))}
          </ul>
        </section>

        {/* Community */}
        <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
          <div className="flex items-center gap-2 mb-3">
            <Users size={14} className="text-accent-cyan" aria-hidden="true" />
            <h2 className="text-sm text-ink-primary">Across the community</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-surface-border bg-surface-panel p-4">
              <div className="text-data-numeric text-2xl text-ink-primary nums-tabular">
                {stats.community_observations}
              </div>
              <div className="text-[11px] text-ink-muted mt-0.5">
                observations recorded in this organisation
              </div>
            </div>
            <div className="rounded-xl border border-surface-border bg-surface-panel p-4">
              <div className="text-data-numeric text-2xl text-ink-primary nums-tabular">
                {stats.community_observers}
              </div>
              <div className="text-[11px] text-ink-muted mt-0.5">
                people contributing observations
              </div>
            </div>
          </div>
        </section>

        {/* The guarantee that matters */}
        <div className="rounded-xl border border-accent-blue/25 bg-accent-blue/5 p-4">
          <p className="text-[11px] text-ink-muted">{stats.note}</p>
        </div>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  suffix,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-center justify-between">
        <div className="text-compact text-[10px] text-ink-muted">{label}</div>
        <span className="text-ink-faint" aria-hidden="true">
          {icon}
        </span>
      </div>
      <div className="text-data-numeric text-3xl text-ink-primary mt-2 nums-tabular">
        {value}
        {suffix && <span className="text-sm text-ink-faint">{suffix}</span>}
      </div>
    </div>
  );
}

function BadgeCard({ badge }: { badge: Badge }) {
  const pct = badge.target > 0 ? Math.round((badge.progress / badge.target) * 100) : 0;
  return (
    <li
      className={
        badge.earned
          ? "rounded-xl border border-accent-green/40 bg-accent-green/5 p-4"
          : "rounded-xl border border-surface-border bg-surface-panel p-4"
      }
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {badge.earned ? (
            <Trophy size={15} className="text-accent-green" aria-hidden="true" />
          ) : (
            <Lock size={15} className="text-ink-faint" aria-hidden="true" />
          )}
          <span
            className={
              badge.earned ? "text-sm text-accent-green" : "text-sm text-ink-body"
            }
          >
            {badge.label}
          </span>
        </div>
        <span className="text-mono-tech text-[10px] text-ink-muted nums-tabular shrink-0">
          {badge.progress} / {badge.target}
        </span>
      </div>

      <p className="text-[11px] text-ink-muted mt-2">{badge.description}</p>

      {!badge.earned && (
        <div className="mt-2.5 h-1.5 w-full rounded-full bg-surface-border overflow-hidden">
          <div
            className="h-full rounded-full bg-accent-cyan"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </li>
  );
}
