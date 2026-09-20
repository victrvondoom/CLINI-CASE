/* global window, React */
const { useState: useStateP, useMemo: useMemoP } = React;

// ============================================================================
// Policies — library + diff viewer (P2)
// ============================================================================

function PoliciesPage({ navigate }) {
  const { POLICIES, DIFFS } = window.CLINCASE_POLICIES;
  const [q, setQ] = useStateP("");
  const [payerFilter, setPayerFilter] = useStateP("all");

  const payers = useMemoP(() => {
    const ids = Array.from(new Set(POLICIES.map((p) => p.payer_id)));
    return ids;
  }, [POLICIES]);

  const filtered = POLICIES.filter((p) => {
    if (payerFilter !== "all" && p.payer_id !== payerFilter) return false;
    if (!q.trim()) return true;
    const needle = q.toLowerCase();
    return (
      p.title.toLowerCase().includes(needle) ||
      p.drug.toLowerCase().includes(needle) ||
      p.number.toLowerCase().includes(needle) ||
      p.indications.some((i) => i.toLowerCase().includes(needle))
    );
  });

  return (
    <div data-screen-label="policies" className="space-y-5">
      <header>
        <Eyebrow>Knowledge · Policies</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">Policy Library</h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          Indexed payer medical policies + NCCN guideline excerpts. Versioned, diff-tracked, citation-ready —
          every policy here is a live source of truth for the agent DAG.
        </p>
      </header>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[280px] max-w-[460px]">
          <I.Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search payer / drug / policy number…"
            className="w-full pl-9 pr-3 py-2.5 text-[13px] bg-surface-raised border border-surface-border rounded-lg text-ink-primary placeholder:text-ink-muted focus:outline-none focus:border-accent-brand"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <FilterChip active={payerFilter === "all"}      onClick={() => setPayerFilter("all")}     >All payers</FilterChip>
          {payers.map((id) => (
            <FilterChip key={id} active={payerFilter === id} onClick={() => setPayerFilter(id)}>
              <PayerChip id={id} small /> 
            </FilterChip>
          ))}
        </div>
        <div className="ml-auto text-[11px] font-mono text-ink-muted">
          {filtered.length} policies · {Object.keys(DIFFS).length} pending diff
        </div>
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((p) => (
          <PolicyCard key={p.id} p={p} navigate={navigate} hasDiff={p.hasDiff} />
        ))}
      </div>
    </div>
  );
}

function FilterChip({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1.5 text-[12px] rounded-md border transition-colors inline-flex items-center gap-1.5 ${
        active
          ? "bg-brand-50 border-accent-brand text-accent-brand"
          : "bg-surface-raised border-surface-border text-ink-body hover:border-surface-border-hi"
      }`}
    >
      {children}
    </button>
  );
}

function PolicyCard({ p, navigate, hasDiff }) {
  return (
    <article className="rounded-xl bg-surface-raised border border-surface-border hover:border-surface-border-hi transition-colors overflow-hidden flex flex-col">
      <div className="p-4 flex-1">
        <div className="flex items-start gap-3">
          <div className="shrink-0">
            <PayerChip id={p.payer_id} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono text-ink-muted uppercase tracking-wider">{p.number}</span>
              <span className="text-[10px] font-mono text-ink-faint">·</span>
              <span className="text-[10px] font-mono text-ink-muted">{p.version}</span>
              {hasDiff && (
                <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-mono text-accent-amber">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-amber animate-pulse" />
                  diff
                </span>
              )}
            </div>
            <h3 className="text-[14px] font-semibold text-ink-primary leading-snug">{p.title}</h3>
          </div>
        </div>
        <p className="mt-3 text-[12.5px] text-ink-body leading-relaxed">{p.summary}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {p.indications.map((ind) => (
            <span key={ind} className="px-2 py-0.5 text-[10px] font-mono bg-surface-raised-hi text-ink-body rounded border border-surface-border">
              {ind}
            </span>
          ))}
        </div>
      </div>
      <div className="px-4 py-2.5 border-t border-surface-border bg-surface-bg/50 flex items-center gap-2">
        <button className="flex-1 text-[12px] font-medium text-ink-body hover:text-ink-primary inline-flex items-center justify-center gap-1.5 py-1.5 rounded-md hover:bg-surface-raised-hi">
          <I.Eye className="w-3.5 h-3.5" /> View
        </button>
        {hasDiff ? (
          <button
            onClick={() => navigate(`#/policies/${p.id}/diff`)}
            className="flex-1 text-[12px] font-medium text-accent-brand hover:text-accent-brand inline-flex items-center justify-center gap-1.5 py-1.5 rounded-md bg-brand-50 hover:bg-brand-100 border border-accent-brand/20"
          >
            <I.GitBranch className="w-3.5 h-3.5" /> Diff vs prev
          </button>
        ) : (
          <button className="flex-1 text-[12px] font-medium text-ink-faint cursor-not-allowed inline-flex items-center justify-center gap-1.5 py-1.5 rounded-md">
            <I.GitBranch className="w-3.5 h-3.5" /> No changes
          </button>
        )}
      </div>
    </article>
  );
}

// ----------------------------------------------------------------------------
// Diff viewer
// ----------------------------------------------------------------------------
function PolicyDiffPage({ navigate, policyId }) {
  const { POLICIES, DIFFS } = window.CLINCASE_POLICIES;
  const data = window.CLINCASE_DATA;
  const policy = POLICIES.find((p) => p.id === policyId);
  const diff = DIFFS[policyId];

  if (!policy || !diff) {
    return (
      <div className="rounded-2xl bg-surface-raised border border-surface-border p-8 text-center">
        <h2 className="text-[16px] font-semibold text-ink-primary">Policy not found</h2>
        <button onClick={() => navigate("#/policies")} className="mt-3 text-[12px] text-accent-brand">← Back to policies</button>
      </div>
    );
  }

  return (
    <div data-screen-label="policies-diff" className="space-y-5">
      {/* Header */}
      <header>
        <button
          onClick={() => navigate("#/policies")}
          className="text-[11px] font-mono text-ink-muted hover:text-ink-primary inline-flex items-center gap-1 mb-2"
        >
          <I.ArrowLeft className="w-3 h-3" /> Policies
        </button>
        <Eyebrow>Knowledge · Policies · Diff</Eyebrow>
        <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-ink-primary display-tight">
          {diff.title}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-mono text-ink-muted line-through">{diff.fromVersion}</span>
          <I.ArrowRight className="w-3 h-3 text-ink-muted" />
          <span className="px-2 py-0.5 text-[11px] font-mono bg-accent-green/10 text-accent-green border border-accent-green/30 rounded">{diff.toVersion}</span>
          <span className="text-[11px] font-mono text-ink-muted">· effective {diff.effective}</span>
          <span className="text-[11px] font-mono text-ink-muted">· {diff.section}</span>
        </div>
      </header>

      {/* Two-column body — diff + right rail */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        {/* Diff column */}
        <div className="space-y-3">
          {/* Impact banner */}
          <div className="rounded-xl bg-accent-amber/8 border border-accent-amber/30 p-4 flex items-start gap-3">
            <I.AlertTriangle className="w-5 h-5 text-accent-amber shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-[13px] font-semibold text-ink-primary">{diff.impact.cases_affected} case affected by this change</div>
              <p className="text-[12.5px] text-ink-body mt-1 leading-relaxed">
                {diff.summary}
              </p>
              <button
                onClick={() => navigate("#/cases")}
                className="mt-2 text-[12px] font-medium text-accent-brand hover:underline inline-flex items-center gap-1"
              >
                Jump to {diff.impact.hint_case_id}
                <I.ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Side-by-side diff */}
          <div className="rounded-xl bg-surface-raised border border-surface-border overflow-hidden">
            <div className="grid grid-cols-2 border-b border-surface-border">
              <div className="px-4 py-2.5 border-r border-surface-border">
                <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">previous</div>
                <div className="text-[12px] font-mono text-ink-body line-through">{diff.fromVersion}</div>
              </div>
              <div className="px-4 py-2.5">
                <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">current</div>
                <div className="text-[12px] font-mono text-accent-green">{diff.toVersion}</div>
              </div>
            </div>
            <DiffBody rows={diff.rows} />
          </div>
        </div>

        {/* Right rail */}
        <aside className="space-y-3">
          <div className="rounded-xl bg-surface-raised border border-surface-border p-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-2">Agents that consume this policy</div>
            <div className="space-y-2">
              {diff.consumed_by_agents.map((k) => {
                const spec = data.AGENT_SPECS.find((a) => a.key === k);
                return (
                  <button
                    key={k}
                    onClick={() => navigate("#/agents")}
                    className="w-full text-left px-2.5 py-2 rounded-md bg-surface-bg border border-surface-border hover:border-surface-border-hi transition-colors flex items-center gap-2"
                  >
                    <I.Cpu className="w-3.5 h-3.5 text-accent-violet shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] font-semibold text-ink-primary truncate">{spec ? spec.name : k}</div>
                      <div className="text-[10px] font-mono text-ink-muted truncate">{k}</div>
                    </div>
                    <I.ChevronRight className="w-3.5 h-3.5 text-ink-faint shrink-0" />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl bg-surface-raised border border-surface-border p-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-1">Re-run affected case</div>
            <div className="text-[12.5px] text-ink-body mb-3 leading-relaxed">
              The new LVEF window may flip <span className="font-mono text-ink-primary">{diff.impact.hint_case_id}</span> from REFER to APPROVE.
            </div>
            <button className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[12px] font-medium bg-accent-brand text-white rounded-md hover:opacity-90">
              <I.Play className="w-3.5 h-3.5" /> Re-run with v2026.1
            </button>
          </div>

          <div className="rounded-xl bg-surface-raised border border-surface-border p-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-2">Change metadata</div>
            <div className="space-y-1.5 text-[11.5px] font-mono">
              <Row k="committed_by" v="aetna_policy_bot" />
              <Row k="reviewed_by"  v="aetna_med_director" />
              <Row k="ts"           v="2026-02-26 14:21" />
              <Row k="aligned_with" v="NCCN BINV-N v3.2026" />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-ink-muted">{k}</span>
      <span className="text-ink-faint">·</span>
      <span className="text-ink-primary truncate">{v}</span>
    </div>
  );
}

function DiffBody({ rows }) {
  // Side-by-side: each row renders its "before" cell and "after" cell.
  // For a `del` row, after cell is empty; for `add`, before cell is empty;
  // we group adjacent del+add into the same visual row when feasible.
  // For simplicity we render two parallel columns row-by-row from the rows[] list,
  // pairing del→add when they're adjacent.
  const paired = [];
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.kind === "del" && rows[i + 1] && rows[i + 1].kind === "add") {
      paired.push({ kind: "change", a: r, b: rows[i + 1] });
      i++;
      continue;
    }
    paired.push({ kind: r.kind, a: r.kind === "add" ? null : r, b: r.kind === "del" ? null : r });
  }

  return (
    <div className="font-mono text-[12px] leading-[1.65]">
      {paired.map((p, i) => {
        if (p.kind === "ctx") {
          const r = p.a;
          return (
            <div key={i} className="grid grid-cols-2">
              <DiffCell kind="ctx" num={r.a} text={r.text} />
              <DiffCell kind="ctx" num={r.b} text={r.text} />
            </div>
          );
        }
        if (p.kind === "change") {
          return (
            <div key={i} className="grid grid-cols-2">
              <DiffCell kind="del" num={p.a.a} text={p.a.text} />
              <DiffCell kind="add" num={p.b.b} text={p.b.text} />
            </div>
          );
        }
        if (p.kind === "del") {
          return (
            <div key={i} className="grid grid-cols-2">
              <DiffCell kind="del" num={p.a.a} text={p.a.text} />
              <DiffCell kind="empty" />
            </div>
          );
        }
        // add only
        return (
          <div key={i} className="grid grid-cols-2">
            <DiffCell kind="empty" />
            <DiffCell kind="add" num={p.b.b} text={p.b.text} />
          </div>
        );
      })}
    </div>
  );
}

function DiffCell({ kind, num, text }) {
  if (kind === "empty") {
    return <div className="px-3 py-1 bg-surface-bg/40 border-r border-surface-border last:border-r-0 min-h-[1.65em]" />;
  }
  const tone =
    kind === "add" ? "bg-accent-green/15 text-ink-primary border-l-2 border-accent-green"
    : kind === "del" ? "bg-accent-red/15 text-ink-body border-l-2 border-accent-red"
    : "border-l-2 border-transparent";
  const sign = kind === "add" ? "+" : kind === "del" ? "−" : " ";
  return (
    <div className={`px-3 py-1 border-r border-surface-border last:border-r-0 ${tone} flex gap-2`}>
      <span className="text-ink-faint w-6 shrink-0 text-right select-none">{num ?? ""}</span>
      <span className="text-ink-faint w-3 shrink-0 select-none">{sign}</span>
      <span className="whitespace-pre-wrap break-words">{text || "\u00A0"}</span>
    </div>
  );
}

window.PoliciesPage = PoliciesPage;
window.PolicyDiffPage = PolicyDiffPage;
