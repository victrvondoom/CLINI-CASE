// =============================================================
// Multi-Payer Compare page
// =============================================================
const { useState: useStateCM, useMemo: useMemoCM } = React;

function ComparePage({ navigate, fixtures }) {
  const extra = window.CLINCASE_EXTRA;

  // Default scenario = Pembrolizumab NSCLC (the approve fixture)
  const scenarios = [
    { key: "nsclc",  label: "Pembrolizumab · NSCLC, PD-L1 ≥1%",       drug: "Pembrolizumab",  j: "J9271", indication: "NSCLC, PD-L1 ≥1%" },
    { key: "her2",   label: "Trastuzumab · HER2+ breast",              drug: "Trastuzumab",    j: "J9355", indication: "HER2+ breast" },
    { key: "tnbc",   label: "Atezolizumab · TNBC",                     drug: "Atezolizumab",   j: "J9022", indication: "TNBC" },
  ];
  const [scenario, setScenario] = useStateCM("nsclc");
  const sc = scenarios.find((s) => s.key === scenario);

  // Comparison rows for each (scenario, payer)
  // Verdict reasoning: scenario "nsclc" has clean PD-L1 ≥1% w/ EGFR-WT
  // Different payers weight evidence differently.
  const COMPARE_DATA = {
    nsclc: [
      { payer: "aetna",   verdict: "APPROVE", confidence: 0.94, doc_match: 1.00, time_s: 287, cost: 0.34, policy_id: "AET-ONC-2026-031", policy_section: "§4.2(a)",
        gating: ["PD-L1 ≥1% confirmed", "EGFR/ALK wild-type", "ECOG 0–1"], blockers: [] },
      { payer: "uhc",     verdict: "APPROVE", confidence: 0.91, doc_match: 0.93, time_s: 312, cost: 0.36, policy_id: "UHC-ONC-2026-114", policy_section: "§3.1(c)",
        gating: ["PD-L1 ≥1%", "Stage IV", "Prior chemo not required"], blockers: [] },
      { payer: "anthem",  verdict: "REFER",  confidence: 0.71, doc_match: 0.86, time_s: 401, cost: 0.51, policy_id: "BCBS-ONC-2026-077", policy_section: "§5.4(b)",
        gating: ["PD-L1 ≥1%", "Stage IV"], blockers: ["Requires prior platinum doublet OR documented contraindication"] },
      { payer: "cigna",   verdict: "APPROVE", confidence: 0.88, doc_match: 0.95, time_s: 268, cost: 0.32, policy_id: "CIG-ONC-2026-044", policy_section: "§2.3(a)",
        gating: ["PD-L1 ≥1%", "EGFR-WT", "ECOG ≤2"], blockers: [] },
    ],
    her2: [
      { payer: "aetna",   verdict: "APPROVE", confidence: 0.92, doc_match: 0.97, time_s: 244, cost: 0.31, policy_id: "AET-ONC-2026-018", policy_section: "§3.1",
        gating: ["IHC 3+ OR FISH ratio ≥2.0", "Adjuvant or metastatic"], blockers: [] },
      { payer: "uhc",     verdict: "DENY",    confidence: 0.89, doc_match: 0.78, time_s: 356, cost: 0.42, policy_id: "UHC-ONC-2026-091", policy_section: "§4.2(b)",
        gating: ["IHC 3+ AND FISH ratio ≥2.0"], blockers: ["Submitted IHC 2+; FISH not provided in record"] },
      { payer: "anthem",  verdict: "APPROVE", confidence: 0.86, doc_match: 0.92, time_s: 298, cost: 0.34, policy_id: "BCBS-ONC-2026-046", policy_section: "§3.4",
        gating: ["HER2 positive by IHC 3+ or FISH"], blockers: [] },
      { payer: "cigna",   verdict: "REFER",  confidence: 0.65, doc_match: 0.84, time_s: 422, cost: 0.49, policy_id: "CIG-ONC-2026-052", policy_section: "§3.5",
        gating: ["HER2 positivity"], blockers: ["LVEF result missing — required pre-trastuzumab"] },
    ],
    tnbc: [
      { payer: "aetna",   verdict: "REFER",  confidence: 0.62, doc_match: 0.81, time_s: 388, cost: 0.47, policy_id: "AET-ONC-2026-029", policy_section: "§4.6",
        gating: ["PD-L1 SP142 ≥1% on IC"], blockers: ["PD-L1 22C3 submitted; SP142 required"] },
      { payer: "uhc",     verdict: "APPROVE", confidence: 0.84, doc_match: 0.91, time_s: 281, cost: 0.35, policy_id: "UHC-ONC-2026-067", policy_section: "§5.1",
        gating: ["PD-L1 by any FDA-approved assay"], blockers: [] },
      { payer: "anthem",  verdict: "DENY",    confidence: 0.88, doc_match: 0.83, time_s: 341, cost: 0.40, policy_id: "BCBS-ONC-2026-077", policy_section: "§5.4(b)",
        gating: ["PD-L1 SP142 ≥1%"], blockers: ["Tightened 2026-04 — only SP142 accepted now"] },
      { payer: "cigna",   verdict: "APPROVE", confidence: 0.79, doc_match: 0.88, time_s: 312, cost: 0.36, policy_id: "CIG-ONC-2026-061", policy_section: "§4.3",
        gating: ["PD-L1 expression confirmed"], blockers: [] },
    ],
  };
  const rows = COMPARE_DATA[scenario];

  // Recommendation: pick the payer with highest confidence among APPROVE
  const recommendation = useMemoCM(() => {
    const approves = rows.filter((r) => r.verdict === "APPROVE")
                         .sort((a, b) => b.confidence - a.confidence);
    return approves[0] || null;
  }, [rows]);

  return (
    <div className="space-y-5">
      <header>
        <Eyebrow>Workspace · Multi-payer Compare</Eyebrow>
        <h1 className="display-tight font-bold text-ink-primary text-[28px] mt-1.5">Compare across payers</h1>
        <p className="text-[13px] text-ink-body mt-1 max-w-prose">
          Run a hypothetical request against four payer policies side-by-side. Useful when picking which plan to file under, or when the patient has dual coverage.
        </p>
      </header>

      {/* Scenario picker */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-1.5">Clinical scenario</div>
            <div className="flex items-center gap-2 flex-wrap">
              {scenarios.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setScenario(s.key)}
                  className={`h-9 px-3 rounded-md text-[12px] font-medium border transition-all ${
                    scenario === s.key
                      ? "bg-accent-brand/15 border-accent-brand/60 text-ink-primary"
                      : "bg-surface-bg border-surface-border text-ink-body hover:bg-surface-raised-hi"
                  }`}
                >{s.label}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="h-9 px-3 rounded-md border border-surface-border bg-surface-bg text-[12px] text-ink-body inline-flex items-center gap-1.5 hover:bg-surface-raised-hi">
              <I.RefreshCw size={13} /> Re-run
            </button>
            <button className="h-9 px-3 rounded-md border border-surface-border bg-surface-bg text-[12px] text-ink-body inline-flex items-center gap-1.5 hover:bg-surface-raised-hi">
              <I.Copy size={13} /> Export
            </button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-3 max-w-2xl">
          <ScenarioStat label="Drug" value={sc.drug} mono />
          <ScenarioStat label="J-code" value={sc.j} mono />
          <ScenarioStat label="Indication" value={sc.indication} />
        </div>
      </section>

      {/* Recommendation panel */}
      {recommendation && (
        <section className="relative bg-surface-raised border border-accent-green/40 rounded-2xl p-5 overflow-hidden">
          <div className="absolute inset-0 pointer-events-none opacity-60"
               style={{ background: "radial-gradient(ellipse at top right, rgba(52,211,153,0.12), transparent 60%)" }} />
          <div className="relative flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg grid place-items-center shrink-0"
                 style={{ background: "linear-gradient(135deg, rgba(52,211,153,0.25), rgba(52,211,153,0.05))", border: "1px solid rgba(52,211,153,0.3)" }}>
              <I.CheckCircle size={20} className="text-accent-green" />
            </div>
            <div className="flex-1">
              <div className="text-[10px] font-mono uppercase tracking-widest text-accent-green">ClinCase recommends</div>
              <div className="mt-1 flex items-center gap-2 flex-wrap">
                <PayerChip id={recommendation.payer} />
                <span className="text-[14px] text-ink-primary">— file with this payer first.</span>
              </div>
              <p className="text-[12.5px] text-ink-body mt-2 leading-relaxed max-w-3xl">
                Highest confidence ({Math.round(recommendation.confidence*100)}%), no blocking documentation gaps,
                fastest expected decision ({Math.floor(recommendation.time_s/60)}m {recommendation.time_s%60}s),
                lowest agent cost (${recommendation.cost.toFixed(2)}). Cited from {recommendation.policy_id} {recommendation.policy_section}.
              </p>
            </div>
            <button className="h-8 px-3 rounded-md bg-accent-green/15 border border-accent-green/40 text-accent-green text-[11px] font-medium hover:bg-accent-green/25 shrink-0">
              File now
            </button>
          </div>
        </section>
      )}

      {/* Comparison grid */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-4 divide-y lg:divide-y-0 lg:divide-x divide-surface-border">
          {rows.map((r) => (
            <ComparePayerColumn key={r.payer} row={r} isRec={recommendation && r.payer === recommendation.payer} />
          ))}
        </div>
      </section>

      <p className="text-[11px] font-mono text-ink-muted">
        Compare runs are sandbox simulations — patient PHI is never sent across payer boundaries. Each verdict is anchored to the policy ID and section shown.
      </p>
    </div>
  );
}

function ScenarioStat({ label, value, mono }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-ink-muted">{label}</div>
      <div className={`text-[13px] mt-0.5 text-ink-primary ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function ComparePayerColumn({ row, isRec }) {
  const tone = row.verdict === "APPROVE" ? "emerald" : row.verdict === "DENY" ? "rose" : "amber";
  const ringColor =
    row.verdict === "APPROVE" ? "rgba(52,211,153,0.45)" :
    row.verdict === "DENY"    ? "rgba(244,114,182,0.45)" :
                                "rgba(251,191,36,0.45)";
  return (
    <div className={`p-5 relative ${isRec ? "bg-accent-green/[0.04]" : ""}`}>
      {isRec && (
        <span className="absolute top-3 right-3 text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded bg-accent-green/20 text-accent-green border border-accent-green/30">
          Best
        </span>
      )}
      <PayerChip id={row.payer} />

      {/* verdict + confidence */}
      <div className="mt-4 flex items-center gap-3">
        <Pill tone={tone} className="text-[11px]">{row.verdict}</Pill>
        <CompareConfidenceRing pct={row.confidence} color={ringColor} />
      </div>

      {/* metrics */}
      <div className="mt-4 grid grid-cols-2 gap-y-2.5 gap-x-3 text-[11px]">
        <Metric label="Doc match"    value={`${Math.round(row.doc_match*100)}%`} mono />
        <Metric label="Decision"     value={`${Math.floor(row.time_s/60)}m ${row.time_s%60}s`} mono />
        <Metric label="Cost"         value={`$${row.cost.toFixed(2)}`} mono accent="cyan" />
        <Metric label="Policy"       value={row.policy_section} mono />
      </div>

      <div className="mt-3 text-[10px] font-mono text-ink-faint truncate" title={row.policy_id}>
        {row.policy_id}
      </div>

      {/* gating */}
      <div className="mt-4">
        <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-1.5">Gating criteria</div>
        <ul className="space-y-1">
          {row.gating.map((g, i) => (
            <li key={i} className="flex items-start gap-1.5 text-[11.5px] text-ink-body">
              <I.CheckCircle size={11} className="text-accent-green mt-0.5 shrink-0" />
              <span className="leading-snug">{g}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* blockers */}
      {row.blockers.length > 0 && (
        <div className="mt-3 p-2.5 rounded-md bg-accent-rose/10 border border-accent-rose/25">
          <div className="text-[10px] font-mono uppercase tracking-widest text-accent-rose mb-1">Blockers</div>
          <ul className="space-y-1">
            {row.blockers.map((b, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[11.5px] text-ink-body leading-snug">
                <I.AlertTriangle size={11} className="text-accent-rose mt-0.5 shrink-0" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, mono, accent }) {
  const valColor = accent === "cyan" ? "text-accent-cyan" : "text-ink-primary";
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-ink-muted">{label}</div>
      <div className={`mt-0.5 ${valColor} ${mono ? "font-mono" : ""} tabular-nums`}>{value}</div>
    </div>
  );
}

function CompareConfidenceRing({ pct, color }) {
  const r = 14, c = 2 * Math.PI * r;
  return (
    <div className="relative w-9 h-9">
      <svg viewBox="0 0 36 36" className="w-9 h-9 -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="var(--surface-border)" strokeWidth="3" />
        <circle cx="18" cy="18" r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
                style={{ transition: "stroke-dashoffset 600ms ease-out" }} />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-[10px] font-mono tabular-nums text-ink-primary">
        {Math.round(pct*100)}
      </span>
    </div>
  );
}

window.ComparePage = ComparePage;
