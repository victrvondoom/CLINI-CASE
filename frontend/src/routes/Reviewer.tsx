/**
 * /reviewer — REFER-status cases routed to human reviewers.
 * Override-and-learn: reviewer overrides become training feedback.
 */
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  MessageSquare,
  Pause,
  UserCheck,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PayerCell } from "../components/PayerCell";
import { api } from "../lib/api";
import type { CaseListItem } from "../lib/api";
import type { ReviewQueueItem, ReviewQueueReport } from "../lib/types";
import { useLive } from "../lib/useLive";

type Priority = "high" | "medium" | "low";
type ReviewItem = ReviewQueueItem & { id: string };

const PRIORITY_TINT: Record<Priority, string> = {
  high:   "bg-accent-red/15    text-accent-red",
  medium: "bg-accent-amber/15  text-accent-amber",
  low:    "bg-surface-border   text-ink-muted",
};

function fmtAgo(min: number): string {
  if (min < 60) return `${min}m ago`;
  if (min < 48 * 60) return `${Math.floor(min / 60)}h ${min % 60}m ago`;
  const d = Math.floor(min / 1440);
  return `${d}d ${Math.floor((min % 1440) / 60)}h ago`;
}

type ActionResult = {
  case_id: string;
  action: string;
  new_status: string;
  ts: number;
};

export default function Reviewer() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [recent, setRecent] = useState<ActionResult[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const live = useLive<ReviewQueueReport>(() => api.getReviewQueue(50), [], 30_000);
  const queue: ReviewItem[] = (live.data?.items ?? []).map((i) => ({ ...i, id: i.case_id }));
  const selected = queue.find((q) => q.id === selectedId) ?? null;

  const counts = live.data?.counts ?? { high: 0, medium: 0, low: 0 };
  const avgWait = queue.length ? Math.round(queue.reduce((s, q) => s + q.age_minutes, 0) / queue.length) : null;

  async function submitAction(
    item: ReviewItem,
    action: "override_to_approve" | "override_to_deny" | "escalate" | "add_note",
    note?: string,
  ) {
    setSubmitting(action);
    setActionError(null);
    try {
      // A review is only recorded if the backend confirms it — a failure is shown, never simulated as success.
      const r = await api.submitReview(item.case_id, { action, note });
      setRecent((prev) => [{ ...r, ts: Date.now() } as ActionResult, ...prev].slice(0, 5));
      if (action === "override_to_approve" || action === "override_to_deny") setSelectedId(null);
      live.reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="px-6 py-6">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
          <UserCheck size={22} className="text-accent-brand" />
          Reviewer queue
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          <span className="text-mono-tech text-ink-body" data-testid="queue-total">{queue.length}</span> cases awaiting human review
          <span className="mx-2 text-ink-faint">·</span>
          <span className="text-accent-red font-medium">{counts.high} high</span>
          <span className="mx-2 text-ink-faint">·</span>
          <span className="text-accent-amber font-medium">{counts.medium} medium</span>
          <span className="mx-2 text-ink-faint">·</span>
          <span className="text-ink-muted">{counts.low} low</span>
        </p>
      </header>

      {/* HITL gate: cases paused live by the LangGraph review_gate node */}
      <HITLPausedPanel />

      <div className="grid lg:grid-cols-[1fr_400px] gap-5">
        {/* Queue list */}
        <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink-primary">Queue</h3>
            <span className="text-[11px] text-mono-tech text-ink-muted" data-testid="avg-wait">{avgWait == null ? "avg wait: —" : `avg wait: ${fmtAgo(avgWait).replace(" ago", "")}`}</span>
          </div>
          <div className="divide-y divide-surface-border">
            {live.error && (
              <div role="alert" data-testid="queue-error" className="p-4 text-sm text-accent-red">
                Could not load the reviewer queue: {live.error}{" "}
                <button type="button" className="underline" onClick={live.reload}>Retry</button>
              </div>
            )}
            {!live.data && live.loading && (
              <div className="p-10 text-center text-ink-muted text-sm" role="status">
                <Loader2 size={20} className="mx-auto mb-2 animate-spin" />
                Loading reviewer queue…
              </div>
            )}
            {live.data && queue.length === 0 && (
              <div data-testid="queue-empty" className="p-10 text-center text-ink-muted text-sm">
                <CheckCircle2 size={28} className="mx-auto mb-2 text-accent-green" />
                Queue cleared. No REFER cases are waiting for review.
              </div>
            )}
            {queue.map((q) => (
              <button
                key={q.id}
                type="button"
                data-testid={`queue-item-${q.id}`}
                onClick={() => setSelectedId(q.id)}
                className={clsx(
                  "w-full text-left px-5 py-3 transition-colors flex items-start gap-3 hover:bg-surface-raised-hi",
                  selected?.id === q.id && "bg-accent-brand/5",
                )}
              >
                <span className={clsx("text-[10px] text-mono-tech uppercase tracking-wide px-2 py-0.5 rounded shrink-0 mt-0.5", PRIORITY_TINT[q.priority])}>
                  {q.priority}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-mono-tech text-xs text-ink-body">{q.patient}</span>
                    <span className="text-ink-faint">·</span>
                    <span className="text-sm font-medium text-ink-primary truncate">{q.treatment}</span>
                  </div>
                  <p className="text-xs text-ink-muted mt-0.5 line-clamp-1">{q.reason}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <PayerCell payer_id={q.payer} showLabel={false} />
                  <span className="text-[11px] text-mono-tech text-ink-faint w-14 text-right">{fmtAgo(q.age_minutes)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Side column: review panel + confirmations */}
        <div className="lg:sticky lg:top-20 lg:self-start">
        <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
          {!selected ? (
            <div className="p-10 text-center text-ink-muted text-sm">
              <ClipboardCheck size={36} className="mx-auto mb-3 text-ink-faint" />
              Select a case from the queue to begin review.
            </div>
          ) : (
            <>
              <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink-primary">Review · {selected.patient}</h3>
                <span className={clsx("text-[10px] text-mono-tech uppercase tracking-wide px-2 py-0.5 rounded", PRIORITY_TINT[selected.priority])}>
                  {selected.priority}
                </span>
              </div>
              <div className="px-5 py-4 space-y-3">
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Treatment</div>
                  <div className="text-sm font-medium text-ink-primary">{selected.treatment}</div>
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Payer</div>
                  <PayerCell payer_id={selected.payer} />
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Necessity Reasoner verdict</div>
                  <div className="text-sm text-accent-amber font-semibold">REFER</div>
                  <div className="text-xs text-ink-muted">confidence {selected.confidence == null ? "—" : `${(selected.confidence * 100).toFixed(0)}%`}</div>
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Reason for refer</div>
                  <p className="text-sm text-ink-body leading-relaxed">{selected.reason}</p>
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Missing evidence</div>
                  <p className="text-sm text-ink-body leading-relaxed">{selected.missing_evidence ?? "None recorded by the Necessity Reasoner."}</p>
                </div>
              </div>
              <div className="border-t border-surface-border px-5 py-4 space-y-2">
                <div className="text-[10px] text-compact text-ink-muted mb-1">Reviewer actions</div>
                <button
                  type="button"
                  disabled={submitting !== null}
                  onClick={() => submitAction(selected, "override_to_approve")}
                  className="w-full text-sm font-medium px-3 py-2 rounded-md bg-accent-green text-ink-invert hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  {submitting === "override_to_approve" ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Override → APPROVE
                </button>
                <button
                  type="button"
                  disabled={submitting !== null}
                  onClick={() => submitAction(selected, "override_to_deny")}
                  className="w-full text-sm font-medium px-3 py-2 rounded-md bg-accent-red text-ink-invert hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  {submitting === "override_to_deny" ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                  Override → DENY
                </button>
                <button
                  type="button"
                  disabled={submitting !== null}
                  onClick={() => submitAction(selected, "escalate")}
                  className="w-full text-sm font-medium px-3 py-2 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  <AlertTriangle size={14} />
                  Escalate to oncology committee
                </button>
                <button
                  type="button"
                  disabled={submitting !== null}
                  onClick={() => submitAction(selected, "add_note", "Pending additional documentation request")}
                  className="w-full text-sm font-medium px-3 py-2 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                >
                  <MessageSquare size={14} />
                  Add note · request more info
                </button>
                <a
                  href={`/cases/${selected.case_id}`}
                  className="w-full text-sm font-medium px-3 py-2 rounded-md text-accent-brand hover:underline transition-colors flex items-center justify-center gap-1.5 mt-3"
                >
                  Open full case detail
                  <ArrowRight size={12} />
                </a>
                {actionError && (
                  <div className="text-[11px] text-accent-red bg-accent-red/10 rounded px-2 py-1.5 mt-2">
                    {actionError}
                  </div>
                )}
              </div>
              <div className="px-5 py-2.5 border-t border-surface-border bg-surface-panel/40 text-[11px] text-ink-muted text-mono-tech flex items-center gap-1">
                <ArrowLeft size={11} />
                Reviewer overrides feed back into the system for retraining
              </div>

            </>
          )}
        </div>

        {/* confirmations stay visible after a case leaves the queue */}
        {recent.length > 0 && (
          <div data-testid="recent-actions" className="mt-3 border border-accent-green/30 rounded-2xl px-5 py-3 bg-accent-green/5">
            <div className="text-[10px] text-compact text-accent-green mb-1.5">
              Recent actions ({recent.length})
            </div>
            <div className="space-y-1">
              {recent.map((r, i) => (
                <div key={i} className="text-[11px] text-ink-body text-mono-tech flex items-center gap-2">
                  <CheckCircle2 size={10} className="text-accent-green" />
                  <span className="text-ink-muted">{r.case_id}</span>
                  <span>·</span>
                  <span className="text-accent-green">{r.action}</span>
                  <span>·</span>
                  <span>{r.new_status}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// HITL Paused Panel — live cases routed here by the LangGraph review_gate node
// =============================================================================

function HITLPausedPanel() {
  const [paused, setPaused] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [resumingId, setResumingId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const r = await api.listCases({ status: "awaiting_review", limit: 50 });
      setPaused(r.cases);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load paused cases");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleResume(caseId: string, verdict: "APPROVE" | "DENY" | "REFER") {
    setResumingId(caseId);
    setError(null);
    try {
      const resumed = await api.resumeCase(caseId, { verdict, reviewer_note: note, continuation_mode: "inline" });
      if (resumed.continuation?.error) throw new Error(resumed.continuation.error);
      setNote("");
      // Optimistic remove
      setPaused((prev) => prev.filter((c) => c.case_id !== caseId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setResumingId(null);
    }
  }

  if (loading) {
    return (
      <section className="mb-5 border-2 border-accent-amber/30 rounded-2xl bg-accent-amber/5 px-5 py-4 text-sm text-ink-muted">
        <Loader2 size={14} className="inline-block animate-spin mr-2" />
        Loading HITL-paused cases...
      </section>
    );
  }

  if (paused.length === 0) {
    return (
      <section className="mb-5 border border-accent-green/20 rounded-2xl bg-accent-green/5 px-5 py-4 text-sm text-ink-muted flex items-center gap-2">
        <CheckCircle2 size={14} className="text-accent-green" />
        No cases currently awaiting clinician sign-off. Every AI DENY recommendation requires review.
      </section>
    );
  }

  return (
    <section className="mb-5 border-2 border-accent-amber/40 rounded-2xl overflow-hidden">
      <div className="bg-accent-amber/15 px-5 py-3 border-b border-accent-amber/30 flex items-center gap-2">
        <Pause size={16} className="text-accent-amber" />
        <h2 className="text-sm font-semibold text-ink-primary">
          {paused.length} case{paused.length === 1 ? "" : "s"} paused at <code className="text-mono-tech text-[12px]">review_gate</code> — clinician sign-off required
        </h2>
        <span className="ml-auto text-[10px] text-compact text-accent-amber">
          CMS-0057-F § IV.C · CA SB 1120
        </span>
      </div>
      <div className="divide-y divide-surface-border">
        {paused.map((c) => (
          <div key={c.case_id} className="px-5 py-4 bg-surface-raised">
            <div className="flex items-start gap-4 mb-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-mono-tech text-xs text-ink-body">{c.patient_initials}</span>
                  <span className="text-ink-faint">·</span>
                  <span className="text-sm font-medium text-ink-primary">{c.treatment}</span>
                  <span className="text-ink-faint">·</span>
                  <code className="text-mono-tech text-[11px] text-ink-muted">{c.case_id}</code>
                </div>
                <p className="text-xs text-ink-muted leading-snug">
                  AI DENY recommendations and uncertain assessments require clinician sign-off.
                  Review the evidence and draft letters before recording your verdict.
                </p>
                <Link to={`/cases/${c.case_id}`} className="inline-block mt-1 text-xs underline text-accent-brand">Review evidence and draft letters</Link>
              </div>
              <PayerCell payer_id={(c.payer_id ?? "aetna") as "aetna" | "uhc" | "bcbs" | "anthem"} showLabel={false} />
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Reviewer note (becomes part of audit trail)"
                className="flex-1 min-w-[240px] text-xs px-3 py-1.5 rounded-md border border-surface-border bg-surface-panel/60 text-ink-body placeholder:text-ink-faint focus:outline-none focus:border-accent-brand"
              />
              <button
                type="button"
                disabled={resumingId === c.case_id}
                onClick={() => handleResume(c.case_id, "APPROVE")}
                className="text-xs font-medium px-3 py-1.5 rounded-md bg-accent-green/15 text-accent-green hover:bg-accent-green/25 disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                <CheckCircle2 size={12} />
                Resume · APPROVE
              </button>
              <button
                type="button"
                disabled={resumingId === c.case_id}
                onClick={() => handleResume(c.case_id, "DENY")}
                className="text-xs font-medium px-3 py-1.5 rounded-md bg-accent-red/15 text-accent-red hover:bg-accent-red/25 disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                <XCircle size={12} />
                Resume · DENY
              </button>
              <button
                type="button"
                disabled={resumingId === c.case_id}
                onClick={() => handleResume(c.case_id, "REFER")}
                className="text-xs font-medium px-3 py-1.5 rounded-md bg-accent-amber/15 text-accent-amber hover:bg-accent-amber/25 disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                <AlertTriangle size={12} />
                Refer
              </button>
              {resumingId === c.case_id && (
                <Loader2 size={14} className="animate-spin text-accent-brand" />
              )}
            </div>
          </div>
        ))}
      </div>
      {error && (
        <div className="px-5 py-2 bg-accent-red/10 text-accent-red text-xs border-t border-accent-red/30">
          {error}
        </div>
      )}
    </section>
  );
}
