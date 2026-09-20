// =============================================================
// Dashboard page (replaces Home as / and /dashboard)
// =============================================================
const { useState: useStateD, useEffect: useEffectD, useRef: useRefD } = React;

function DashboardPage({ navigate, fixtures, onCreate }) {
  const extra = window.CLINCASE_EXTRA;
  const k = extra.KPIS;

  const [creating, setCreating] = useStateD(null);
  const handleCreate = (fx) => {
    setCreating(fx.name);
    setTimeout(() => {
      onCreate(fx);
      navigate(`#/cases/${fx.case_id}`);
    }, 350);
  };

  const headline = "Approve Cancer Treatment in Minutes, Not Weeks.";
  const headlineWords = headline.split(" ");

  return (
    <div className="space-y-5">
      {/* HERO band — institutional depth */}
      <section className="relative bg-surface-raised border border-surface-border rounded-2xl p-7 sm:p-9 overflow-hidden card-premium" style={{ boxShadow: "var(--shadow-raise)" }}>
        {/* Layered depth treatment: navy gradient wash + grid + shield silhouette */}
        <div aria-hidden="true" className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 opacity-[0.55]" style={{ background: "radial-gradient(900px 460px at 88% -10%, rgba(0,163,224,0.16), transparent 65%), radial-gradient(700px 380px at -10% 110%, rgba(0,51,161,0.18), transparent 60%)" }} />
          <div className="absolute inset-0 grid-bg opacity-50" />
          {/* Floating 3D shield mark */}
          <div className="hidden lg:block absolute right-8 top-1/2 -translate-y-1/2 motion-safe:animate-float-soft" style={{ filter: "drop-shadow(0 18px 40px rgba(0,51,161,0.30))" }}>
            <svg width="180" height="220" viewBox="0 0 180 220" className="opacity-90">
              <defs>
                <linearGradient id="hSh" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563d9" stopOpacity="0.85" />
                  <stop offset="60%" stopColor="#0033a1" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#0a1f44" />
                </linearGradient>
                <linearGradient id="hShG" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
                  <stop offset="50%" stopColor="#ffffff" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="hT" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#00b5b8" />
                  <stop offset="100%" stopColor="#00a3e0" />
                </linearGradient>
              </defs>
              <path d="M90 8 L168 30 V102 C168 156 138 196 90 214 C42 196 12 156 12 102 V30 Z" fill="url(#hSh)" stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
              <path d="M90 8 L168 30 V102 C168 156 138 196 90 214 C42 196 12 156 12 102 V30 Z" fill="url(#hShG)" />
              <rect x="82" y="50" width="16" height="100" rx="3" fill="#ffffff" opacity="0.92" />
              <rect x="50" y="86" width="80" height="16" rx="3" fill="#ffffff" opacity="0.92" />
              <path d="M30 130 L46 130 L52 116 L62 144 L72 124 L82 140 L92 124 L102 140 L112 116 L122 144 L130 130 L150 130" fill="none" stroke="url(#hT)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="150" cy="130" r="3" fill="#00b5b8" />
            </svg>
          </div>
        </div>
        <window.Spotlight />
        <div className="relative max-w-[64ch]">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md border border-accent-brand/25 bg-accent-brand/[0.06]">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan status-dot-live" />
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-accent-brand-glow">Healthcare · Prior Authorisation Automation</span>
          </div>
          <h1 className="display-tight font-bold leading-[1.04] mt-4 text-ink-primary text-[36px] sm:text-[48px] lg:text-[56px] max-w-[20ch]">
            {headlineWords.map((w, i) => {
              const isAccent = w.replace(/[.,]/g, "").toLowerCase() === "minutes";
              return (
                <React.Fragment key={i}>
                  <span
                    className={`inline-block motion-safe:animate-word-up ${isAccent ? "gradient-text-anim" : ""}`}
                    style={{ animationDelay: `${80 + i * 60}ms` }}
                  >
                    {w}
                  </span>
                  {i < headlineWords.length - 1 && " "}
                </React.Fragment>
              );
            })}
          </h1>
          <p className="text-ink-body leading-relaxed mt-4 max-w-[58ch] text-[14.5px]">
            Provider-side, FHIR-native copilot. Five agents read clinical evidence and payer policy, then ship a verdict with a citation chain. On denial, an NCCN-grounded appeal letter is drafted automatically.
          </p>
          <div className="mt-6 flex items-center gap-2 flex-wrap">
            <TrustChip dot="cyan">HIPAA · PHI redaction</TrustChip>
            <TrustChip dot="brand">FHIR R4 · USCDI v3</TrustChip>
            <TrustChip dot="green">Bedrock-ready</TrustChip>
            <TrustChip dot="cyan">CMS-0057-F · 2026 / 2027</TrustChip>
          </div>
        </div>
      </section>

      {/* KPI row */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPITile
          label="Active cases"
          value={k.active_cases}
          mono="—"
          trend={
            <Sparkline values={k.sparkline_active} color="var(--accent-brand-glow)" />
          }
        />
        <KPITile
          label="Avg time-to-decision"
          value={`${Math.floor(k.avg_decision_seconds/60)}m ${k.avg_decision_seconds%60}s`}
          trend={
            <span className="inline-flex items-center gap-1 text-[11px] font-mono text-accent-green">
              <I.TrendingDown size={11} /> -18% vs last week
            </span>
          }
        />
        <KPITile
          label="Approval rate"
          value={`${Math.round(k.approval_rate*100)}%`}
          trend={
            <span className="text-[10px] font-mono text-ink-muted">
              band {Math.round(k.approval_band[0]*100)}%–{Math.round(k.approval_band[1]*100)}% · 95% CI
            </span>
          }
        />
        <KPITile
          label="Cost-to-date"
          value={`$${k.cost_to_date.toFixed(2)}`}
          mono
          accent="cyan"
          trend={<span className="text-[10px] font-mono text-ink-muted">Sonnet 4.6 · cumulative</span>}
        />
      </div>

      {/* Case queue + Agent health */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <section className="xl:col-span-8 bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
          <header className="flex items-center justify-between px-5 py-3.5 border-b border-surface-border">
            <div className="flex items-center gap-2">
              <I.FolderOpen size={15} className="text-ink-muted" />
              <h2 className="font-semibold tracking-tight text-ink-primary text-[15px]">Recent cases</h2>
              <span className="text-[10px] font-mono text-ink-muted ml-1">last 6</span>
            </div>
            <button
              onClick={() => navigate("#/cases")}
              className="text-[12px] font-mono text-accent-brand-glow hover:underline"
            >
              View all 47 cases →
            </button>
          </header>
          <div className="divide-y divide-surface-border">
            {extra.CASES.slice(0, 6).map((c, i) => (
              <CaseRow key={c.id} c={c} navigate={navigate} idx={i} />
            ))}
          </div>
        </section>

        <section className="xl:col-span-4 bg-surface-raised border border-surface-border rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <I.Cpu size={15} className="text-ink-muted" />
              <h2 className="font-semibold tracking-tight text-ink-primary text-[15px]">Agent health</h2>
            </div>
            <span className="text-[10px] font-mono text-ink-muted">24h</span>
          </div>
          <ul className="space-y-2.5">
            {extra.AGENT_HEALTH.map((a) => (
              <li key={a.key} className="flex items-center gap-2.5 text-[12px]">
                <span className={`relative w-2 h-2 rounded-full shrink-0 ${a.success >= 0.999 ? "bg-accent-green" : "bg-accent-amber"}`}>
                  {a.running && <span className="absolute inset-0 rounded-full animate-ping bg-accent-green opacity-50" />}
                </span>
                <span className="flex-1 text-ink-body truncate">{a.name}</span>
                <span className="font-mono text-ink-muted text-[10px]">{(a.success*100).toFixed(1)}%</span>
                <span className="font-mono text-ink-faint text-[10px] tabular-nums">p95 {(a.p95_ms/1000).toFixed(1)}s</span>
              </li>
            ))}
          </ul>
          <button
            onClick={() => navigate("#/agents")}
            className="mt-4 w-full text-[12px] font-mono text-accent-brand-glow hover:underline text-left"
          >
            View agent runtime →
          </button>
        </section>
      </div>

      {/* Policy updates + Compliance pulse */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <section className="xl:col-span-6 bg-surface-raised border border-surface-border rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <I.BookOpen size={15} className="text-ink-muted" />
              <h2 className="font-semibold tracking-tight text-ink-primary text-[15px]">Policy updates</h2>
            </div>
            <span className="text-[10px] font-mono text-ink-muted">last 30d</span>
          </div>
          <ul className="space-y-2.5">
            {extra.POLICY_UPDATES.map((u) => (
              <li key={u.policy_id} className="flex items-start gap-3 py-2 px-2 -mx-2 rounded hover:bg-surface-raised-hi transition-colors">
                <PayerChip id={u.payer} small />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-ink-muted">{u.policy_id}</span>
                    <span className="text-[10px] font-mono text-accent-amber">
                      {u.from} <span className="text-ink-faint mx-0.5">→</span> {u.to}
                    </span>
                  </div>
                  <div className="text-[12px] text-ink-body mt-0.5 truncate">{u.title}</div>
                  <div className="text-[10px] font-mono text-ink-faint mt-0.5">
                    {extra.timeAgo(u.changed_at)} · <span className="text-accent-amber">{u.impacted_cases} in-flight cases impacted</span>
                  </div>
                </div>
                <button
                  onClick={() => navigate(`#/policies/${u.policy_id}/diff`)}
                  className="text-[11px] font-mono text-accent-brand-glow hover:underline shrink-0"
                >
                  Diff →
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={() => navigate("#/policies")}
            className="mt-3 w-full text-[12px] font-mono text-accent-brand-glow hover:underline text-left"
          >
            View Policy Library →
          </button>
        </section>

        <section className="xl:col-span-6 bg-surface-raised border border-surface-border rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <I.ShieldCheck size={15} className="text-ink-muted" />
              <h2 className="font-semibold tracking-tight text-ink-primary text-[15px]">Compliance pulse</h2>
            </div>
            <span className="text-[10px] font-mono text-ink-muted">live</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <PulseTile
              label="CMS-0057-F mandate"
              value={`${extra.COMPLIANCE_PULSE.cms_0057_days}d`}
              caption="until 2027 deadline"
              dot="amber"
            />
            <PulseTile
              label="PHI redactions (24h)"
              value={extra.COMPLIANCE_PULSE.phi_redactions_24h}
              caption="zero leaks"
              dot="green"
            />
            <PulseTile
              label="Audit completeness"
              value={`${Math.round(extra.COMPLIANCE_PULSE.audit_completeness*100)}%`}
              caption="every decision cited"
              dot="green"
            />
          </div>
          <div className="mt-4 p-3 rounded-lg bg-surface-bg border border-surface-border text-[12px] text-ink-body leading-relaxed">
            <span className="font-mono text-[10px] text-ink-muted uppercase tracking-widest mr-1.5">Cite</span>
            Every ClinCase decision is traceable to its FHIR resource IDs and policy section pointers. Generate a quarterly evidence pack on demand.
          </div>
          <button
            onClick={() => navigate("#/compliance")}
            className="mt-3 w-full text-[12px] font-mono text-accent-brand-glow hover:underline text-left"
          >
            Open Compliance Reports →
          </button>
        </section>
      </div>

      {/* Demo cases — kept from prior, smaller */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <I.Sparkles size={15} className="text-accent-brand-glow motion-safe:animate-glow-pulse" />
          <h2 className="font-semibold tracking-tight text-ink-primary text-[15px]">Live demo fixtures</h2>
          <span className="ml-auto text-[10px] font-mono text-ink-muted">3 fixtures · click to run</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {fixtures.map((fx, fxi) => {
            const verdictMeta = VERDICT_META[fx.expected_verdict];
            const isCreating = creating === fx.name;
            return (
              <window.Reveal key={fx.name} delay={fxi * 90}>
                <window.TiltCard intensity={9} className="rounded-xl">
                  <button
                    onClick={() => handleCreate(fx)}
                    disabled={isCreating}
                    className="group relative w-full h-full text-left bg-surface-bg border border-surface-border rounded-xl p-4 hover:border-accent-brand/60 hover:bg-surface-raised-hi transition-all duration-200 disabled:opacity-60 disabled:cursor-wait focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand overflow-hidden"
                    data-screen-label={`fixture-${fx.expected_verdict.toLowerCase()}`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Pill tone={verdictMeta.tone}>Expected · {fx.expected_verdict}</Pill>
                      <I.ArrowRight size={13} className="ml-auto text-ink-faint group-hover:text-accent-brand-glow group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <h3 className="font-semibold tracking-tight text-ink-primary text-[14px] leading-snug">{fx.title}</h3>
                    <p className="text-[12px] text-ink-body mt-1 leading-relaxed line-clamp-2">{fx.description}</p>
                    <div className="text-[10px] font-mono text-ink-muted mt-2.5 truncate">
                      {fx.payer.toUpperCase()} · {fx.treatment} ({fx.j_code})
                    </div>
                    {isCreating && (
                      <div className="absolute right-3 bottom-3">
                        <I.Loader size={13} className="animate-spin text-accent-brand-glow" />
                      </div>
                    )}
                  </button>
                </window.TiltCard>
              </window.Reveal>
            );
          })}
        </div>
      </section>
    </div>
  );
}

// ---------- Helpers ----------
function TrustChip({ dot, children }) {
  const dotColor = dot === "cyan" ? "bg-accent-cyan" : dot === "brand" ? "bg-accent-brand-glow" : dot === "green" ? "bg-accent-green" : "bg-ink-muted";
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-ink-body bg-surface-bg border border-surface-border rounded-md">
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {children}
    </span>
  );
}

function KPITile({ label, value, trend, accent }) {
  const valColor = accent === "cyan" ? "text-accent-cyan" : "text-ink-primary";

  // If value is a number, animate; if it's a formatted string, parse digits and animate the leading number portion.
  const renderValue = () => {
    if (typeof value === "number") {
      return <window.NumberRoll value={value} duration={1200} />;
    }
    // try to extract leading number for "$2.45" or "94%" or "12m 30s"
    const m = String(value).match(/^([^\d-]*)(-?[\d,.]+)(.*)$/);
    if (!m) return value;
    const prefix = m[1], num = parseFloat(m[2].replace(/,/g, "")), suffix = m[3];
    if (Number.isNaN(num)) return value;
    const decimals = (m[2].split(".")[1] || "").length;
    const fmt = (v) => {
      const fixed = v.toFixed(decimals);
      // re-add comma grouping for ints
      if (decimals === 0) return Number(fixed).toLocaleString();
      return fixed;
    };
    return <>{prefix}<window.NumberRoll value={num} duration={1100} format={fmt} />{suffix}</>;
  };

  return (
    <window.TiltCard intensity={5} className="bg-surface-raised border border-surface-border rounded-2xl p-5 min-h-[120px] hover:border-surface-border-hi transition-colors">
      <div className="text-[10px] font-mono text-ink-muted uppercase tracking-widest">{label}</div>
      <div className={`display-tight font-bold text-[34px] leading-none mt-2 tabular-nums ${valColor} ${accent === "cyan" ? "font-mono" : ""}`}>
        {renderValue()}
      </div>
      <div className="mt-3">{trend}</div>
    </window.TiltCard>
  );
}

function Sparkline({ values, color }) {
  const w = 110, h = 28, pad = 2;
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const xs = values.map((_, i) => pad + (i * (w - 2*pad)) / (values.length - 1));
  const ys = values.map((v) => h - pad - ((v - min) / range) * (h - 2*pad));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
  const last = { x: xs[xs.length-1], y: ys[ys.length-1] };
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last.x} cy={last.y} r="2.5" fill={color} />
    </svg>
  );
}

function PulseTile({ label, value, caption, dot }) {
  const dotColor = dot === "amber" ? "bg-accent-amber" : dot === "rose" ? "bg-accent-rose" : "bg-accent-green";
  return (
    <div className="bg-surface-bg border border-surface-border rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        <span className="text-[10px] font-mono text-ink-muted uppercase tracking-widest truncate">{label}</span>
      </div>
      <div className="text-[20px] font-bold tabular-nums text-ink-primary leading-none">{value}</div>
      <div className="text-[10px] font-mono text-ink-faint mt-1">{caption}</div>
    </div>
  );
}

function PayerChip({ id, small }) {
  const extra = window.CLINCASE_EXTRA;
  const p = (extra.PAYERS || []).find((x) => x.id === id);
  if (!p) return <span className="text-[10px] font-mono text-ink-muted">{id}</span>;
  const sz = small ? "w-6 h-6 text-[9px]" : "w-7 h-7 text-[10px]";
  return (
    <div className="flex items-center gap-2 shrink-0" title={p.name}>
      <div
        className={`${sz} rounded grid place-items-center font-mono font-semibold text-white shrink-0`}
        style={{ background: p.color }}
      >{p.tinyLogo}</div>
      {!small && <span className="text-[12px] text-ink-body truncate">{p.name}</span>}
    </div>
  );
}

const VERDICT_PILL = {
  APPROVE: { tone: "emerald", label: "APPROVE" },
  DENY:    { tone: "rose",    label: "DENY" },
  REFER:   { tone: "amber",   label: "REFER" },
  pending: { tone: "slate",   label: "PENDING" },
  running: { tone: "brand",   label: "RUNNING" },
};

function CaseRow({ c, navigate, idx }) {
  const status = c.verdict || (c.status === "running" ? "running" : "pending");
  const meta = VERDICT_PILL[status];
  const conf = c.confidence;
  const extra = window.CLINCASE_EXTRA;
  return (
    <button
      onClick={() => navigate(`#/cases/${c.id}`)}
      className="group w-full flex items-center gap-3 px-4 sm:px-5 py-3 hover:bg-surface-raised-hi transition-colors text-left motion-safe:animate-fade-in"
      style={{ animationDelay: `${idx * 30}ms` }}
    >
      {/* Verdict pill — fixed width */}
      <div className="flex items-center gap-1.5 w-[88px] sm:w-[100px] shrink-0">
        <Pill tone={meta.tone} className={c.status === "running" ? "animate-pulse-soft" : ""}>{meta.label}</Pill>
        {c.appealed && !c.overturned && <span className="text-[9px] font-mono text-accent-amber" title="Appealed">↩</span>}
        {c.overturned && <span className="text-[9px] font-mono px-1 rounded bg-accent-green/20 text-accent-green" title="Overturned">+1</span>}
      </div>

      {/* Patient + treatment — flexes */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[12px] font-mono text-ink-muted shrink-0">{c.initials}</span>
          <span className="text-[13px] text-ink-primary truncate">{c.treatment}</span>
          <span className="text-[10px] font-mono text-ink-faint shrink-0 hidden md:inline">{c.j_code}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] font-mono text-ink-faint truncate">{c.id}</span>
          {/* Mobile-only inline meta */}
          <span className="sm:hidden text-[10px] font-mono text-ink-faint shrink-0">· {extra.timeAgo(c.submitted_at)}</span>
        </div>
      </div>

      {/* Payer chip — hidden on small */}
      <div className="hidden sm:flex w-[112px] shrink-0 justify-start">
        <PayerChip id={c.payer} small />
      </div>

      {/* Confidence — hidden on small */}
      <div className="hidden md:block w-[72px] shrink-0 text-right">
        {conf != null ? (
          <div>
            <div className="text-[11px] font-mono text-ink-body tabular-nums">{Math.round(conf*100)}%</div>
            <div className="w-full h-1 rounded-full bg-surface-border overflow-hidden mt-0.5">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${conf*100}%`,
                  background: c.verdict === "APPROVE" ? "var(--accent-green)" : c.verdict === "DENY" ? "var(--accent-rose)" : "var(--accent-amber)",
                }}
              />
            </div>
          </div>
        ) : (
          <span className="text-[10px] font-mono text-ink-faint">—</span>
        )}
      </div>

      {/* Time — hidden on mobile (shown inline above instead) */}
      <div className="hidden sm:block w-[80px] shrink-0 text-[10px] font-mono text-ink-muted text-right" title={new Date(c.submitted_at).toISOString()}>
        {extra.timeAgo(c.submitted_at)}
      </div>

      <I.ChevronRight size={14} className="text-ink-faint group-hover:text-accent-brand-glow group-hover:translate-x-0.5 transition-all shrink-0" />
    </button>
  );
}

window.DashboardPage = DashboardPage;
window.CaseRow = CaseRow;
window.PayerChip = PayerChip;
window.VERDICT_PILL_DASH = VERDICT_PILL;
