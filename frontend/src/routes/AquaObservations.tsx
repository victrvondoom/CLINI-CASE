/**
 * /aquahealth/observations — every freshwater observation, filterable.
 *
 * Each row carries its data source and verification state, which the brief
 * calls essential: a reader must never have to guess whether a record is a
 * citizen report, a sensor feed or demonstration data, nor whether a human has
 * checked it.
 */
import { Filter, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  DemoBadge,
  EmptyState,
  ErrorNote,
  LoadingNote,
  PageHeader,
  STATUS_LABEL,
  SourceChip,
  StatusBadge,
  VerificationStateChip,
  formatDate,
} from "../aquahealth/panels";
import type {
  EcosystemStatus,
  ObservationSummary,
  ReviewStatus,
  WaterbodyRow,
} from "../aquahealth/types";

const selectClass =
  "rounded-md border border-surface-border bg-surface-bg px-2.5 py-1.5 text-[11px] text-ink-body focus:border-accent-cyan focus:outline-none transition-colors";

const STATUS_FILTERS: Array<{ value: EcosystemStatus | "all"; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "critical_signal", label: STATUS_LABEL.critical_signal },
  { value: "potential_stress", label: STATUS_LABEL.potential_stress },
  { value: "watch", label: STATUS_LABEL.watch },
  { value: "healthy_signal", label: STATUS_LABEL.healthy_signal },
  { value: "insufficient_data", label: STATUS_LABEL.insufficient_data },
];

const REVIEW_FILTERS: Array<{ value: ReviewStatus | "all"; label: string }> = [
  { value: "all", label: "Any review state" },
  { value: "pending_review", label: "Pending review" },
  { value: "in_review", label: "In review" },
  { value: "completed", label: "Reviewed" },
];

export default function AquaObservations() {
  const [rows, setRows] = useState<ObservationSummary[]>([]);
  const [waterbodies, setWaterbodies] = useState<WaterbodyRow[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [status, setStatus] = useState<EcosystemStatus | "all">("all");
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | "all">("all");
  const [waterbodyId, setWaterbodyId] = useState<string>("all");
  const [includeDemo, setIncludeDemo] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const res = await aqua.listObservations({
        status: status === "all" ? undefined : status,
        reviewStatus: reviewStatus === "all" ? undefined : reviewStatus,
        waterbodyId: waterbodyId === "all" ? undefined : waterbodyId,
        includeDemo,
        limit: 200,
      });
      setRows(res.observations);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load observations");
    } finally {
      setLoading(false);
    }
  }, [status, reviewStatus, waterbodyId, includeDemo]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    aqua
      .waterbodies()
      .then((r) => setWaterbodies(r.waterbodies))
      .catch(() => {
        /* filter stays on "all" — not worth surfacing an error for */
      });
  }, []);

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        eyebrow="AQUAHEALTH · OBSERVATIONS"
        title="Freshwater observations"
        description="Every citizen, sensor and demonstration record, with its provenance and verification state."
        actions={
          <Link
            to="/aquahealth/observations/new"
            className="inline-flex items-center gap-1.5 rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
          >
            <Plus size={13} aria-hidden="true" />
            New observation
          </Link>
        }
      />

      <div className="space-y-4">
        {/* Filters */}
        <div className="rounded-xl border border-surface-border bg-surface-raised p-4">
          <div className="flex items-center gap-2 mb-3">
            <Filter size={13} className="text-ink-muted" aria-hidden="true" />
            <span className="text-compact text-[10px] text-ink-muted">Filters</span>
          </div>
          <div className="flex gap-3 flex-wrap items-center">
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as EcosystemStatus | "all")}
              className={selectClass}
              aria-label="Filter by ecosystem status"
            >
              {STATUS_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>

            <select
              value={reviewStatus}
              onChange={(e) => setReviewStatus(e.target.value as ReviewStatus | "all")}
              className={selectClass}
              aria-label="Filter by review state"
            >
              {REVIEW_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>

            <select
              value={waterbodyId}
              onChange={(e) => setWaterbodyId(e.target.value)}
              className={selectClass}
              aria-label="Filter by waterbody"
            >
              <option value="all">All waterbodies</option>
              {waterbodies.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>

            <label className="flex items-center gap-1.5 text-[11px] text-ink-body cursor-pointer">
              <input
                type="checkbox"
                checked={includeDemo}
                onChange={(e) => setIncludeDemo(e.target.checked)}
                className="accent-accent-cyan"
              />
              Include demonstration data
            </label>

            <span className="text-[11px] text-ink-muted ml-auto">
              {total} observation{total === 1 ? "" : "s"}
            </span>
          </div>
        </div>

        {error && <ErrorNote message={error} />}
        {loading && <LoadingNote label="Loading observations…" />}

        {!loading && rows.length === 0 && !error && (
          <EmptyState
            title="No observations match these filters"
            detail="Try widening the filters, or record a new freshwater observation."
            action={
              <Link
                to="/aquahealth/observations/new"
                className="rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan"
              >
                New observation
              </Link>
            }
          />
        )}

        {!loading && rows.length > 0 && (
          <ul className="space-y-2">
            {rows.map((o) => (
              <li key={o.id}>
                <Link
                  to={`/aquahealth/observations/${o.id}`}
                  className="block rounded-xl border border-surface-border bg-surface-raised p-4 hover:border-accent-cyan/40 transition-colors group"
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-mono-tech text-[11px] text-ink-muted">
                          {o.reference}
                        </span>
                        <span className="text-sm text-ink-primary group-hover:text-accent-cyan transition-colors">
                          {o.waterbody_name}
                        </span>
                        {o.is_demo && <DemoBadge />}
                      </div>

                      {o.headline && (
                        <p className="text-[12px] text-ink-muted mt-1.5 line-clamp-2">
                          {o.headline}
                        </p>
                      )}

                      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                        <SourceChip source={o.source} />
                        <VerificationStateChip verification={o.verification} />
                        <span className="text-[10px] text-ink-faint">
                          {formatDate(o.observed_at)}
                        </span>
                        {o.review_status !== "completed" && (
                          <span className="text-[10px] text-accent-amber">
                            Awaiting review
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 flex flex-col items-end gap-1.5">
                      <StatusBadge status={o.status} size="sm" />
                      <span className="text-[10px] text-ink-faint">
                        {o.confidence} confidence · {o.data_quality} data
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
