// First-time onboarding tour — full-bleed overlay with steps
const { useState: useTState, useEffect: useTEffect, useRef: useTRef } = React;

function OnboardingTour({ open, onClose, navigate }) {
  const [step, setStep] = useTState(0);
  const STEPS = [
    {
      kind: "welcome",
      eyebrow: "Welcome to ClinCase",
      title: "Prior authorization, decided in minutes.",
      body: "A 5-agent clinical AI platform that reads FHIR data + payer policy and returns an auditable verdict with citations — instead of weeks of fax-fight.",
      stat: { value: "94%", label: "of physicians say PA delays care" },
      stat2: { value: "6.4 min", label: "avg ClinCase decision" },
    },
    {
      kind: "feature",
      eyebrow: "Step 1 · The Workspace",
      title: "Every case starts in one place.",
      body: "The Dashboard shows your queue, today's KPIs, agent health, and the policies that just changed. Side-nav gets you anywhere in two keystrokes.",
      bullets: [
        ["LayoutDashboard", "Dashboard — KPI row + live queue"],
        ["FolderOpen", "Cases — every PA your team owns"],
        ["BookOpen", "Policies — payer rule diffs"],
        ["BarChart3", "Cohorts — outcomes & approval rates"],
      ],
      shortcut: ["⌘", "K"],
      shortcutDesc: "Open command palette anywhere",
    },
    {
      kind: "feature",
      eyebrow: "Step 2 · The 5-Agent DAG",
      title: "Five specialists, one decision.",
      body: "Clinical Extractor reads the FHIR bundle. Policy Retriever pulls the right MCG/InterQual section. Reasoner aligns evidence to criteria. Validator checks confidence. If denied, Appeals Drafter writes an NCCN-grounded letter — automatically.",
      bullets: [
        ["Stethoscope", "Clinical Extractor — FHIR R4 → typed snapshot"],
        ["BookOpen", "Policy Retriever — payer rules + LCDs"],
        ["GitBranch", "Reasoner — evidence ↔ criteria alignment"],
        ["ShieldCheck", "Validator — confidence + guardrails"],
        ["Mail", "Appeals Drafter — NCCN-grounded rebuttal"],
      ],
    },
    {
      kind: "feature",
      eyebrow: "Step 3 · The Verdict",
      title: "Citations or it didn't happen.",
      body: "Every Approve / Deny / Refer shows the exact clinical evidence and policy clauses it relied on. Click any citation to flash-highlight the source. Auditors love it. Reviewers trust it.",
      bullets: [
        ["CheckCircle", "APPROVE — meets criteria, payer-ready"],
        ["AlertCircle", "REFER — needs human review (low conf or doc-gap)"],
        ["XCircle", "DENY — with auto-drafted NCCN appeal letter"],
      ],
    },
    {
      kind: "feature",
      eyebrow: "Step 4 · Compliance built in",
      title: "CMS-0057-F. SOC2. HIPAA. PHI redaction.",
      body: "Bedrock Guardrails redact PHI before any LLM call. Every decision is an immutable audit log line. CMS-0057-F deadlines (Jan 2026 / Jan 2027) — we ship the API today.",
      bullets: [
        ["ShieldCheck", "HIPAA · BAA-ready · PHI redacted at ingress"],
        ["FileText", "Immutable audit log per case"],
        ["Database", "FHIR R4 · USCDI v3 native"],
        ["Cpu", "Bedrock-ready · Claude Sonnet 4.6"],
      ],
    },
    {
      kind: "cta",
      eyebrow: "You're ready",
      title: "Try a live case.",
      body: "Three pre-loaded scenarios show APPROVE, REFER, and DENY paths end-to-end. Click any one to watch all five agents run in real time.",
      ctas: [
        { label: "Try APPROVE — HER2+ Trastuzumab", to: "#/cases/case_8f4ad9c2", tone: "emerald" },
        { label: "Try REFER — Missing LVEF", to: "#/cases/case_2a91bd64", tone: "amber" },
        { label: "Try DENY — Biomarker mismatch", to: "#/cases/case_d4f30781", tone: "rose" },
      ],
    },
  ];
  const total = STEPS.length;
  const cur = STEPS[step];

  useTEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") {
        if (step < total - 1) setStep((s) => s + 1);
        else onClose();
      } else if (e.key === "ArrowLeft") {
        if (step > 0) setStep((s) => s - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, step, total, onClose]);

  if (!open) return null;
  const I = window.I;

  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-[#0a1f44]/85 backdrop-blur-md p-3 sm:p-6 motion-safe:animate-fade-in"
      onClick={onClose}
    >
      {/* glow */}
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full" style={{ background: "radial-gradient(circle, rgba(0,163,224,0.20) 0%, transparent 60%)", filter: "blur(60px)" }} />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] rounded-full" style={{ background: "radial-gradient(circle, rgba(0,181,184,0.18) 0%, transparent 60%)", filter: "blur(60px)" }} />
      </div>

      <div
        className="relative w-full max-w-3xl max-h-[92vh] overflow-y-auto rounded-2xl sm:rounded-3xl bg-surface-raised border border-surface-border-hi"
        onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: "0 0 0 1px rgba(0,51,161,0.30), 0 40px 80px -16px rgba(10,31,68,0.7)" }}
      >
        {/* progress bar */}
        <div className="absolute top-0 inset-x-0 h-1 bg-surface-raised-hi">
          <div
            className="h-full transition-all duration-500"
            style={{
              width: `${((step + 1) / total) * 100}%`,
              background: "linear-gradient(90deg, #0033a1 0%, #00a3e0 50%, #00b5b8 100%)",
            }}
          />
        </div>

        {/* close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-8 h-8 rounded-md grid place-items-center hover:bg-surface-raised-hi text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          aria-label="Close tour"
        >
          <I.X size={16} />
        </button>

        <div className="p-6 sm:p-10 md:p-12">
          <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-accent-cyan">{cur.eyebrow}</div>
          <h2 className="display-tight font-bold text-ink-primary text-[24px] sm:text-[32px] md:text-[40px] leading-[1.05] mt-3 max-w-[24ch]">{cur.title}</h2>
          <p className="text-[14px] sm:text-[15px] text-ink-body leading-relaxed mt-3 sm:mt-4 max-w-[60ch]">{cur.body}</p>

          {cur.kind === "welcome" && (
            <div className="mt-7 grid grid-cols-2 gap-3 max-w-md">
              <StatCard value={cur.stat.value} label={cur.stat.label} tone="muted" />
              <StatCard value={cur.stat2.value} label={cur.stat2.label} tone="brand" />
            </div>
          )}

          {cur.bullets && (
            <ul className="mt-7 grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-2xl">
              {cur.bullets.map((b, i) => {
                const Ico = I[b[0]] || I.Activity;
                return (
                  <li key={i} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-surface-bg border border-surface-border">
                    <span className="w-7 h-7 rounded-md grid place-items-center bg-accent-brand/10 text-accent-brand-glow border border-accent-brand/25 shrink-0">
                      <Ico size={13} />
                    </span>
                    <span className="text-[13px] text-ink-body leading-snug">{b[1]}</span>
                  </li>
                );
              })}
            </ul>
          )}

          {cur.shortcut && (
            <div className="mt-6 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-surface-border bg-surface-bg text-[12px] text-ink-body">
              <span className="text-ink-muted">Try it:</span>
              {cur.shortcut.map((k, i) => (
                <kbd key={i} className="px-1.5 py-0.5 text-[10px] font-mono bg-surface-raised-hi border border-surface-border rounded text-ink-primary">{k}</kbd>
              ))}
              <span className="text-ink-muted">— {cur.shortcutDesc}</span>
            </div>
          )}

          {cur.ctas && (
            <div className="mt-7 grid grid-cols-1 gap-2.5 max-w-2xl">
              {cur.ctas.map((c) => {
                const tone =
                  c.tone === "emerald" ? { fg: "text-accent-green", bg: "bg-emerald-500/[0.06]", bd: "border-emerald-500/30" }
                  : c.tone === "amber" ? { fg: "text-accent-amber", bg: "bg-amber-500/[0.06]", bd: "border-amber-500/30" }
                  : { fg: "text-accent-red", bg: "bg-rose-500/[0.06]", bd: "border-rose-500/30" };
                return (
                  <button
                    key={c.to}
                    onClick={() => { onClose(); navigate(c.to); }}
                    className={`group flex items-center gap-3 text-left px-4 py-3 rounded-xl border ${tone.bd} ${tone.bg} hover:border-current ${tone.fg} transition-colors`}
                  >
                    <I.Play size={14} className={tone.fg} />
                    <span className="flex-1 text-[14px] font-medium text-ink-primary">{c.label}</span>
                    <I.ArrowRight size={15} className={`${tone.fg} group-hover:translate-x-0.5 transition-transform`} />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* footer / nav */}
        <div className="px-6 sm:px-10 md:px-12 py-4 border-t border-surface-border bg-surface-raised-hi/40 flex items-center justify-between gap-2 sm:gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            {STEPS.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                aria-label={`Go to step ${i + 1}`}
                className={`h-1.5 rounded-full transition-all ${i === step ? "w-8 bg-accent-brand-glow" : i < step ? "w-1.5 bg-accent-brand/60" : "w-1.5 bg-surface-border-hi"}`}
              />
            ))}
            <span className="ml-2 text-[11px] font-mono text-ink-muted">{step + 1} / {total}</span>
          </div>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => setStep((s) => s - 1)}
                className="h-9 px-3 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:bg-surface-raised-hi"
              >
                Back
              </button>
            )}
            <button
              onClick={onClose}
              className="h-9 px-3 text-[12px] text-ink-muted hover:text-ink-body"
            >
              Skip
            </button>
            <button
              onClick={() => step < total - 1 ? setStep((s) => s + 1) : onClose()}
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md text-white text-[12.5px] font-medium"
              style={{
                background: "linear-gradient(180deg, #2563d9 0%, #0033a1 100%)",
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.18), 0 0 0 1px rgba(0,51,161,0.55), 0 8px 20px -8px rgba(0,51,161,0.55)",
              }}
            >
              {step < total - 1 ? "Continue" : "Get started"}
              <I.ArrowRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ value, label, tone = "muted" }) {
  const cls = tone === "brand"
    ? "border-accent-brand/30 bg-accent-brand/[0.06]"
    : "border-surface-border bg-surface-bg";
  return (
    <div className={`rounded-xl border ${cls} p-3.5`}>
      <div className="display-tight font-bold text-[24px] tabular-nums leading-none text-ink-primary">{value}</div>
      <div className="text-[11px] text-ink-muted mt-1.5 leading-tight">{label}</div>
    </div>
  );
}

window.OnboardingTour = OnboardingTour;
