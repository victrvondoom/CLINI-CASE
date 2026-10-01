/**
 * /policies/:policyId/diff — Policy Diff Viewer.
 *
 * When a payer publishes a new policy version, ClinCase shows what criteria
 * changed and which in-flight cases are now affected. Operational moat —
 * no other PA tool does this.
 */
import clsx from "clsx";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, GitCompare, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { POLICIES, POLICY_DIFFS } from "../lib/syntheticPolicies";

export default function PolicyDiff() {
  const { policyId } = useParams<{ policyId: string }>();
  const [reevaluating, setReevaluating] = useState(false);
  const [reevaluated, setReevaluated] = useState(false);
  const policy = useMemo(
    () => POLICIES.find(
      (p) => p.policy_id === policyId
        || p.policy_id.toLowerCase() === (policyId || "").toLowerCase(),
    ),
    [policyId],
  );
  const diff = useMemo(() => {
    if (!policyId) return undefined;
    if (POLICY_DIFFS[policyId]) return POLICY_DIFFS[policyId];
    // case-insensitive fallback so /policies/ONCG-... also resolves
    const key = Object.keys(POLICY_DIFFS).find(
      (k) => k.toLowerCase() === policyId.toLowerCase(),
    );
    return key ? POLICY_DIFFS[key] : undefined;
  }, [policyId]);

  if (!policy) {
    return (
      <div className="px-6 py-12 text-center text-ink-muted">
        <p className="text-sm">Policy <span className="text-mono-tech">{policyId}</span> not found.</p>
        <Link to="/policies" className="text-accent-brand hover:underline text-sm mt-2 inline-block">
          ← Back to Policy Library
        </Link>
      </div>
    );
  }

  // No diff in the curated map → render a "this version is current; no
  // historical diffs recorded yet" panel with the policy's metadata + a
  // related-policies rail and a sample-of-current-criteria preview so the
  // page feels like a real artifact, not a placeholder.
  if (!diff) {
    const related = POLICIES
      .filter((p) => p.policy_id !== policy.policy_id && (
        p.payer_id === policy.payer_id ||
        p.treatment_keywords.some((t) => policy.treatment_keywords.includes(t))
      ))
      .slice(0, 4);
    return (
      <div className="px-6 py-6">
        <Link to="/policies" className="text-xs text-mono-tech text-accent-brand hover:underline inline-flex items-center gap-1 mb-3">
          <ArrowLeft size={11} /> Back to Policy Library
        </Link>

        {/* Header */}
        <div className="bg-surface-raised border border-surface-border rounded-2xl p-6 mb-4">
          <div className="text-[11px] text-compact text-accent-brand mb-2 flex items-center gap-2">
            <GitCompare size={12} /> Policy Diff Viewer
            <span className="text-ink-faint">·</span>
            <span className="text-ink-muted">No prior versions tracked</span>
          </div>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight">{policy.title}</h1>
          <div className="text-sm text-ink-muted mt-2 flex items-center gap-2 flex-wrap">
            <span className="text-ink-body font-medium">{policy.payer_id.toUpperCase()}</span>
            <span className="text-ink-faint">·</span>
            <span className="text-mono-tech text-xs text-accent-cyan">POLICY {policy.policy_id}</span>
            <span className="text-ink-faint">·</span>
            <span className="text-mono-tech text-xs">v{policy.version}</span>
            {policy.last_updated_iso && (
              <>
                <span className="text-ink-faint">·</span>
                <span className="text-xs">last updated {new Date(policy.last_updated_iso).toLocaleDateString()}</span>
              </>
            )}
          </div>
        </div>

        {/* Status banner */}
        <div className="border border-accent-amber/30 bg-accent-amber/5 rounded-xl px-5 py-4 mb-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-accent-amber shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-ink-primary text-sm mb-1">This is the current published version.</div>
            <p className="text-sm text-ink-body leading-relaxed">
              No prior versions have been ingested for this policy yet. As soon as{" "}
              <span className="text-accent-brand font-medium">{policy.payer_id.toUpperCase()}</span> publishes the next
              revision, ClinCase's policy crawler picks it up, surfaces every changed clause here, flags in-flight cases
              affected by the change, and offers "Re-evaluate all".
            </p>
          </div>
        </div>

        {/* Stat rail */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StatTile label="Sections" value={String(policy.section_count)} caption="indexed for retrieval" />
          <StatTile label="Words" value={policy.word_count.toLocaleString()} caption="text-layer chunks" />
          <StatTile label="Version" value={`v${policy.version}`} caption={policy.last_updated_iso ? new Date(policy.last_updated_iso).toLocaleDateString() : "—"} />
          <StatTile label="Treatments" value={String(policy.treatment_keywords.length)} caption={policy.treatment_keywords.slice(0, 2).join(", ")} />
        </div>

        {/* What this policy covers */}
        <div className="bg-surface-raised border border-surface-border rounded-2xl p-5 mb-4">
          <h2 className="text-sm font-semibold text-ink-primary mb-3 flex items-center gap-2">
            <Sparkles size={14} className="text-accent-brand" />
            What this policy covers
          </h2>
          <div className="flex flex-wrap gap-2">
            {policy.treatment_keywords.map((t) => (
              <span key={t} className="text-xs text-mono-tech px-2 py-1 rounded-md bg-accent-brand/10 text-accent-brand border border-accent-brand/20">
                {t}
              </span>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div className="border border-surface-border rounded-lg p-3 bg-surface-bg">
              <div className="text-[10px] text-compact text-ink-muted mb-1">Crawler status</div>
              <div className="text-ink-body flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-green" />
                Watching {policy.payer_id.toUpperCase()} oncology policy URL · checked hourly
              </div>
            </div>
            <div className="border border-surface-border rounded-lg p-3 bg-surface-bg">
              <div className="text-[10px] text-compact text-ink-muted mb-1">Indexing</div>
              <div className="text-ink-body flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-cyan" />
                pgvector · {policy.section_count} chunks · embedded with Titan v2
              </div>
            </div>
          </div>
        </div>

        {/* Related policies */}
        {related.length > 0 && (
          <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
            <h2 className="text-sm font-semibold text-ink-primary mb-3 flex items-center gap-2">
              <GitCompare size={14} className="text-accent-brand" />
              Related policies
              <span className="text-[10px] text-mono-tech text-ink-muted">same payer or shared treatment</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {related.map((p) => (
                <Link
                  key={p.policy_id}
                  to={`/policies/${p.policy_id}/diff`}
                  className="border border-surface-border rounded-lg p-3 bg-surface-bg hover:border-accent-brand/40 hover:bg-surface-raised-hi transition-colors flex items-center gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-primary truncate">{p.title}</div>
                    <div className="text-[11px] text-mono-tech text-ink-muted truncate">
                      {p.payer_id.toUpperCase()} · {p.policy_id} · v{p.version}
                    </div>
                  </div>
                  <ArrowRight size={13} className="text-ink-faint shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const verdictChanges = diff.affected_in_flight_cases.filter(
    (c) => c.old_verdict !== c.new_verdict,
  );

  return (
    <div className="px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <Link
          to="/policies"
          className="text-sm text-ink-muted hover:text-ink-primary flex items-center gap-1 transition-colors"
        >
          <ArrowLeft size={14} />
          Policy Library
        </Link>
      </div>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-[10px] text-compact text-accent-brand mb-2">
          <GitCompare size={12} />
          POLICY DIFF VIEWER
          <span className="text-ink-faint">·</span>
          <span className="text-ink-muted">novelty</span>
        </div>
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight">
          {policy.title}
        </h1>
        <div className="flex items-center gap-3 mt-2 text-sm text-ink-muted flex-wrap">
          <span className="text-mono-tech">
            {policy.payer_id.toUpperCase()} · {policy.policy_id}
          </span>
          <span className="text-ink-faint">·</span>
          <span className="flex items-center gap-1.5">
            <span className="text-mono-tech px-1.5 py-0.5 rounded bg-surface-panel text-ink-body">
              {diff.from_version}
            </span>
            <ArrowRight size={12} />
            <span className="text-mono-tech px-1.5 py-0.5 rounded bg-accent-brand/15 text-accent-brand">
              {diff.to_version}
            </span>
          </span>
          <span className="text-ink-faint">·</span>
          <span>14 days ago</span>
        </div>
      </div>

      {/* Impact callout */}
      <div className="bg-accent-amber/5 border border-accent-amber/30 rounded-xl px-4 py-3 mb-5 flex items-start gap-3">
        <AlertCircle size={18} className="text-accent-amber shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="text-sm font-medium text-ink-primary">
            <span className="text-mono-tech nums-tabular">{verdictChanges.length}</span> in-flight case{verdictChanges.length === 1 ? "" : "s"} affected by this change
          </div>
          <div className="text-xs text-ink-muted mt-0.5">
            ClinCase auto-re-evaluates open cases when a payer publishes a new policy version.
            Resubmission may be required for cases now flagged REFER.
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            if (reevaluating || reevaluated) return;
            setReevaluating(true);
            // Local simulation: ~1.4s of "running" animation, then a stable
            // success state. Production wires this to a real backend job that
            // re-runs the affected agents against the new policy version.
            setTimeout(() => {
              setReevaluating(false);
              setReevaluated(true);
            }, 1400);
          }}
          disabled={reevaluating}
          className={clsx(
            "text-xs font-medium px-3 py-1.5 rounded-md flex items-center gap-1.5 shrink-0 transition-opacity disabled:opacity-60",
            reevaluated
              ? "bg-accent-green text-ink-invert"
              : "bg-accent-amber text-ink-invert hover:opacity-90",
          )}
        >
          {reevaluating ? <Loader2 size={11} className="animate-spin" />
            : reevaluated ? <CheckCircle2 size={11} />
            : <RefreshCw size={11} />}
          {reevaluating ? "Re-evaluating…"
            : reevaluated ? `Re-evaluated · ${verdictChanges.length} cases re-scored`
            : "Re-evaluate all"}
        </button>
      </div>

      {/* Side-by-side diff */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <DiffColumn
          version={diff.from_version}
          label="Previous"
          tone="muted"
          segments={diff.segments_v_old}
        />
        <DiffColumn
          version={diff.to_version}
          label="Current"
          tone="active"
          segments={diff.segments_v_new}
        />
      </section>

      {/* Summary changes */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-5 mb-6">
        <h3 className="text-sm font-semibold text-ink-primary mb-3">Summary of changes</h3>
        <ul className="space-y-1.5">
          {diff.summary_changes.map((c, i) => (
            <li key={i} className="text-sm text-ink-body flex items-start gap-2">
              <span className="text-accent-brand shrink-0 mt-1">•</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Affected cases table */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink-primary">
            In-flight cases re-evaluated under {diff.to_version}
          </h3>
          <span className="text-[11px] text-mono-tech text-ink-muted">
            {diff.affected_in_flight_cases.length} cases
          </span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-surface-panel text-[10px] text-compact text-ink-muted">
            <tr>
              <th className="text-left px-4 py-2.5">Case</th>
              <th className="text-left px-4 py-2.5">Patient</th>
              <th className="text-left px-4 py-2.5">Treatment</th>
              <th className="text-left px-4 py-2.5 w-32">Old verdict</th>
              <th className="text-left px-4 py-2.5 w-8"></th>
              <th className="text-left px-4 py-2.5 w-32">New verdict</th>
              <th className="text-left px-4 py-2.5">Reason</th>
              <th className="px-4 py-2.5 w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {diff.affected_in_flight_cases.map((c) => {
              const changed = c.old_verdict !== c.new_verdict;
              return (
                <tr
                  key={c.case_id}
                  className={clsx("hover:bg-surface-raised-hi transition-colors", changed && "bg-accent-amber/[0.03]")}
                >
                  <td className="px-4 py-2.5 text-mono-tech text-xs text-ink-muted">
                    {c.case_id}
                  </td>
                  <td className="px-4 py-2.5 text-mono-tech text-xs text-ink-body">
                    {c.patient}
                  </td>
                  <td className="px-4 py-2.5 text-ink-primary">
                    {c.treatment}
                  </td>
                  <td className="px-4 py-2.5">
                    <VerdictText v={c.old_verdict} faded />
                  </td>
                  <td className="px-4 py-2.5 text-ink-faint">
                    <ArrowRight size={12} />
                  </td>
                  <td className="px-4 py-2.5">
                    <VerdictText v={c.new_verdict} faded={!changed} />
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-muted">
                    {c.reason}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/cases/${c.case_id}`}
                      className="inline-flex text-ink-faint hover:text-accent-brand transition-colors"
                    >
                      <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

// =============================================================================
// Sub-components
// =============================================================================

function DiffColumn({
  version,
  label,
  tone,
  segments,
}: {
  version: string;
  label: string;
  tone: "muted" | "active";
  segments: { type: "unchanged" | "removed" | "added"; text: string }[];
}) {
  return (
    <div className={clsx(
      "border rounded-2xl overflow-hidden",
      tone === "active" ? "border-accent-brand/30" : "border-surface-border",
    )}>
      <div
        className={clsx(
          "px-5 py-2.5 border-b text-xs font-medium flex items-center justify-between",
          tone === "active"
            ? "border-accent-brand/30 bg-accent-brand/5 text-accent-brand"
            : "border-surface-border bg-surface-panel text-ink-muted",
        )}
      >
        <span>{label}</span>
        <span className="text-mono-tech">{version}</span>
      </div>
      <div className="p-5 text-sm leading-relaxed text-mono-tech whitespace-pre-wrap">
        {segments.map((seg, i) => (
          <span
            key={i}
            className={clsx(
              seg.type === "removed" && "bg-accent-red/10 text-accent-red line-through px-0.5 rounded",
              seg.type === "added"   && "bg-accent-green/10 text-accent-green underline decoration-accent-green/40 px-0.5 rounded",
              seg.type === "unchanged" && "text-ink-body",
            )}
          >
            {seg.text}
          </span>
        ))}
      </div>
    </div>
  );
}

function VerdictText({ v, faded }: { v: "APPROVE" | "DENY" | "REFER"; faded?: boolean }) {
  const tint =
    v === "APPROVE" ? "text-accent-green" :
    v === "DENY"    ? "text-accent-red"   :
                      "text-accent-amber";
  return (
    <span className={clsx("text-xs text-mono-tech font-semibold", tint, faded && "opacity-60")}>
      {v}
    </span>
  );
}

function StatTile({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-xl p-4">
      <div className="text-[10px] text-compact text-ink-muted">{label}</div>
      <div className="text-2xl font-semibold text-ink-primary tabular-nums mt-1">{value}</div>
      <div className="text-[11px] text-ink-faint truncate mt-0.5" title={caption}>{caption}</div>
    </div>
  );
}
