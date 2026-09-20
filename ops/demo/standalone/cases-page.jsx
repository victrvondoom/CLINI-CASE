// =============================================================
// Cases page — filters + table + pagination
// =============================================================
const { useState: useStateC, useMemo: useMemoC } = React;

function CasesPage({ navigate, allCases }) {
  const extra = window.CLINCASE_EXTRA;
  const cases = allCases || extra.CASES;

  const [verdict, setVerdict]   = useStateC("all");
  const [payer,   setPayer]     = useStateC("all");
  const [query,   setQuery]     = useStateC("");

  const filtered = useMemoC(() => {
    return cases.filter((c) => {
      if (verdict !== "all") {
        if (verdict === "running" && c.status !== "running") return false;
        if (verdict !== "running" && c.verdict !== verdict)  return false;
      }
      if (payer !== "all" && c.payer !== payer) return false;
      if (query) {
        const q = query.toLowerCase();
        const blob = `${c.id} ${c.treatment} ${c.j_code} ${c.initials} ${c.payer}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }, [verdict, payer, query, cases]);

  const counts = useMemoC(() => {
    const all     = cases.length;
    const running = cases.filter((c) => c.status === "running").length;
    const approve = cases.filter((c) => c.verdict === "APPROVE").length;
    const deny    = cases.filter((c) => c.verdict === "DENY").length;
    const refer   = cases.filter((c) => c.verdict === "REFER").length;
    return { all, running, APPROVE: approve, DENY: deny, REFER: refer };
  }, [cases]);

  const Tab = ({ value, label, n, tone }) => {
    const active = verdict === value;
    return (
      <button
        onClick={() => setVerdict(value)}
        className={`relative h-9 px-3 -mb-px text-[12px] font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
          active ? "border-accent-brand text-ink-primary" : "border-transparent text-ink-muted hover:text-ink-body"
        }`}
        aria-pressed={active}
      >
        {label}
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${active ? "bg-accent-brand/15 text-accent-brand-glow" : "bg-surface-raised text-ink-muted"}`}>{n}</span>
      </button>
    );
  };

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Eyebrow>Workspace · Cases</Eyebrow>
          <h1 className="display-tight font-bold text-ink-primary text-[28px] mt-1.5">Cases</h1>
          <p className="text-[13px] text-ink-body mt-1 max-w-prose">
            Every prior-auth request that has touched the agent DAG. Filter, search, and step into any decision to read the citation chain.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="h-9 px-3 rounded-md border border-surface-border bg-surface-raised hover:bg-surface-raised-hi text-[12px] text-ink-body inline-flex items-center gap-1.5">
            <I.Filter size={13} className="text-ink-muted" /> More filters
          </button>
          <button
            onClick={() => navigate("#/cases/bulk-import")}
            className="h-9 px-3 rounded-md border border-accent-brand/40 bg-accent-brand/10 text-accent-brand-glow text-[12px] inline-flex items-center gap-1.5 hover:bg-accent-brand/20"
          >
            <I.Upload size={13} /> Bulk import
          </button>
        </div>
      </header>

      <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
        {/* Tab bar */}
        <div className="px-5 border-b border-surface-border flex items-center gap-1 overflow-x-auto">
          <Tab value="all"     label="All"      n={counts.all}     />
          <Tab value="running" label="Running"  n={counts.running} />
          <Tab value="APPROVE" label="Approved" n={counts.APPROVE} />
          <Tab value="DENY"    label="Denied"   n={counts.DENY}    />
          <Tab value="REFER"   label="Referred" n={counts.REFER}   />
        </div>

        {/* Filter row */}
        <div className="px-5 py-3 border-b border-surface-border flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 max-w-md">
            <I.Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by ID, drug, J-code, initials…"
              className="w-full h-8 pl-7 pr-3 text-[12px] bg-surface-bg border border-surface-border rounded-md text-ink-primary placeholder-ink-faint focus:outline-none focus:border-accent-brand/60"
            />
          </div>
          <select
            value={payer}
            onChange={(e) => setPayer(e.target.value)}
            className="h-8 px-2 text-[12px] bg-surface-bg border border-surface-border rounded-md text-ink-body focus:outline-none focus:border-accent-brand/60"
          >
            <option value="all">All payers</option>
            {extra.PAYERS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <span className="text-[11px] font-mono text-ink-muted ml-auto">
            {filtered.length} of {cases.length}
          </span>
        </div>

        {/* Header row */}
        <div className="px-5 py-2 border-b border-surface-border grid grid-cols-[110px_1fr_120px_72px_90px_24px] gap-3 text-[10px] font-mono uppercase tracking-widest text-ink-muted">
          <span>Verdict</span>
          <span>Patient · Treatment</span>
          <span>Payer</span>
          <span className="text-right">Confidence</span>
          <span className="text-right">Submitted</span>
          <span></span>
        </div>

        {/* Body */}
        <div className="divide-y divide-surface-border">
          {filtered.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <div className="text-ink-muted text-[13px]">No cases match these filters.</div>
              <button
                onClick={() => { setVerdict("all"); setPayer("all"); setQuery(""); }}
                className="mt-2 text-[12px] font-mono text-accent-brand-glow hover:underline"
              >Reset filters</button>
            </div>
          ) : (
            filtered.map((c, i) => <CaseRow key={c.id} c={c} navigate={navigate} idx={i} />)
          )}
        </div>

        {/* Pagination */}
        <div className="px-5 py-3 border-t border-surface-border flex items-center justify-between text-[11px] font-mono text-ink-muted">
          <span>Page 1 of 1 · 47 total cases · 35 archived</span>
          <div className="flex items-center gap-1.5">
            <button disabled className="h-7 px-2 rounded border border-surface-border text-ink-faint disabled:opacity-50 inline-flex items-center gap-1">
              <I.ArrowLeft size={11} /> Prev
            </button>
            <button disabled className="h-7 px-2 rounded border border-surface-border text-ink-faint disabled:opacity-50 inline-flex items-center gap-1">
              Next <I.ArrowRight size={11} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

window.CasesPage = CasesPage;
