/* global window, React */
const { useState: useStateC } = React;

function CompliancePage({ navigate }) {
  const { CLAUSES, PHI_REDACTIONS_7D, SCORECARD } = window.CLINCASE_COMPLIANCE;
  const [selected, setSelected] = useStateC(null);

  const pct = SCORECARD.in_force / SCORECARD.total;

  return (
    <div data-screen-label="compliance" className="space-y-5">
      {/* Header */}
      <header>
        <Eyebrow>Analytics · Compliance</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          CMS-0057-F readiness
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          The auditor's first ask. Every clause in CMS-0057-F § IV mapped to a live ClinCase endpoint,
          attestation, or audit artifact. T-{SCORECARD.days_to_deadline} days to mandatory enforcement.
        </p>
      </header>

      {/* Top row — donut + side metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        {/* Donut card */}
        <section className="rounded-2xl bg-surface-raised border border-surface-border p-5 flex flex-col items-center text-center">
          <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">readiness</div>
          <ClauseDonut pct={pct} />
          <div className="mt-3 text-[20px] font-semibold text-ink-primary">
            {SCORECARD.in_force} of {SCORECARD.total}
          </div>
          <div className="text-[12.5px] text-ink-body mt-0.5">
            CMS-0057-F § IV clauses in force
          </div>
          <div className="mt-4 w-full grid grid-cols-2 gap-2 text-left">
            <ScoreCell label="last audit" value={SCORECARD.last_audit} />
            <ScoreCell label="next audit" value={SCORECARD.next_audit} />
          </div>
        </section>

        {/* Right side metrics */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricCard
            label="Audit Trail Completeness"
            value="100%"
            sub="412 / 412 agent invocations logged · last 24h"
            accent="green"
            icon={I.ShieldCheck}
          />
          <MetricCard
            label="PHI Redactions / 24h"
            value={SCORECARD.phi_redactions_24h.toLocaleString()}
            sub={`${SCORECARD.phi_redactions_7d_total.toLocaleString()} redactions across last 7 days`}
            accent="cyan"
            icon={I.Shield}
            chart={<PHISparkline values={PHI_REDACTIONS_7D} />}
          />
          <MetricCard
            label="Decision Timeliness"
            value="4m 18s"
            sub="median · zero late decisions in last 90 days"
            accent="brand"
            icon={I.Clock}
          />
          <MetricCard
            label="Citation Coverage"
            value="100%"
            sub="every decision returns structured citation_chain[]"
            accent="violet"
            icon={I.BookOpen}
          />
        </section>
      </div>

      {/* Two-column: clause grid + right rail */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        <section className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden">
          <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">§ IV clauses</div>
              <div className="text-[14px] font-semibold text-ink-primary">8 of 8 in force</div>
            </div>
            <div className="text-[11px] font-mono text-ink-muted">click to view evidence</div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-surface-border">
            {CLAUSES.map((c) => (
              <ClauseCard key={c.id} clause={c} selected={selected === c.id} onClick={() => setSelected(c.id === selected ? null : c.id)} />
            ))}
          </div>
        </section>

        <aside className="space-y-3">
          {/* Quarterly evidence pack */}
          <div className="rounded-2xl bg-gradient-to-br from-brand-50 to-surface-raised border border-accent-brand/20 p-5">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent-brand/10 border border-accent-brand/20 flex items-center justify-center text-accent-brand shrink-0">
                <I.FileText className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">CMS-0057-F § IV</div>
                <div className="text-[15px] font-semibold text-ink-primary mt-0.5">Quarterly Evidence Pack</div>
              </div>
            </div>
            <p className="mt-3 text-[12.5px] text-ink-body leading-relaxed">
              Auto-generated bundle: clause-by-clause attestations, audit trail hashes, agent prompt versions,
              policy diffs, and 90 days of redaction logs. Signed and chain-of-custody preserved.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="px-2.5 py-1.5 bg-surface-bg/60 rounded border border-surface-border">
                <span className="text-ink-muted">period</span><span className="text-ink-primary ml-1">Q1 2026</span>
              </div>
              <div className="px-2.5 py-1.5 bg-surface-bg/60 rounded border border-surface-border">
                <span className="text-ink-muted">size</span><span className="text-ink-primary ml-1">86.4 MB</span>
              </div>
            </div>
            <button className="mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[12px] font-medium bg-accent-brand text-white rounded-md hover:opacity-90">
              <I.Download className="w-3.5 h-3.5" /> Download evidence_pack.zip
            </button>
            <div className="mt-2 text-[10px] font-mono text-ink-muted text-center">
              SHA-256 verified · chain-of-custody preserved
            </div>
          </div>

          {/* Selected clause panel */}
          {selected && (() => {
            const c = CLAUSES.find((x) => x.id === selected);
            return (
              <div className="rounded-2xl bg-surface-raised border border-accent-brand/30 p-4">
                <div className="text-[10px] font-mono uppercase tracking-widest text-accent-brand">{c.id.toUpperCase()}</div>
                <div className="text-[14px] font-semibold text-ink-primary mt-0.5">{c.title}</div>
                <p className="mt-2 text-[12.5px] text-ink-body leading-relaxed">{c.blurb}</p>
                <div className="mt-3 px-3 py-2 bg-surface-bg rounded border border-surface-border">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">evidence</div>
                  <div className="text-[12px] font-mono text-ink-primary mt-0.5">{c.evidence}</div>
                </div>
              </div>
            );
          })()}
        </aside>
      </div>
    </div>
  );
}

// Donut SVG with animated arc
function ClauseDonut({ pct }) {
  const r = 64, cx = 80, cy = 80;
  const C = 2 * Math.PI * r;
  const dash = C * pct;
  return (
    <div className="relative my-2">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx={cx} cy={cy} r={r} stroke="var(--surface-raised-hi)" strokeWidth="14" fill="none" />
        <circle
          cx={cx} cy={cy} r={r}
          stroke="var(--accent-green)"
          strokeWidth="14"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${C - dash}`}
          strokeDashoffset={C * 0.25}
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: "stroke-dasharray 1.2s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-[36px] font-semibold tabular-nums text-ink-primary leading-none">
          {Math.round(pct * 100)}%
        </div>
        <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mt-1">in force</div>
      </div>
    </div>
  );
}

function ScoreCell({ label, value }) {
  return (
    <div className="px-2.5 py-1.5 bg-surface-bg rounded border border-surface-border">
      <div className="text-[9px] font-mono uppercase tracking-wider text-ink-muted">{label}</div>
      <div className="text-[12px] font-mono text-ink-primary">{value}</div>
    </div>
  );
}

function MetricCard({ label, value, sub, accent, icon: Ico, chart }) {
  const tone =
    accent === "green" ? "text-accent-green"
    : accent === "cyan" ? "text-accent-cyan"
    : accent === "violet" ? "text-accent-violet"
    : "text-accent-brand";
  const bg =
    accent === "green" ? "bg-accent-green/10 border-accent-green/20"
    : accent === "cyan" ? "bg-accent-cyan/10 border-accent-cyan/20"
    : accent === "violet" ? "bg-accent-violet/10 border-accent-violet/20"
    : "bg-accent-brand/10 border-accent-brand/20";
  return (
    <div className="rounded-xl bg-surface-raised border border-surface-border p-4 flex flex-col">
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border ${bg} ${tone}`}>
          <Ico className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">{label}</div>
          <div className={`text-[24px] font-semibold tabular-nums mt-0.5 ${tone}`}>{value}</div>
        </div>
        {chart && <div className="shrink-0">{chart}</div>}
      </div>
      <p className="mt-2 text-[11.5px] text-ink-body leading-relaxed">{sub}</p>
    </div>
  );
}

function PHISparkline({ values }) {
  const w = 110, h = 36, pad = 3;
  const max = Math.max(...values), min = Math.min(...values);
  const span = max - min || 1;
  const dx = (w - 2 * pad) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = pad + i * dx;
    const y = h - pad - ((v - min) / span) * (h - 2 * pad);
    return `${x},${y}`;
  });
  const area = `${pad},${h - pad} ${pts.join(" ")} ${w - pad},${h - pad}`;
  return (
    <svg width={w} height={h} className="block">
      <polygon points={area} fill="var(--accent-cyan)" opacity="0.15" />
      <polyline points={pts.join(" ")} fill="none" stroke="var(--accent-cyan)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      {values.map((v, i) => {
        const [x, y] = pts[i].split(",").map(Number);
        return <circle key={i} cx={x} cy={y} r={i === values.length - 1 ? 2.2 : 0} fill="var(--accent-cyan)" />;
      })}
    </svg>
  );
}

function ClauseCard({ clause, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`text-left p-4 transition-colors ${
        selected ? "bg-brand-50" : "bg-surface-raised hover:bg-surface-raised-hi"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-md bg-accent-green/15 border border-accent-green/30 text-accent-green flex items-center justify-center shrink-0">
          <I.Check className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">§ {clause.id.toUpperCase()}</span>
            <Pill tone="green">in force</Pill>
          </div>
          <div className="text-[13px] font-semibold text-ink-primary mt-0.5">{clause.title}</div>
          <p className="text-[12px] text-ink-body mt-1 leading-relaxed line-clamp-2">{clause.blurb}</p>
        </div>
      </div>
    </button>
  );
}

window.CompliancePage = CompliancePage;
