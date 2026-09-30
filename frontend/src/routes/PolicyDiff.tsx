/**
 * /policies/:policyId/diff — Policy detail & change view.
 *
 * Everything here is served by GET /api/v1/policy-catalog/{id}: the policy's real sections from the corpus the
 * Policy Retriever searches, the payer policy changes recorded in the change snapshot (matched by payer + drug),
 * and the caller's own OPEN cases that this policy governs. The change snapshot is a bundled demo dataset and is
 * labelled as such; if no change is recorded for a policy, the page says so instead of inventing one.
 */
import clsx from "clsx";
import { AlertCircle, ArrowLeft, ArrowRight, ExternalLink, GitCompare, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StatTile } from "../components/StatTile";
import { api } from "../lib/api";
import type { PolicyChange } from "../lib/types";
import { useLive } from "../lib/useLive";

const ACTION_STYLE: Record<PolicyChange["diff"][number]["action"], string> = {
  added: "border-accent-green/40 bg-accent-green/5",
  removed: "border-accent-red/40 bg-accent-red/5",
  modified: "border-accent-amber/40 bg-accent-amber/5",
};
const ACTION_GLYPH = { added: "+", removed: "−", modified: "~" } as const;

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

export default function PolicyDiff() {
  const { policyId = "" } = useParams<{ policyId: string }>();
  const { data: policy, error, loading, reload } = useLive(() => api.getPolicyDetail(policyId), [policyId]);
  const [openSection, setOpenSection] = useState<number | null>(null);

  if (error) {
    return (
      <div className="px-6 py-12 text-center text-ink-muted" data-testid="policy-error">
        <p className="text-sm">
          Could not load policy <span className="text-mono-tech">{policyId}</span>: {error}
        </p>
        <div className="mt-2 flex justify-center gap-3 text-sm">
          <button type="button" onClick={reload} className="text-accent-brand hover:underline">Retry</button>
          <Link to="/policies" className="text-accent-brand hover:underline">← Back to Policy Library</Link>
        </div>
      </div>
    );
  }
  if (!policy) {
    return (
      <div className="px-6 py-12 text-center text-ink-muted text-sm" role="status">
        {loading && <Loader2 size={18} className="mx-auto mb-2 animate-spin" />}Loading policy…
      </div>
    );
  }

  return (
    <div className="px-6 py-6 space-y-5" data-testid="policy-detail">
      <Link to="/policies" className="text-xs text-mono-tech text-accent-brand hover:underline inline-flex items-center gap-1">
        <ArrowLeft size={12} /> Policy Library
      </Link>

      <header>
        <div className="text-[10px] text-compact text-ink-muted">
          {policy.payer_id.toUpperCase()} · POLICY {policy.policy_id}
        </div>
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight mt-0.5">{policy.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {policy.treatment_keywords.map((k) => (
            <span key={k} className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-surface-panel text-ink-body">{k}</span>
          ))}
          {policy.source_url && (
            <a href={policy.source_url} target="_blank" rel="noreferrer" className="ml-2 text-[11px] text-accent-cyan hover:underline inline-flex items-center gap-1">
              payer source <ExternalLink size={10} />
            </a>
          )}
        </div>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile eyebrow="Sections" value={String(policy.section_count)} hint="indexed for retrieval" />
        <StatTile eyebrow="Words" value={policy.word_count.toLocaleString()} hint="policy text" />
        <StatTile eyebrow="Recorded changes" value={String(policy.diffs.length)} hint={`snapshot ${fmtDate(policy.snapshot.taken_at)}`} />
        <StatTile
          eyebrow="Your open cases"
          value={policy.open_cases_available ? String(policy.open_cases.length) : "—"}
          hint={policy.open_cases_available ? "governed by this policy" : "case database unavailable"}
        />
      </section>

      {/* Recorded changes */}
      <section aria-label="Recorded policy changes" className="space-y-3">
        <h2 className="text-sm font-semibold text-ink-primary flex items-center gap-2">
          <GitCompare size={15} className="text-accent-brand" /> Recorded changes
        </h2>
        {policy.diffs.length === 0 ? (
          <div data-testid="no-diffs" className="rounded-xl border border-surface-border bg-surface-raised px-4 py-3 text-sm text-ink-muted">
            No change is recorded for this policy in the payer-change snapshot ({fmtDate(policy.snapshot.taken_at)}, {policy.snapshot.version}).
            Current criteria are shown below.
          </div>
        ) : (
          policy.diffs.map((d) => (
            <article key={`${d.policy_id}-${d.changed_at}`} data-testid="diff-card" className="rounded-xl border border-surface-border bg-surface-raised p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs text-mono-tech text-ink-muted">
                <span className="px-1.5 py-0.5 rounded bg-surface-panel">{d.version_old}</span>
                <ArrowRight size={11} aria-hidden />
                <span className="px-1.5 py-0.5 rounded bg-accent-amber/15 text-accent-amber">{d.version_new}</span>
                <span>· {d.payer} {d.policy_id} · {fmtDate(d.changed_at)}</span>
              </div>
              <p className="text-sm text-ink-body mt-2">{d.summary}</p>
              <ul className="mt-3 space-y-2">
                {d.diff.map((c, i) => (
                  <li key={i} className={clsx("rounded-lg border px-3 py-2 text-xs", ACTION_STYLE[c.action])}>
                    <span className="text-mono-tech font-semibold mr-2">{ACTION_GLYPH[c.action]} {c.action}</span>
                    <span className="text-ink-muted">{c.section}</span>
                    <p className="mt-0.5 text-ink-body">{c.text}</p>
                  </li>
                ))}
              </ul>
            </article>
          ))
        )}
        <p className="text-[11px] text-ink-muted flex gap-1.5">
          <AlertCircle size={12} className="mt-0.5 shrink-0" aria-hidden />
          <span>{policy.snapshot.note}</span>
        </p>
      </section>

      {/* Open cases governed by this policy */}
      <section aria-label="Open cases governed by this policy" className="space-y-2">
        <h2 className="text-sm font-semibold text-ink-primary">Your open cases under this policy</h2>
        {!policy.open_cases_available ? (
          <p className="text-xs text-ink-muted">The case database is unavailable, so open cases could not be listed.</p>
        ) : policy.open_cases.length === 0 ? (
          <p data-testid="no-open-cases" className="text-xs text-ink-muted">
            No open cases for {policy.payer_id.toUpperCase()} match this policy's treatments.
          </p>
        ) : (
          <ul className="divide-y divide-surface-border rounded-xl border border-surface-border bg-surface-raised">
            {policy.open_cases.map((c) => (
              <li key={c.case_id} data-testid="open-case">
                <Link to={`/cases/${c.case_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-raised-hi text-sm">
                  <span className="text-mono-tech text-xs text-ink-body">{c.patient}</span>
                  <span className="font-medium text-ink-primary truncate">{c.treatment}</span>
                  <span className="ml-auto text-[10px] text-mono-tech uppercase text-ink-muted">{c.status.replace("_", " ")}</span>
                  <span className="text-[11px] text-ink-faint">{fmtDate(c.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Current criteria */}
      <section aria-label="Policy sections" className="space-y-2">
        <h2 className="text-sm font-semibold text-ink-primary">Current criteria</h2>
        {policy.sections.map((s, i) => (
          <div key={i} className="rounded-xl border border-surface-border bg-surface-raised">
            <button
              type="button"
              onClick={() => setOpenSection(openSection === i ? null : i)}
              aria-expanded={openSection === i}
              className="w-full text-left px-4 py-2.5 flex items-center justify-between text-sm text-ink-primary"
            >
              <span>{s.heading ?? `Section ${i + 1}`}</span>
              <span className="text-[11px] text-mono-tech text-ink-muted">
                {s.page_number != null ? `p.${s.page_number} · ` : ""}{s.word_count} words
              </span>
            </button>
            {openSection === i && <p className="px-4 pb-3 text-xs text-ink-body leading-relaxed whitespace-pre-line">{s.text}</p>}
          </div>
        ))}
      </section>

      {policy.related.length > 0 && (
        <section aria-label="Related policies">
          <h2 className="text-sm font-semibold text-ink-primary mb-2">Related policies</h2>
          <div className="flex flex-wrap gap-2">
            {policy.related.map((r) => (
              <Link key={r.policy_id} to={`/policies/${r.policy_id}/diff`} className="text-xs px-2.5 py-1 rounded-md border border-surface-border hover:border-accent-brand/60 text-ink-body">
                {r.payer_id.toUpperCase()} {r.policy_id} · {r.title.slice(0, 40)}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
