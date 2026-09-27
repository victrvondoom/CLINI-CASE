/**
 * /aquahealth/review — the environmental human-in-the-loop queue.
 *
 * Completely separate from ClinCase's clinical /reviewer queue, which is
 * untouched. Ordering is by severity so a critical signal is never buried
 * under routine records, and a reviewer can act on an observation inline
 * without losing their place in the queue.
 */
import { Check, ClipboardCheck, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  DemoBadge,
  EmptyState,
  ErrorNote,
  LoadingNote,
  PageHeader,
  SourceChip,
  StatusBadge,
  VerificationStateChip,
  formatDate,
} from "../aquahealth/panels";
import type {
  EcosystemStatus,
  ObservationSummary,
  ReviewDecision,
  ReviewQueue,
} from "../aquahealth/types";

const STATUS_CHOICES: EcosystemStatus[] = [
  "healthy_signal",
  "watch",
  "potential_stress",
  "critical_signal",
  "insufficient_data",
];

export default function AquaReview() {
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [decision, setDecision] = useState<ReviewDecision>("accepted");
  const [comment, setComment] = useState("");
  const [corrected, setCorrected] = useState<EcosystemStatus>("watch");

  const load = useCallback(async () => {
    try {
      setError(null);
      setQueue(await aqua.reviewQueue());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the review queue");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function openFor(id: string) {
    setOpenId((prev) => (prev === id ? null : id));
    setDecision("accepted");
    setComment("");
    setCorrected("watch");
  }

  async function submit(observationId: string) {
    setBusyId(observationId);
    setError(null);
    try {
      await aqua.review(observationId, {
        decision,
        comment: comment.trim() || null,
        corrected_status: decision === "modified" ? corrected : null,
      });
      setOpenId(null);
      setComment("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the review");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1100px]">
      <PageHeader
        eyebrow="AQUAHEALTH · HUMAN REVIEW"
        title="Environmental review queue"
        description="Confirm, correct or reject AI assessments. The reviewer's decision is what the dashboard, map and trends report."
      />

      <div className="space-y-4">
        {error && <ErrorNote message={error} />}
        {!queue && !error && <LoadingNote label="Loading review queue…" />}

        {queue && queue.observations.length === 0 && (
          <EmptyState
            title="Nothing awaiting review"
            detail="Every observation has been through human verification. New submissions will appear here automatically."
            action={
              <Link
                to="/aquahealth"
                className="rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body"
              >
                Back to overview
              </Link>
            }
          />
        )}

        {queue && queue.observations.length > 0 && (
          <>
            <div className="flex items-center gap-2 text-[11px] text-ink-muted">
              <ClipboardCheck size={13} aria-hidden="true" />
              {queue.total} observation{queue.total === 1 ? "" : "s"} awaiting human
              verification · most concerning first
            </div>

            <ul className="space-y-2">
              {queue.observations.map((o) => (
                <li
                  key={o.id}
                  className="rounded-xl border border-surface-border bg-surface-raised overflow-hidden"
                >
                  <QueueRow
                    obs={o}
                    onToggle={() => openFor(o.id)}
                    open={openId === o.id}
                  />

                  {openId === o.id && (
                    <div className="border-t border-surface-border p-4 bg-surface-panel">
                      <div className="flex gap-1.5 flex-wrap">
                        {queue.decisions.map((d) => (
                          <button
                            key={d.value}
                            type="button"
                            onClick={() => setDecision(d.value)}
                            aria-pressed={decision === d.value}
                            className={
                              decision === d.value
                                ? "rounded-md border border-accent-cyan/50 bg-accent-cyan/15 px-3 py-1.5 text-xs text-accent-cyan transition-colors"
                                : "rounded-md border border-surface-border bg-surface-bg px-3 py-1.5 text-xs text-ink-muted hover:text-ink-body transition-colors"
                            }
                          >
                            {d.label}
                          </button>
                        ))}
                      </div>

                      {decision === "modified" && (
                        <div className="mt-3">
                          <span className="text-compact text-[10px] text-ink-muted">
                            Corrected status
                          </span>
                          <div className="mt-1.5 flex gap-1.5 flex-wrap">
                            {STATUS_CHOICES.map((s) => (
                              <button
                                key={s}
                                type="button"
                                onClick={() => setCorrected(s)}
                                aria-pressed={corrected === s}
                                className={
                                  corrected === s
                                    ? "rounded-md border border-accent-cyan/50 bg-accent-cyan/10 p-0.5"
                                    : "rounded-md border border-transparent p-0.5 opacity-60 hover:opacity-100 transition-opacity"
                                }
                              >
                                <StatusBadge status={s} size="sm" />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        rows={2}
                        placeholder="Comment (optional) — what did you verify, and how?"
                        className="mt-3 w-full rounded-md border border-surface-border bg-surface-bg px-3 py-2 text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-cyan focus:outline-none resize-y transition-colors"
                      />

                      <div className="flex items-center gap-3 mt-3 flex-wrap">
                        <button
                          type="button"
                          onClick={() => void submit(o.id)}
                          disabled={busyId === o.id}
                          className="inline-flex items-center gap-2 rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-3 py-2 text-xs text-accent-cyan hover:bg-accent-cyan/25 disabled:opacity-50 transition-colors"
                        >
                          {busyId === o.id ? (
                            <Loader2
                              size={13}
                              className="animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <Check size={13} aria-hidden="true" />
                          )}
                          Record decision
                        </button>
                        <Link
                          to={`/aquahealth/observations/${o.id}`}
                          className="text-[11px] text-accent-cyan hover:underline"
                        >
                          Open full record and evidence
                        </Link>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

function QueueRow({
  obs,
  onToggle,
  open,
}: {
  obs: ObservationSummary;
  onToggle: () => void;
  open: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="w-full text-left p-4 hover:bg-surface-raised-hi transition-colors"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-mono-tech text-[11px] text-ink-muted">
              {obs.reference}
            </span>
            <span className="text-sm text-ink-primary">{obs.waterbody_name}</span>
            {obs.is_demo && <DemoBadge />}
          </div>

          {obs.headline && (
            <p className="text-[12px] text-ink-muted mt-1.5 line-clamp-2">
              {obs.headline}
            </p>
          )}

          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            <SourceChip source={obs.source} />
            <VerificationStateChip verification={obs.verification} />
            <span className="text-[10px] text-ink-faint">
              {formatDate(obs.observed_at)} · {obs.confidence} confidence ·{" "}
              {obs.data_quality} data
            </span>
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-2">
          <StatusBadge status={obs.status} size="sm" />
          <span className="text-[11px] text-accent-cyan">
            {open ? "Close" : "Review"}
          </span>
        </div>
      </div>
    </button>
  );
}
