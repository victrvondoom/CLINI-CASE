/* global window, React */
const { useState: useStateCo } = React;

function CohortsPage({ navigate }) {
  const { PAYERS, DRUGS, MATRIX, KPIS } = window.CLINCASE_COHORTS;
  const [drillPayer, setDrillPayer] = useStateCo(null);
  const [drillDrug,  setDrillDrug]  = useStateCo(null);

  return (
    <div data-screen-label="cohorts" className="space-y-5">
      <header>
        <Eyebrow>Analytics · Cohorts</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          Cohort analytics
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          Slice approval rate and time-to-decision by payer × drug × indication. Click any bar to drill into the
          underlying case list — useful for finding step-therapy bottlenecks or payer-specific friction.
        </p>
      </header>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterChip active>last 30d</FilterChip>
        <FilterChip>last 7d</FilterChip>
        <FilterChip>this quarter</FilterChip>
        <span className="mx-2 text-ink-faint">·</span>
        <FilterChip active>oncology</FilterChip>
        <FilterChip>specialty drugs</FilterChip>
        <span className="ml-auto text-[11px] font-mono text-ink-muted">
          {KPIS.total_cases.toLocaleString()} cases · 4 payers · 3 drugs
        </span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <CohortKPI label="overall approval rate"   value={`${Math.round(KPIS.overall_approval * 100)}%`} sub="across all payers and drugs" accent="green" />
        <CohortKPI label="median time-to-decision" value={`${Math.floor(KPIS.median_decision_seconds / 60)}m ${KPIS.median_decision_seconds % 60}s`} sub="DAG end-to-end, excluding human review" accent="cyan" />
        <CohortKPI label="appeals overturned"      value={`${Math.round(KPIS.appeals_overturned * 100)}%`} sub="of denials successfully appealed" accent="violet" />
      </div>

      {/* Stacked bar chart */}
      <section className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">approval rate by payer × drug</div>
            <div className="text-[14px] font-semibold text-ink-primary">stacked breakdown</div>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <Legend color="bg-accent-green" label="APPROVE" />
            <Legend color="bg-accent-amber" label="REFER" />
            <Legend color="bg-accent-red"   label="DENY" />
          </div>
        </div>

        <div className="p-5 grid grid-cols-1 md:grid-cols-4 gap-4">
          {PAYERS.map((pid) => (
            <div key={pid}>
              <div className="flex items-center gap-2 mb-3">
                <PayerChip id={pid} small />
              </div>
              <div className="space-y-2.5">
                {DRUGS.map((d) => {
                  const c = MATRIX[pid][d];
                  const total = c.approve + c.deny + c.refer;
                  const pa = c.approve / total, pr = c.refer / total, pd = c.deny / total;
                  const isDrill = drillPayer === pid && drillDrug === d;
                  return (
                    <button
                      key={d}
                      onClick={() => { setDrillPayer(pid); setDrillDrug(d); }}
                      className={`w-full text-left group rounded-md p-1.5 -m-1.5 transition-colors ${
                        isDrill ? "bg-brand-50" : "hover:bg-surface-raised-hi"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-ink-body truncate">{d}</span>
                        <span className="text-[11px] font-mono text-ink-primary tabular-nums">{Math.round(pa * 100)}%</span>
                      </div>
                      <div className="h-2 flex rounded-full overflow-hidden bg-surface-raised-hi">
                        <span className="h-full bg-accent-green" style={{ width: `${pa * 100}%` }} />
                        <span className="h-full bg-accent-amber" style={{ width: `${pr * 100}%` }} />
                        <span className="h-full bg-accent-red"   style={{ width: `${pd * 100}%` }} />
                      </div>
                      <div className="mt-1 text-[10px] font-mono text-ink-muted">
                        {c.approve} / {total} approved
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Drill-down table */}
      {drillPayer && drillDrug && (
        <DrillDown payer={drillPayer} drug={drillDrug} matrix={MATRIX} />
      )}
    </div>
  );
}

function FilterChip({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1.5 text-[12px] rounded-md border transition-colors ${
        active
          ? "bg-brand-50 border-accent-brand text-accent-brand"
          : "bg-surface-raised border-surface-border text-ink-body hover:border-surface-border-hi"
      }`}
    >
      {children}
    </button>
  );
}

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1 text-ink-muted">
      <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
      {label}
    </span>
  );
}

function CohortKPI({ label, value, sub, accent }) {
  const tone = accent === "green" ? "text-accent-green" : accent === "cyan" ? "text-accent-cyan" : "text-accent-violet";
  return (
    <div className="rounded-xl bg-surface-raised border border-surface-border p-4">
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">{label}</div>
      <div className={`text-[28px] font-semibold tabular-nums mt-0.5 ${tone}`}>{value}</div>
      <div className="text-[12px] text-ink-body mt-1">{sub}</div>
    </div>
  );
}

function DrillDown({ payer, drug, matrix }) {
  const c = matrix[payer][drug];
  const total = c.approve + c.deny + c.refer;
  const SAMPLE = [
    { id: "AUTH-2026-1842", initials: "M.K.", verdict: "APPROVE", confidence: 0.94, latency: "4m 18s" },
    { id: "AUTH-2026-1841", initials: "A.K.", verdict: "REFER",   confidence: 0.71, latency: "3m 52s" },
    { id: "AUTH-2026-1839", initials: "D.R.", verdict: "REFER",   confidence: 0.68, latency: "4m 06s" },
    { id: "AUTH-2026-1837", initials: "P.L.", verdict: "DENY",    confidence: 0.91, latency: "5m 14s" },
    { id: "AUTH-2026-1834", initials: "C.B.", verdict: "APPROVE", confidence: 0.96, latency: "3m 48s" },
    { id: "AUTH-2026-1832", initials: "T.J.", verdict: "REFER",   confidence: 0.62, latency: "4m 22s" },
  ];
  return (
    <section className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden">
      <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PayerChip id={payer} small />
          <span className="text-[14px] font-semibold text-ink-primary">{drug}</span>
          <span className="text-[11px] font-mono text-ink-muted">· {total} cases · {Math.round((c.approve / total) * 100)}% approval</span>
        </div>
        <div className="text-[11px] font-mono text-ink-muted">showing 6 of {total}</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead className="bg-surface-bg/50">
            <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-ink-muted">
              <th className="px-5 py-2.5">case</th>
              <th className="px-3 py-2.5">patient</th>
              <th className="px-3 py-2.5">verdict</th>
              <th className="px-3 py-2.5">confidence</th>
              <th className="px-3 py-2.5">latency</th>
              <th className="px-5 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {SAMPLE.map((s) => (
              <tr key={s.id} className="hover:bg-surface-raised-hi cursor-pointer">
                <td className="px-5 py-2.5 font-mono text-ink-muted text-[11px]">{s.id}</td>
                <td className="px-3 py-2.5 text-ink-body">{s.initials}</td>
                <td className="px-3 py-2.5">
                  <Pill tone={s.verdict === "APPROVE" ? "green" : s.verdict === "DENY" ? "red" : "amber"}>{s.verdict}</Pill>
                </td>
                <td className="px-3 py-2.5 font-mono tabular-nums text-ink-primary">{(s.confidence * 100).toFixed(0)}%</td>
                <td className="px-3 py-2.5 font-mono tabular-nums text-ink-body">{s.latency}</td>
                <td className="px-5 py-2.5 text-right">
                  <I.ChevronRight className="w-3.5 h-3.5 text-ink-faint inline" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

window.CohortsPage = CohortsPage;
