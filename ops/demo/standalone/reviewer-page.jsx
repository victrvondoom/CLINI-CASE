/* global window, React */
const { useState: useStateR } = React;

function ReviewerPage({ navigate }) {
  const { REFERS } = window.CLINCASE_REVIEWER;
  const [selectedId, setSelectedId] = useStateR(REFERS[0].id);
  const sel = REFERS.find((r) => r.id === selectedId) || REFERS[0];

  return (
    <div data-screen-label="reviewer" className="space-y-5">
      <header>
        <Eyebrow>Analytics · Reviewer</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          Reviewer queue
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          REFER cases that need a clinician's eyes. Each row is preloaded with the snapshot, the policy excerpt
          that triggered the referral, and a missing-evidence checklist — so reviewers act in seconds, not minutes.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Pill tone="amber">{REFERS.length} REFER</Pill>
          <span className="text-[11px] font-mono text-ink-muted">avg wait time 1h 39m</span>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[11px] font-mono text-ink-muted">
          sort:
          <button className="px-2 py-1 bg-surface-raised border border-surface-border rounded text-ink-body">oldest first</button>
          <button className="px-2 py-1 bg-surface-raised border border-surface-border rounded">payer</button>
          <button className="px-2 py-1 bg-surface-raised border border-surface-border rounded">drug</button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-4">
        {/* List */}
        <ul className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden divide-y divide-surface-border">
          {REFERS.map((r) => (
            <li key={r.id}>
              <button
                onClick={() => setSelectedId(r.id)}
                className={`w-full text-left px-4 py-3.5 transition-colors ${
                  r.id === selectedId
                    ? "bg-brand-50 border-l-[3px] border-l-accent-brand pl-[13px]"
                    : "hover:bg-surface-raised-hi border-l-[3px] border-l-transparent pl-[13px]"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-surface-raised-hi border border-surface-border flex items-center justify-center text-[11px] font-mono text-ink-body shrink-0">
                    {r.initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <PayerChip id={r.payer} small />
                      <span className="font-mono text-[10px] text-ink-muted truncate">{r.id}</span>
                    </div>
                    <div className="text-[13px] font-semibold text-ink-primary mt-0.5 truncate">{r.drug}</div>
                    <div className="text-[11.5px] text-ink-body mt-0.5 line-clamp-2 leading-snug">{r.reason}</div>
                    <div className="text-[10px] font-mono text-ink-faint mt-1.5">{r.received}</div>
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>

        {/* Detail */}
        <ReviewerDetail r={sel} />
      </div>
    </div>
  );
}

function ReviewerDetail({ r }) {
  return (
    <section className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-5 py-4 border-b border-surface-border flex items-start gap-4">
        <div className="w-12 h-12 rounded-full bg-surface-raised-hi border border-surface-border flex items-center justify-center text-[14px] font-mono text-ink-body shrink-0">
          {r.initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <PayerChip id={r.payer} small />
            <span className="font-mono text-[11px] text-ink-muted">{r.id}</span>
            <Pill tone="amber">REFER</Pill>
            <span className="font-mono text-[10px] text-ink-faint">received {r.received}</span>
          </div>
          <h2 className="text-[18px] font-semibold text-ink-primary mt-0.5">{r.drug}</h2>
        </div>
      </div>

      {/* Reason */}
      <div className="px-5 py-4 border-b border-surface-border bg-accent-amber/5">
        <div className="text-[10px] font-mono uppercase tracking-widest text-accent-amber">referred because</div>
        <p className="text-[13px] text-ink-primary mt-1 leading-relaxed">{r.reason}</p>
      </div>

      {/* Snapshot */}
      <div className="px-5 py-4 border-b border-surface-border">
        <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-1.5">clinical snapshot</div>
        <p className="text-[13px] text-ink-body leading-relaxed">{r.summary}</p>
      </div>

      {/* Missing evidence */}
      <div className="px-5 py-4 border-b border-surface-border">
        <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-2">evidence checklist</div>
        <ul className="space-y-1.5">
          {r.missing.map((m, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <div className={`w-4 h-4 rounded shrink-0 mt-0.5 flex items-center justify-center ${
                m.ok ? "bg-accent-green/15 text-accent-green" : "bg-accent-red/15 text-accent-red"
              }`}>
                {m.ok ? <I.Check className="w-3 h-3" /> : <I.X className="w-3 h-3" />}
              </div>
              <span className={`text-[12.5px] ${m.ok ? "text-ink-body" : "text-ink-primary font-medium"}`}>{m.label}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Hint */}
      {r.hint && (
        <div className="px-5 py-3 border-b border-surface-border bg-brand-50/50">
          <div className="flex items-start gap-2 text-[12px]">
            <I.Sparkles className="w-3.5 h-3.5 text-accent-brand shrink-0 mt-0.5" />
            <span className="text-ink-body"><span className="text-accent-brand font-medium">ClinCase hint:</span> {r.hint}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-auto px-5 py-3.5 flex items-center gap-2">
        <button className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2.5 text-[13px] font-medium bg-accent-green text-white rounded-md hover:opacity-90">
          <I.Check className="w-4 h-4" /> Approve
        </button>
        <button className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2.5 text-[13px] font-medium bg-accent-red text-white rounded-md hover:opacity-90">
          <I.X className="w-4 h-4" /> Deny
        </button>
        <button className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2.5 text-[13px] font-medium bg-surface-raised border border-surface-border-hi text-ink-body rounded-md hover:bg-surface-raised-hi">
          <I.ArrowLeft className="w-4 h-4" /> Send back
        </button>
      </div>
    </section>
  );
}

window.ReviewerPage = ReviewerPage;
