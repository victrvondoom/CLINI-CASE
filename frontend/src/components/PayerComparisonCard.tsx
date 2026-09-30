/** One payer column in the Multi-payer comparison: policy on file, real decision (if any), and the next real action. */
import clsx from "clsx";
import { CheckCircle2, Clock, ExternalLink, FileWarning, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { Link } from "react-router-dom";

import type { PayerColumn } from "../lib/types";

const VERDICT: Record<string, { ring: string; text: string; pill: string; Icon: typeof CheckCircle2 }> = {
  APPROVE: { ring: "border-accent-green/40", text: "text-accent-green", pill: "bg-accent-green/15", Icon: CheckCircle2 },
  DENY: { ring: "border-accent-red/40", text: "text-accent-red", pill: "bg-accent-red/15", Icon: XCircle },
  REFER: { ring: "border-accent-amber/40", text: "text-accent-amber", pill: "bg-accent-amber/15", Icon: ShieldCheck },
};

const STATE_TEXT: Record<PayerColumn["state"], string> = {
  decided: "Evaluated",
  in_progress: "Case created — not yet decided",
  not_started: "Not evaluated under this payer",
  no_policy: "No policy on file for this treatment",
};

interface Props {
  col: PayerColumn;
  recommended: boolean;
  creating: boolean;
  onCreate: () => void;
}

export function PayerComparisonCard({ col, recommended, creating, onCreate }: Props) {
  const v = col.decision ? VERDICT[col.decision.verdict] : null;
  return (
    <div
      data-testid={`payer-col-${col.payer_id}`}
      className={clsx(
        "border-2 rounded-2xl p-5 flex flex-col gap-3 relative bg-surface-raised",
        v ? v.ring : "border-surface-border",
        recommended && "ring-2 ring-accent-brand ring-offset-2 ring-offset-surface-bg",
      )}
    >
      {recommended && (
        <span className="absolute -top-2 left-4 text-[10px] text-compact px-2 py-0.5 rounded bg-accent-brand text-ink-invert">Recommended</span>
      )}
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-sm text-ink-primary">{col.name}</div>
          <div className="text-[10px] text-mono-tech text-ink-muted">{col.payer_id}{col.is_this_case ? " · this case" : ""}</div>
        </div>
        <span className="text-[9px] text-compact px-1.5 py-0.5 rounded bg-surface-panel text-ink-muted">{STATE_TEXT[col.state]}</span>
      </div>

      {col.decision && v ? (
        <div data-testid={`verdict-${col.payer_id}`}>
          <div className="flex items-center gap-2">
            <v.Icon size={20} className={v.text} strokeWidth={2.5} />
            <div>
              <div className={clsx("text-sm font-bold uppercase tracking-wider", v.text)}>{col.decision.verdict}</div>
              <div className="text-[10px] text-mono-tech text-ink-muted">{Math.round(col.decision.confidence * 100)}% confidence</div>
            </div>
          </div>
          {col.decision.rationale && <p className="text-xs text-ink-body mt-2 leading-snug">{col.decision.rationale}</p>}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          {col.state === "in_progress" ? <Loader2 size={14} className="animate-spin" /> : col.state === "no_policy" ? <FileWarning size={14} /> : <Clock size={14} />}
          {STATE_TEXT[col.state]}
        </div>
      )}

      <div className="text-[11px] text-ink-muted border-t border-surface-border pt-2 space-y-1">
        {col.policy ? (
          <div data-testid={`policy-${col.payer_id}`}>
            <span className="text-ink-faint">Policy on file: </span>
            <Link to={`/policies/${col.policy.policy_id}/diff`} className="text-accent-brand hover:underline text-mono-tech">{col.policy.policy_id}</Link>
            <span> · {col.policy.section_count} sections</span>
            {col.policy.has_recent_change && <span className="ml-1 text-accent-amber">· recent change</span>}
            {col.policy.source_url && (
              <a href={col.policy.source_url} target="_blank" rel="noreferrer" className="ml-1 inline-flex align-middle text-accent-cyan" aria-label="payer source"><ExternalLink size={10} /></a>
            )}
          </div>
        ) : (
          <div>No matching policy in the corpus.</div>
        )}
      </div>

      {col.case && !col.is_this_case && (
        <Link to={`/cases/${col.case.case_id}`} className="text-xs font-medium text-accent-brand hover:underline">Open {col.case.case_id} ({col.case.status}) →</Link>
      )}
      {col.can_create && (
        <button
          type="button"
          onClick={onCreate}
          disabled={creating}
          data-testid={`create-${col.payer_id}`}
          className="text-xs font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi disabled:opacity-50 flex items-center justify-center gap-1.5"
        >
          {creating && <Loader2 size={12} className="animate-spin" />}
          Create comparison case for {col.name}
        </button>
      )}
    </div>
  );
}
