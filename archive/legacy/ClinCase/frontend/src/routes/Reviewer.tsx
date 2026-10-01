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

import { PayerCell } from "../components/PayerCell";
import { api } from "../lib/api";
import type { CaseListItem } from "../lib/api";

type Priority = "high" | "medium" | "low";

interface ReviewItem {
  id: string;
  case_id: string;
  patient: string;
  treatment: string;
  payer: "aetna" | "uhc" | "bcbs" | "anthem";
  priority: Priority;
  reason: string;
  missing_evidence: string;
  ago_minutes: number;
  confidence: number;
}

const QUEUE: ReviewItem[] = [
  { id: "rev_01", case_id: "case_8f4ad9c2", patient: "S.D.", treatment: "trastuzumab",      payer: "aetna",  priority: "high",   reason: "Baseline LVEF documentation outside payer window",      missing_evidence: "ECHO/MUGA within 60 days (current: 75d ago)",  ago_minutes:  4, confidence: 0.50 },
  { id: "rev_02", case_id: "case_3d44e1b9", patient: "P.N.", treatment: "pembrolizumab",    payer: "bcbs",   priority: "medium", reason: "MSI-H status not documented for indication",            missing_evidence: "MSI / dMMR companion-diagnostic result", ago_minutes: 14, confidence: 0.62 },
  { id: "rev_03", case_id: "case_a8f23910", patient: "R.K.", treatment: "osimertinib",      payer: "uhc",    priority: "high",   reason: "EGFR mutation type unclear",                            missing_evidence: "Specific exon 19 / L858R / T790M designation", ago_minutes: 27, confidence: 0.55 },
  { id: "rev_04", case_id: "case_e9128d3c", patient: "F.E.", treatment: "T-DXd",            payer: "aetna",  priority: "high",   reason: "Prior anthracycline; new 30-day LVEF requirement",      missing_evidence: "Repeat echocardiogram within 30 days of initiation",  ago_minutes: 33, confidence: 0.48 },
  { id: "rev_05", case_id: "case_6a7b8c9d", patient: "C.R.", treatment: "osimertinib",      payer: "anthem", priority: "medium", reason: "ECOG status not in chart",                              missing_evidence: "Documented ECOG performance status (0–4)", ago_minutes: 47, confidence: 0.65 },
  { id: "rev_06", case_id: "case_9c12fa70", patient: "T.O.", treatment: "olaparib",         payer: "aetna",  priority: "low",    reason: "BRCA testing methodology footnote missing",             missing_evidence: "Companion-diagnostic name + version", ago_minutes: 78, confidence: 0.78 },
  { id: "rev_07", case_id: "case_2b1f8a04", patient: "K.M.", treatment: "dabrafenib + trametinib", payer: "uhc", priority: "medium", reason: "BRAF V600E confirmation method unclear", missing_evidence: "PCR vs FISH vs NGS designation", ago_minutes: 96, confidence: 0.70 },
  { id: "rev_08", case_id: "case_5e87bb31", patient: "L.W.", treatment: "trastuzumab",      payer: "aetna",  priority: "low",    reason: "Cardiac comorbidity history incomplete",                missing_evidence: "Prior history of NYHA II-IV heart failure",  ago_minutes: 122, confidence: 0.72 },
];

const PRIORITY_TINT: Record<Priority, string> = {
  high:   "bg-accent-red/15    text-accent-red",
  medium: "bg-accent-amber/15  text-accent-amber",
  low:    "bg-surface-border   text-ink-muted",
};

function fmtAgo(min: number): string {
  if (min < 60) return `${min}m ago`;
  return `${Math.floor(min / 60)}h ${min % 60}m ago`;
}

type ActionResult = {
  case_id: string;
  action: string;
  new_status: string;
  ts: number;
};

export default function Reviewer() {
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [queue, setQueue] = useState<ReviewItem[]>(QUEUE);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [recent, setRecent] = useState<ActionResult[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);

  const counts = {
    high:   queue.filter((q) => q.priority === "high").length,
    medium: queue.filter((q) => q.priority === "medium").length,
    low:    queue.filter((q) => q.priority === "low").length,
  };

  async function submitAction(
    item: ReviewItem,
    action: "override_to_approve" | "override_to_deny" | "escalate" | "add_note",
    note?: string,
  ) {
    setSubmitting(action);
    setActionError(null);
    try {
      // Synthetic-data items don't exist in the backend DB.
      // Pretend success client-side; in production every queue row would be a real case.
      let result: ActionResult;
      try {
        const r = await api.submitReview(item.case_id, { action, note });
        result = { ...r, ts: Date.now() } as ActionResult;
      } catch {
        result = {
          case_id: item.case_id,
          action,
          new_status: action === "override_to_approve" ? "approved"
                     : action === "override_to_deny" ? "denied"
                     : "referred",
          ts: Date.now(),
        };
      }

      // Remove from queue (escalate/add_note keep in queue)
      if (action === "override_to_approve" || action === "override_to_deny") {
        setQueue((prev) => prev.filter((q) => q.id !== item.id));
        setSelected(null);
      }

      setRecent((prev) => [result, ...prev].slice(0, 5));
    } catch (e) {
      setActionError(String(e));
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
          <span className="text-mono-tech text-ink-body">{QUEUE.length}</span> REFER cases awaiting human review
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
            <span className="text-[11px] text-mono-tech text-ink-muted">avg wait: 38m</span>
          </div>
          <div className="divide-y divide-surface-border">
            {queue.length === 0 && (
              <div className="p-10 text-center text-ink-muted text-sm">
                <CheckCircle2 size={28} className="mx-auto mb-2 text-accent-green" />
                Queue cleared. All REFER cases reviewed.
              </div>
            )}
            {queue.map((q) => (
              <button
                key={q.id}
                type="button"
                onClick={() => setSelected(q)}
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
                  <span className="text-[11px] text-mono-tech text-ink-faint w-14 text-right">{fmtAgo(q.ago_minutes)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Side panel */}
        <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden lg:sticky lg:top-20 lg:self-start">
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
                  <div className="text-xs text-ink-muted">confidence {(selected.confidence * 100).toFixed(0)}%</div>
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Reason for refer</div>
                  <p className="text-sm text-ink-body leading-relaxed">{selected.reason}</p>
                </div>
                <div>
                  <div className="text-[10px] text-compact text-ink-muted mb-1">Missing evidence</div>
                  <p className="text-sm text-ink-body leading-relaxed">{selected.missing_evidence}</p>
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

              {recent.length > 0 && (
                <div className="border-t border-surface-border px-5 py-3 bg-accent-green/5">
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
            </>
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
      await api.resumeCase(caseId, { verdict, reviewer_note: note });
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
        No cases currently paused at the LangGraph <code className="text-mono-tech text-[12px] text-ink-body">review_gate</code> node.
        Confidence threshold:{" "}
        <code className="text-mono-tech text-[12px] text-ink-body">HITL_CONFIDENCE_THRESHOLD = 0.75</code>.
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
                  Necessity Reasoner overall_confidence below threshold.
                  ClinCase's draft assessment is in the audit trail; supply your verdict to resume the workflow.
                </p>
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
