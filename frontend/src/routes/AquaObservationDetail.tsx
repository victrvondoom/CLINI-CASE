/**
 * /aquahealth/observations/:observationId — full record + explainable assessment
 * + the human-in-the-loop review control.
 *
 * This page is where the explainability contract is honoured: the prototype
 * status is shown with the reason that produced it, every agent finding is
 * rendered with its evidence rows, confidence, data quality, uncertainty and
 * recommended next step, and the reviewer can accept, modify, reject or ask for
 * more information. No chain-of-thought is ever displayed — only findings
 * traceable to fields the observer filled in.
 */
import {
  ArrowLeft,
  Bot,
  Check,
  Download,
  Loader2,
  MapPin,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  Chip,
  DemoBadge,
  ErrorNote,
  FindingCard,
  LoadingNote,
  PageHeader,
  PresencePill,
  PrototypeStatusHeader,
  SourceChip,
  StatusBadge,
  VerificationStateChip,
  formatDateTime,
} from "../aquahealth/panels";
import type {
  EcosystemStatus,
  Observation,
  Presence,
  ReviewDecision,
} from "../aquahealth/types";
import { useAuth } from "../components/AuthContext";

const STATUS_CHOICES: EcosystemStatus[] = [
  "healthy_signal",
  "watch",
  "potential_stress",
  "critical_signal",
  "insufficient_data",
];

const MEASUREMENT_LABEL: Record<string, { label: string; unit: string }> = {
  ph: { label: "pH", unit: "" },
  water_temperature_c: { label: "Water temperature", unit: "°C" },
  turbidity_ntu: { label: "Turbidity", unit: "NTU" },
  dissolved_oxygen_mgl: { label: "Dissolved oxygen", unit: "mg/L" },
};

export default function AquaObservationDetail() {
  const { observationId } = useParams<{ observationId: string }>();
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";

  const [obs, setObs] = useState<Observation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [decision, setDecision] = useState<ReviewDecision>("accepted");
  const [comment, setComment] = useState("");
  const [corrected, setCorrected] = useState<EcosystemStatus>("watch");

  const load = useCallback(async () => {
    if (!observationId) return;
    try {
      setError(null);
      setObs(await aqua.getObservation(observationId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the observation");
    }
  }, [observationId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submitReview() {
    if (!observationId) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await aqua.review(observationId, {
        decision,
        comment: comment.trim() || null,
        corrected_status: decision === "modified" ? corrected : null,
      });
      setObs(updated);
      setComment("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the review");
    } finally {
      setBusy(false);
    }
  }

  async function reassess() {
    if (!observationId) return;
    setBusy(true);
    try {
      setObs(await aqua.reassess(observationId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not re-run the assessment");
    } finally {
      setBusy(false);
    }
  }

  async function downloadExport(format: "prototype" | "fhir") {
    if (!observationId) return;
    try {
      const doc = await aqua.exportObservation(observationId, format);
      const blob = new Blob([JSON.stringify(doc, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${obs?.reference ?? "observation"}-${format}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  if (error && !obs) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl space-y-4">
        <BackLink />
        <ErrorNote message={error} />
      </div>
    );
  }

  if (!obs) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl space-y-4">
        <BackLink />
        <LoadingNote label="Loading observation…" />
      </div>
    );
  }

  const a = obs.assessment;
  const measurements = Object.entries(obs.measurements).filter(
    ([, v]) => v !== null && v !== undefined,
  );

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <BackLink />

      <PageHeader
        eyebrow={`AQUAHEALTH · ${obs.reference}`}
        title={obs.waterbody_name}
        description={
          obs.locality
            ? `${obs.locality} · observed ${formatDateTime(obs.observed_at)}`
            : `Observed ${formatDateTime(obs.observed_at)}`
        }
        actions={
          <>
            <button
              type="button"
              onClick={() => void downloadExport("prototype")}
              className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 transition-colors"
            >
              <Download size={13} aria-hidden="true" />
              JSON
            </button>
            <button
              type="button"
              onClick={() => void downloadExport("fhir")}
              className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 transition-colors"
            >
              <Download size={13} aria-hidden="true" />
              FHIR
            </button>
            {canReview && (
              <button
                type="button"
                onClick={reassess}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 disabled:opacity-50 transition-colors"
              >
                <RefreshCw size={13} aria-hidden="true" />
                Re-assess
              </button>
            )}
          </>
        }
      />

      <div className="space-y-5">
        {/* Provenance — required on every record */}
        <div className="flex items-center gap-2 flex-wrap">
          <SourceChip source={obs.source} />
          <VerificationStateChip verification={obs.verification} />
          <Chip className="bg-surface-raised text-ink-muted border-surface-border">
            {obs.case_type}
          </Chip>
          {obs.is_demo && <DemoBadge />}
          {obs.location && (
            <Chip
              className="bg-surface-raised text-ink-muted border-surface-border"
              icon={<MapPin size={11} />}
            >
              {obs.location.latitude.toFixed(4)}, {obs.location.longitude.toFixed(4)}
            </Chip>
          )}
        </div>

        {error && <ErrorNote message={error} />}

        {/* Prototype status */}
        {a ? (
          <PrototypeStatusHeader
            status={obs.review?.corrected_status ?? a.status}
            reason={
              obs.review?.corrected_status
                ? `Reviewer set this status. Original AI assessment: ${a.status.replace(
                    /_/g,
                    " ",
                  )}. ${a.status_reason}`
                : a.status_reason
            }
            confidence={a.confidence}
            dataQuality={a.data_quality}
            humanVerification={a.human_verification}
          />
        ) : (
          <LoadingNote label="Assessment pending…" />
        )}

        {/* Review outcome */}
        {obs.review && (
          <section className="rounded-2xl border border-accent-violet/30 bg-accent-violet/5 p-5">
            <h2 className="text-sm text-ink-primary">Human review</h2>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <Chip className="bg-accent-violet/10 text-accent-violet border-accent-violet/30">
                {obs.review.decision.replace(/_/g, " ")}
              </Chip>
              <span className="text-[11px] text-ink-muted">
                {obs.review.reviewer_label} · {formatDateTime(obs.review.reviewed_at)}
              </span>
            </div>
            {obs.review.corrected_status && (
              <div className="mt-2 flex items-center gap-2 text-[12px] text-ink-body">
                <span>Status corrected to</span>
                <StatusBadge status={obs.review.corrected_status} size="sm" />
              </div>
            )}
            {obs.review.comment && (
              <p className="text-[12px] text-ink-body mt-2">{obs.review.comment}</p>
            )}
          </section>
        )}

        {/* AI findings */}
        {a && a.findings.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Bot size={14} className="text-accent-cyan" aria-hidden="true" />
              <h2 className="text-sm text-ink-primary">
                AI assessment — {a.findings.length} agent findings
              </h2>
            </div>
            <div className="space-y-3">
              {a.findings.map((f) => (
                <FindingCard key={f.agent} finding={f} />
              ))}
            </div>
            <p className="text-[11px] text-ink-faint mt-3">{a.disclaimer}</p>
          </section>
        )}

        {/* Early warning */}
        {a?.early_warning?.active && (
          <section className="rounded-2xl border border-accent-red/30 bg-accent-red/5 p-5">
            <h2 className="text-sm text-ink-primary">{a.early_warning.headline}</h2>
            <dl className="mt-3 space-y-2 text-[12px]">
              <Row label="Reason" value={a.early_warning.reason} />
              <Row label="Confidence" value={a.early_warning.confidence} />
              <Row
                label="Recommended next step"
                value={a.early_warning.recommended_next_step}
              />
            </dl>
            <p className="text-[11px] text-ink-faint mt-3 pt-2.5 border-t border-surface-border">
              {a.early_warning.notice}
            </p>
          </section>
        )}

        {/* Reviewer control */}
        {canReview && obs.review_status !== "completed" && (
          <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm text-ink-primary">Human verification</h2>
            <p className="text-[11px] text-ink-muted mt-1">
              Confirm, correct or reject the AI assessment. Your decision is what the
              dashboard, map and trends will report.
            </p>

            <div className="mt-4 flex gap-1.5 flex-wrap">
              {(
                [
                  ["accepted", "Accept"],
                  ["modified", "Modify status"],
                  ["rejected", "Reject"],
                  ["more_info_requested", "Request more info"],
                ] as Array<[ReviewDecision, string]>
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setDecision(value)}
                  aria-pressed={decision === value}
                  className={
                    decision === value
                      ? "rounded-md border border-accent-cyan/50 bg-accent-cyan/15 px-3 py-1.5 text-xs text-accent-cyan transition-colors"
                      : "rounded-md border border-surface-border bg-surface-bg px-3 py-1.5 text-xs text-ink-muted hover:text-ink-body transition-colors"
                  }
                >
                  {label}
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
                          ? "rounded-md border border-accent-cyan/50 bg-accent-cyan/10 p-0.5 transition-colors"
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
              rows={3}
              placeholder="Comment (optional) — what did you verify, and how?"
              className="mt-3 w-full rounded-md border border-surface-border bg-surface-bg px-3 py-2 text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-cyan focus:outline-none resize-y transition-colors"
            />

            <button
              type="button"
              onClick={submitReview}
              disabled={busy}
              className="mt-3 inline-flex items-center gap-2 rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-4 py-2 text-sm text-accent-cyan hover:bg-accent-cyan/25 disabled:opacity-50 transition-colors"
            >
              {busy ? (
                <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              ) : (
                <Check size={14} aria-hidden="true" />
              )}
              Record decision
            </button>
          </section>
        )}

        {/* What was observed */}
        <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
          <h2 className="text-sm text-ink-primary mb-4">What was observed</h2>

          {measurements.length > 0 && (
            <div className="mb-5">
              <div className="text-compact text-[10px] text-ink-faint mb-2">
                Measurements
              </div>
              <div className="grid gap-3 sm:grid-cols-4">
                {measurements.map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-lg border border-surface-border bg-surface-panel p-3"
                  >
                    <div className="text-[10px] text-ink-muted">
                      {MEASUREMENT_LABEL[k]?.label ?? k}
                    </div>
                    <div className="text-data-numeric text-lg text-ink-primary mt-0.5 nums-tabular">
                      {String(v)}
                      <span className="text-[11px] text-ink-faint ml-1">
                        {MEASUREMENT_LABEL[k]?.unit}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <PresenceSection
            title="Water appearance"
            entries={pickPresence(obs.appearance)}
            extra={
              <span className="text-[11px] text-ink-muted">
                Clarity: {obs.appearance.clarity.replace(/_/g, " ")}
                {obs.appearance.colour_note ? ` · ${obs.appearance.colour_note}` : ""}
              </span>
            }
          />
          <PresenceSection title="Biodiversity" entries={pickPresence(obs.biodiversity)} />
          <PresenceSection
            title="Environmental context"
            entries={pickPresence(obs.context)}
          />

          {obs.observer_note && (
            <div className="mt-4 pt-4 border-t border-surface-border">
              <div className="text-compact text-[10px] text-ink-faint">Observer note</div>
              <p className="text-[12px] text-ink-body mt-1">{obs.observer_note}</p>
            </div>
          )}
        </section>

        {/* Photos */}
        {obs.photos.length > 0 && (
          <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm text-ink-primary">Photo evidence</h2>
            <ul className="mt-3 grid gap-3 sm:grid-cols-2">
              {obs.photos.map((p) => (
                <li
                  key={p.id}
                  className="rounded-xl border border-surface-border bg-surface-panel p-3"
                >
                  {p.uri && (
                    <img
                      src={p.uri}
                      alt={p.caption ?? p.filename}
                      className="w-full h-36 object-cover rounded-lg mb-2"
                    />
                  )}
                  <div className="text-[11px] text-ink-body">
                    {p.caption ?? p.filename}
                  </div>
                  {p.ai_labels.length > 0 && (
                    <div className="mt-2">
                      <div className="text-compact text-[10px] text-ink-faint">
                        AI-assisted labels
                      </div>
                      <ul className="mt-1 space-y-1">
                        {p.ai_labels.map((l, i) => (
                          <li
                            key={`${l.label}-${i}`}
                            className="flex items-center justify-between text-[11px]"
                          >
                            <span className="text-ink-body">{l.label}</span>
                            <span className="text-ink-muted">{l.confidence}</span>
                          </li>
                        ))}
                      </ul>
                      <p className="text-[10px] text-accent-amber mt-2">
                        {p.ai_disclaimer}
                      </p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Local components
// =============================================================================

function BackLink() {
  return (
    <Link
      to="/aquahealth/observations"
      className="inline-flex items-center gap-1.5 text-[11px] text-ink-muted hover:text-accent-cyan mb-4 transition-colors"
    >
      <ArrowLeft size={12} aria-hidden="true" />
      All observations
    </Link>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-ink-muted shrink-0 w-40">{label}</dt>
      <dd className="text-ink-body">{value}</dd>
    </div>
  );
}

/**
 * Only the fields the observer actually answered informatively.
 *
 * Takes `object` rather than a union of the three section interfaces: each has
 * a different key set, and widening to `Record<string, unknown>` would require
 * an index signature the models deliberately do not declare.
 */
function pickPresence(section: object): Array<[string, Presence]> {
  const out: Array<[string, Presence]> = [];
  for (const [k, v] of Object.entries(section)) {
    if (
      v === "observed" ||
      v === "not_observed" ||
      v === "unknown" ||
      v === "not_available"
    ) {
      out.push([k, v]);
    }
  }
  return out;
}

function PresenceSection({
  title,
  entries,
  extra,
}: {
  title: string;
  entries: Array<[string, Presence]>;
  extra?: ReactNode;
}) {
  const answered = entries.filter(([, v]) => v === "observed" || v === "not_observed");
  const skipped = entries.length - answered.length;

  return (
    <div className="mb-4 last:mb-0">
      <div className="flex items-center justify-between">
        <div className="text-compact text-[10px] text-ink-faint">{title}</div>
        {skipped > 0 && (
          <span className="text-[10px] text-ink-faint">{skipped} not checked</span>
        )}
      </div>
      {extra && <div className="mt-1">{extra}</div>}
      {answered.length === 0 ? (
        <p className="text-[11px] text-ink-faint mt-1.5">
          No fields in this section were answered.
        </p>
      ) : (
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {answered.map(([k, v]) => (
            <li
              key={k}
              className="flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-panel px-2 py-1"
            >
              <span className="text-[11px] text-ink-body">{k.replace(/_/g, " ")}</span>
              <PresencePill presence={v} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
