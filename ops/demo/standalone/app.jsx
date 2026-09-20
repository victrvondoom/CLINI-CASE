// Home (bento) + Case Detail + App routing + Tweaks (dark aurora theme)
const { useState: useS, useEffect: useE, useRef: useR, useMemo: useM, useCallback: useCb } = React;

// Pricing for Sonnet 4.6
const PRICE_IN = 3 / 1_000_000;
const PRICE_OUT = 15 / 1_000_000;

// =============================================================
// HOME (bento grid)
// =============================================================
function HomePage({ navigate, fixtures, onCreate }) {
  const [creating, setCreating] = useS(null);
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
    <div className="space-y-6">
      {/* Bento — row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Cell A — Hero */}
        <section className="lg:col-span-7 relative bg-surface-raised border border-surface-border rounded-2xl p-8 sm:p-10 overflow-hidden min-h-[340px]">
          <Eyebrow className="text-accent-brand-glow">Healthcare · Prior Authorisation Automation</Eyebrow>
          <h1 className="display-tight font-bold leading-[1.02] mt-4 text-ink-primary text-[44px] sm:text-[58px] lg:text-[64px]">
            {headlineWords.map((w, i) => {
              const isAccent = w.replace(/[.,]/g, "").toLowerCase() === "minutes";
              return (
                <React.Fragment key={i}>
                  <span
                    className={`inline-block motion-safe:animate-word-up ${isAccent ? "gradient-text" : ""}`}
                    style={{ animationDelay: `${80 + i * 60}ms` }}
                  >
                    {w}
                  </span>
                  {i < headlineWords.length - 1 && " "}
                </React.Fragment>
              );
            })}
          </h1>
          <p className="text-ink-body leading-relaxed mt-5 max-w-[58ch] text-[15px]">
            Provider-side, FHIR-native copilot. Five agents read clinical evidence and payer policy, then ship a verdict with a citation chain. On denial, an NCCN-grounded appeal letter is drafted automatically.
          </p>
          <div className="mt-6 flex items-center gap-3 text-[11px] font-mono text-ink-muted flex-wrap">
            <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" /> 5-agent LangGraph DAG</span>
            <span className="text-ink-faint">·</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-accent-brand-glow" /> Claude Sonnet 4.6</span>
            <span className="text-ink-faint">·</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-accent-green" /> ~$0.09 / case</span>
          </div>
        </section>

        {/* Cell B — Live demo loop */}
        <section className="lg:col-span-5 relative bg-surface-raised border border-surface-border rounded-2xl p-6 overflow-hidden min-h-[340px] flex flex-col">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-green" />
              </span>
              <Eyebrow>Live · Agent Loop</Eyebrow>
            </div>
            <span className="text-[10px] font-mono text-ink-faint">FHIR R4 · NCCN BINV-N</span>
          </div>
          <div className="flex-1 grid place-items-center">
            <LiveAgentLoop />
          </div>
          <p className="text-[12px] text-ink-muted leading-relaxed mt-3">
            Five agents working on real FHIR data right now. Click any case below to step through the trace.
          </p>
        </section>
      </div>

      {/* Bento — row 2 (stat tiles + trust) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <StatTile span="lg:col-span-3" value="94%" target={94} suffix="%" duration={1200} delay={120} label="of physicians say PA delays care" cite="AMA · 2024 PA survey" />
        <StatTile span="lg:col-span-3" value="80.7%" target={80.7} decimals={1} suffix="%" duration={1400} delay={260} label="of appealed MA denials are overturned" cite="KFF · 2023" />
        <StatTile span="lg:col-span-3" value="$30B+" target={30} prefix="$" suffix="B+" duration={1600} delay={400} label="annual US PA admin waste" cite="JAMA · 2022" />
        <section className="lg:col-span-3 bg-surface-raised border border-surface-border rounded-2xl p-5">
          <Eyebrow>Compliance Posture</Eyebrow>
          <ul className="mt-3 space-y-2 text-[13px] text-ink-body">
            {[
              { l: "HIPAA · PHI redaction", k: "Bedrock Guardrails" },
              { l: "FHIR R4 · USCDI v3", k: "native ingest" },
              { l: "Bedrock-ready", k: "Sonnet 4.6" },
              { l: "CMS-0057-F", k: "2026 / 2027" },
            ].map((r) => (
              <li key={r.l} className="flex items-center gap-2.5">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan shrink-0" />
                <span className="flex-1">{r.l}</span>
                <span className="font-mono text-[10px] text-ink-muted">{r.k}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* Bento — row 3 (cases) */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <I.Sparkles size={16} className="text-accent-brand-glow" />
          <h2 className="font-semibold tracking-tight text-ink-primary">Live Demo Cases</h2>
          <span className="ml-auto text-[11px] font-mono text-ink-muted">3 fixtures · click to run</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {fixtures.map((fx) => {
            const verdictMeta = VERDICT_META[fx.expected_verdict];
            const isCreating = creating === fx.name;
            return (
              <button
                key={fx.name}
                onClick={() => handleCreate(fx)}
                disabled={isCreating}
                className="group relative text-left bg-surface-bg border border-surface-border rounded-xl p-5 hover:border-accent-brand/60 hover:bg-surface-raised-hi transition-all duration-200 disabled:opacity-60 disabled:cursor-wait focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg"
                data-screen-label={`fixture-${fx.expected_verdict.toLowerCase()}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Pill tone={verdictMeta.tone}>Expected · {fx.expected_verdict}</Pill>
                  <I.ArrowRight size={14} className="ml-auto text-ink-faint group-hover:text-accent-brand-glow group-hover:translate-x-0.5 transition-all" />
                </div>
                <h3 className="font-semibold tracking-tight text-ink-primary leading-snug">{fx.title}</h3>
                <p className="text-[13px] text-ink-body mt-1.5 leading-relaxed">{fx.description}</p>
                <div className="text-[11px] font-mono text-ink-muted mt-3 truncate">
                  {fx.payer.toUpperCase()} · {fx.treatment} ({fx.j_code}) · Patient {fx.initials}
                </div>
                {isCreating && (
                  <div className="absolute right-4 bottom-4">
                    <I.Loader size={14} className="animate-spin text-accent-brand-glow" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function StatTile({ span, value, target, prefix = "", suffix = "", decimals = 0, duration = 1200, delay = 0, label, cite }) {
  // Animated count-up on first paint. Falls back to static `value` if reduced motion or no target.
  const [n, setN] = useS(target ?? 0);
  const startedRef = useR(false);
  useE(() => {
    if (target == null) return;
    if (startedRef.current) return;
    startedRef.current = true;
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) { setN(target); return; }
    setN(0);
    let raf;
    const startAt = performance.now() + delay;
    const tick = (t) => {
      const elapsed = t - startAt;
      if (elapsed < 0) { raf = requestAnimationFrame(tick); return; }
      const k = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - k, 4); // easeOutQuart
      setN(target * eased);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, delay]);

  const formatted = target != null
    ? `${prefix}${n.toFixed(decimals)}${suffix}`
    : value;

  return (
    <div className={`${span} bg-surface-raised border border-surface-border rounded-2xl p-5`}>
      <div className="display-tight font-bold text-[40px] leading-none tabular-nums text-ink-primary">{formatted}</div>
      <div className="text-[13px] text-ink-body mt-2 leading-tight">{label}</div>
      <div className="text-[10px] font-mono text-ink-muted mt-3">{cite}</div>
    </div>
  );
}

// 3-second autoplay loop showing one agent transitioning pending → running → done
function LiveAgentLoop() {
  const [phase, setPhase] = useS(0); // 0 pending, 1 running, 2 done
  useE(() => {
    const seq = [
      { p: 1, after: 800 },  // pending → running (after a beat)
      { p: 2, after: 2200 }, // running → done
      { p: 0, after: 1100 }, // done → pending (loop)
    ];
    let i = 0;
    let t;
    const step = () => {
      t = setTimeout(() => {
        setPhase(seq[i].p);
        i = (i + 1) % seq.length;
        step();
      }, seq[(i - 1 + seq.length) % seq.length].after);
    };
    step();
    return () => clearTimeout(t);
  }, []);

  const cfg = [
    { tag: "PENDING",    pillTone: "slate", icon: <div className="w-4 h-4 rounded-full border border-dashed border-ink-faint" />, border: "border-surface-border" },
    { tag: "THINKING…",  pillTone: "brand", icon: <I.Loader size={16} className="text-accent-brand-glow animate-spin" />, border: "border-accent-brand/50" },
    { tag: "COMPLETED",  pillTone: "emerald", icon: <I.CheckCircle size={16} className="text-accent-green" />, border: "border-emerald-500/40" },
  ][phase];

  const tokenIn = phase === 2 ? "4,820" : "—";
  const tokenOut = phase === 2 ? "612" : "—";
  const lat = phase === 2 ? "2.14s" : phase === 1 ? "…" : "—";

  return (
    <div className={`w-full bg-surface-bg border-2 ${cfg.border} rounded-xl p-4 transition-colors duration-300`}>
      <div className="flex items-center gap-2.5">
        <div className="shrink-0">{cfg.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[10px] font-mono text-ink-faint">01</span>
              <span className="font-semibold text-[13px] text-ink-primary truncate">Clinical Extractor</span>
            </div>
            <Pill tone={cfg.pillTone} className={phase === 1 ? "animate-pulse-soft" : ""}>{cfg.tag}</Pill>
          </div>
          <p className="text-[11px] text-ink-muted mt-1 leading-snug">FHIR R4 bundle → typed ClinicalSnapshot</p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 text-[11px] font-mono text-ink-muted flex-wrap">
        <span className="inline-flex items-center gap-1"><I.Clock size={11} />{lat}</span>
        <span className="inline-flex items-center gap-1"><I.Cpu size={11} />sonnet-4-6</span>
        <span className="tabular-nums">
          <span className={phase === 2 ? "text-ink-body" : "text-ink-faint"}>{tokenIn}</span>
          <span className="text-ink-faint"> in / </span>
          <span className={phase === 2 ? "text-ink-body" : "text-ink-faint"}>{tokenOut}</span>
          <span className="text-ink-faint"> out</span>
        </span>
      </div>
    </div>
  );
}

// =============================================================
// CASE DETAIL
// =============================================================
function CaseDetailPage({ caseId, fixture, navigate, tweaks, onPHIRequest }) {
  const data = window.CLINCASE_DATA;
  const fixtureName = fixture?.name || "her2_positive_approve";
  const snapshot = data.CLINICAL_SNAPSHOTS[fixtureName];
  const decisionTarget = data.DECISIONS[fixtureName];

  const [events, setEvents] = useS([]);
  const [running, setRunning] = useS(false);
  const [done, setDone] = useS(false);
  const [phiVisible, setPhiVisible] = useS(false);
  const [costRunning, setCostRunning] = useS(0);
  const stopRef = useR(null);
  const startedAtRef = useR(0);
  const [wallclock, setWallclock] = useS(0);

  const verdict = decisionTarget.verdict;
  const totalAgents = data.AGENT_SPECS.filter((a) => verdict === "DENY" || a.key !== "appeals_drafter").length;
  const finishedCount = events.filter((e) => e.type === "agent_finished").length;

  useE(() => {
    let totalIn = 0, totalOut = 0;
    events.forEach((e) => {
      if (e.type === "agent_finished") { totalIn += e.input_tokens; totalOut += e.output_tokens; }
    });
    setCostRunning(totalIn * PRICE_IN + totalOut * PRICE_OUT);
  }, [events]);

  useE(() => {
    if (!running) return;
    const id = setInterval(() => setWallclock(Date.now() - startedAtRef.current), 100);
    return () => clearInterval(id);
  }, [running]);

  const startRun = useCb(() => {
    if (running) return;
    setEvents([]); setDone(false); setRunning(true); setWallclock(0);
    startedAtRef.current = Date.now();
    if (tweaks.show_phi_banner) {
      setPhiVisible(true);
      setTimeout(() => setPhiVisible(false), 8000);
    }
    stopRef.current = runSimulatedStream({
      fixtureName,
      speedMs: tweaks.stream_speed_ms,
      onEvent: (e) => setEvents((prev) => [...prev, e]),
      onDone: () => {
        setRunning(false); setDone(true);
        setWallclock(Date.now() - startedAtRef.current);
      },
    });
  }, [running, fixtureName, tweaks.stream_speed_ms, tweaks.show_phi_banner]);

  useE(() => {
    onPHIRequest((ms) => {
      setPhiVisible(true);
      setTimeout(() => setPhiVisible(false), ms || 8000);
    });
  }, [onPHIRequest]);

  useE(() => {
    const onKey = (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
      if (e.key.toLowerCase() === "r" && !running) {
        e.preventDefault();
        startRun();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [startRun, running]);

  useE(() => () => stopRef.current && stopRef.current(), []);

  const showResults = done;
  const decision = showResults ? decisionTarget : null;
  const showAppeal = showResults && verdict === "DENY";
  const totalCost = costRunning;

  return (
    <div className="space-y-5" data-screen-label={`case-${verdict.toLowerCase()}`}>
      {/* Top row */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => navigate("#/")}
          className="inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand rounded px-1"
        >
          <I.ArrowLeft size={14} /> All cases
        </button>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-ink-muted">case</span>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-raised border border-surface-border text-ink-body">{caseId}</span>
        </div>
      </div>

      <PHIBanner visible={phiVisible} onClose={() => setPhiVisible(false)} />

      {/* Case header */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-[11px] font-mono text-ink-muted mb-3">
          <button onClick={() => navigate("#/dashboard")} className="hover:text-ink-body">Workspace</button>
          <I.ChevronRight size={11} className="text-ink-faint" />
          <button onClick={() => navigate("#/cases")} className="hover:text-ink-body">Cases</button>
          <I.ChevronRight size={11} className="text-ink-faint" />
          <span className="text-ink-body">{caseId}</span>
        </nav>
        <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Eyebrow>Prior Authorisation Request</Eyebrow>
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold tracking-tight text-ink-primary">{fixture?.requested_treatment_full || "Trastuzumab"}</h1>
            <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised-hi text-ink-body border border-surface-border">{fixture?.j_code || "J9355"}</span>
          </div>
          <div className="text-sm text-ink-muted mt-1.5 flex items-center gap-1.5 flex-wrap">
            <span>Patient {fixture?.initials || "—"}</span>
            <span className="text-ink-faint">·</span>
            <span className="font-mono text-xs">{fixture?.payer_id || ""}</span>
            <span className="text-ink-faint">·</span>
            <span className="text-xs">
              status{" "}
              <span className={`font-mono ${done ? (verdict === "APPROVE" ? "text-accent-green" : verdict === "DENY" ? "text-accent-red" : "text-accent-amber") : "text-ink-body"}`}>
                {done ? verdict.toLowerCase() : running ? "running" : "pending"}
              </span>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <RiskMeter fixtureName={fixtureName} done={done} verdict={verdict} />
          {running && (
            <div className="text-right hidden sm:block">
              <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">elapsed</div>
              <div className="text-sm font-mono font-semibold tabular-nums text-ink-primary">{(wallclock / 1000).toFixed(1)}s</div>
            </div>
          )}
          <button
            onClick={() => navigate("#/compare")}
            className="hidden md:inline-flex items-center gap-1.5 h-9 px-3 rounded-md border border-surface-border bg-surface-bg text-[12px] text-ink-body hover:bg-surface-raised-hi"
            title="Compare across payers"
          >
            <I.Scale size={13} className="text-ink-muted" /> Compare
          </button>
          <button
            onClick={startRun}
            disabled={running}
            className="inline-flex items-center gap-2 text-white rounded-lg px-5 py-2.5 font-medium text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg active:scale-[0.98]"
            style={{
              background: "linear-gradient(180deg, #8b6dff 0%, #6c47ff 100%)",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.18), 0 0 0 1px rgba(124,92,255,0.55), 0 8px 24px -8px rgba(124,92,255,0.7)",
            }}
          >
            {running ? <I.Loader size={16} className="animate-spin" /> : <I.Play size={14} />}
            {running ? "Running 5-agent graph…" : done ? "Re-run" : "Run ClinCase"}
            {!running && !done && <kbd className="hidden md:inline px-1.5 py-0.5 text-[10px] font-mono bg-white/15 rounded text-white/90">R</kbd>}
          </button>
        </div>
        </div>
      </section>

      {/* Two-column body */}
      <div className="grid lg:grid-cols-[1fr_420px] gap-5">
        <div className="space-y-5 min-w-0">
          {!running && !done && events.length === 0 && (
            <div className="rounded-2xl border border-dashed border-surface-border-hi bg-surface-raised/60 p-8 text-center">
              <div className="w-10 h-10 rounded-full bg-accent-brand/15 grid place-items-center mx-auto">
                <I.Sparkles size={18} className="text-accent-brand-glow" />
              </div>
              <p className="mt-4 text-sm text-ink-body max-w-md mx-auto leading-relaxed">
                Click <span className="font-semibold text-ink-primary">Run ClinCase</span> to start the 5-agent pipeline. You'll see the clinical snapshot, decision, and (if denied) appeal letter appear here.
              </p>
              <div className="mt-3 text-[11px] font-mono text-ink-muted">
                Press <kbd className="px-1 py-0.5 rounded bg-surface-raised border border-surface-border">R</kbd> · <kbd className="px-1 py-0.5 rounded bg-surface-raised border border-surface-border">⌘K</kbd>
              </div>
              <div className="mt-6 max-w-sm mx-auto text-left">
                <div className="text-[10px] font-mono text-ink-muted tracking-widest mb-2 text-center">PREVIEW · LIVE LOOP</div>
                <LiveAgentLoop />
              </div>
            </div>
          )}

          {(running || done) && finishedCount >= 1 && <ClinicalSummaryCard snapshot={snapshot} />}
          {showResults && <DecisionBadge decision={decision} hasAppeal={showAppeal} />}
          {showResults && <CitationChain citations={decision.citations} />}
          {showAppeal && <AppealLetterEditor draft={data.APPEAL_DRAFT} />}
          {(running || done) && (
            <AuditLogViewer
              events={events}
              fixtureName={fixtureName}
              defaultOpen={tweaks.audit_default_open && done}
              totalCost={totalCost}
              totalWallclock={wallclock}
            />
          )}
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start" style={{ height: "calc(100vh - 100px)" }}>
          <ReasoningTracePanel
            events={events}
            fixtureName={fixtureName}
            isRunning={running}
            costRunning={costRunning}
          />
        </aside>
      </div>
    </div>
  );
}

// =============================================================
// APP + Routing
// =============================================================
function App() {
  const [hash, navigate] = useHashRoute();
  const data = window.CLINCASE_DATA;
  const fixtures = data.FIXTURES;

  const [activeFixture, setActiveFixture] = useS(null);

  const tweakDefaults = /*EDITMODE-BEGIN*/{
    "stream_speed_ms": 1400,
    "demo_path": "her2_positive_approve",
    "show_phi_banner": true,
    "density": "comfortable",
    "brand_hue": 262,
    "audit_default_open": true
  }/*EDITMODE-END*/;
  const [tweaks, setTweak] = window.useTweaks(tweakDefaults);

  useE(() => { window.applyBrandHue(tweaks.brand_hue); }, [tweaks.brand_hue]);

  const [paletteOpen, setPaletteOpen] = useS(false);
  const [shortcutsOpen, setShortcutsOpen] = useS(false);
  const [tourOpen, setTourOpen] = useS(false);

  useE(() => {
    try {
      const seen = localStorage.getItem("clincase-tour-seen");
      if (!seen) setTourOpen(true);
    } catch (e) {}
  }, []);

  useE(() => {
    const onKey = (e) => {
      const tag = e.target && e.target.tagName;
      const inField = tag === "INPUT" || tag === "TEXTAREA" || (e.target && e.target.isContentEditable);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
        setShortcutsOpen(false);
      } else if (!inField && e.key === "?") {
        e.preventDefault();
        setShortcutsOpen((o) => !o);
      } else if (!inField && e.key.toLowerCase() === "n" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setPaletteOpen(true);
      } else if (!inField && e.key === "/") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const phiRef = useR(() => {});
  const onPHIRequest = useCb((cb) => { phiRef.current = cb; }, []);
  const triggerPHI = () => phiRef.current && phiRef.current(8000);

  // Match any case detail route — AUTH-xxx, case_xxx, or any other id —
  // EXCEPT the reserved /cases/bulk-import path. Round-15 fix: previous regex
  // only matched /^AUTH-/ prefix and silently fell back to Dashboard for
  // fixture case IDs like case_8f4ad9c2.
  const caseMatch = hash !== "#/cases/bulk-import" && hash.match(/^#\/cases\/(.+)$/);
  let view, isHome = false, route = hash;

  // Combine fixture cases + synthetic cases for navigation
  const allCases = [...(window.CLINCASE_EXTRA?.CASES || [])];

  if (caseMatch) {
    const caseId = caseMatch[1];
    const fixture = activeFixture && activeFixture.case_id === caseId
      ? activeFixture
      : fixtures.find((f) => f.case_id === caseId) || fixtures[0];
    view = (
      <CaseDetailPage
        caseId={caseId}
        fixture={fixture}
        navigate={navigate}
        tweaks={tweaks}
        onPHIRequest={onPHIRequest}
      />
    );
  } else if (hash === "#/cases") {
    view = <CasesPage navigate={navigate} allCases={allCases} />;
  } else if (hash === "#/cases/bulk-import") {
    view = <BulkImportPage navigate={navigate} />;
  } else if (hash === "#/intake") {
    view = <IntakeFlowPage navigate={navigate} />;
  } else if (hash === "#/about") {
    view = <AboutPage navigate={navigate} />;
  } else if (hash === "#/compare") {
    view = <ComparePage navigate={navigate} fixtures={fixtures} />;
  } else if (hash === "#/policies") {
    view = <PoliciesPage navigate={navigate} />;
  } else if (hash.startsWith("#/policies/") && hash.endsWith("/diff")) {
    const id = hash.slice("#/policies/".length, -"/diff".length);
    view = <PolicyDiffPage navigate={navigate} policyId={id} />;
  } else if (hash === "#/agents") {
    view = <AgentsPage navigate={navigate} />;
  } else if (hash === "#/cohorts") {
    view = <CohortsPage navigate={navigate} />;
  } else if (hash === "#/reviewer") {
    view = <ReviewerPage navigate={navigate} />;
  } else if (hash === "#/compliance") {
    view = <CompliancePage navigate={navigate} />;
  } else {
    isHome = true;
    view = (
      <DashboardPage
        navigate={navigate}
        fixtures={fixtures}
        onCreate={(fx) => setActiveFixture(fx)}
      />
    );
  }

  return (
    <AppShell
      density={tweaks.density}
      showAurora={isHome}
      route={route}
      navigate={navigate}
      onSearch={() => setPaletteOpen(true)}
      onOpenShortcuts={() => setShortcutsOpen(true)}
      onNewCase={() => setPaletteOpen(true)}
    >
      {view}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        fixtures={fixtures}
        navigate={(to) => { setPaletteOpen(false); navigate(to); }}
        onSelectFixture={(fx) => setActiveFixture(fx)}
      />
      {window.ShortcutsOverlay && <window.ShortcutsOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />}
      {window.OnboardingTour && <window.OnboardingTour open={tourOpen} onClose={() => { setTourOpen(false); try { localStorage.setItem("clincase-tour-seen", "1"); } catch (e) {} }} navigate={navigate} />}
      <TweaksUI tweaks={tweaks} setTweak={setTweak} onTriggerPHI={triggerPHI} onShowTour={() => setTourOpen(true)} />
    </AppShell>
  );
}

// =============================================================
// Stub page (for routes deferred from this wave)
// =============================================================
function StubPage({ title, eyebrow, icon: Ico, blurb, ctaLabel, navigate }) {
  return (
    <div className="space-y-5">
      <header>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="display-tight font-bold text-ink-primary text-[28px] mt-1.5">{title}</h1>
      </header>
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-10 text-center">
        <div className="w-12 h-12 rounded-xl bg-accent-brand/10 border border-accent-brand/30 grid place-items-center mx-auto">
          <Ico size={22} className="text-accent-brand-glow" />
        </div>
        <p className="mt-4 text-[14px] text-ink-body max-w-xl mx-auto leading-relaxed">{blurb}</p>
        {ctaLabel && (
          <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-md border border-dashed border-surface-border-hi text-[12px] font-mono text-ink-muted">
            <I.CloudUpload size={13} /> {ctaLabel}
          </div>
        )}
        <div className="mt-6">
          <button onClick={() => navigate("#/dashboard")} className="text-[12px] font-mono text-accent-brand-glow hover:underline">
            ← Back to dashboard
          </button>
        </div>
      </section>
    </div>
  );
}

// =============================================================
// Command Palette (dark glass)
// =============================================================
function CommandPalette({ open, onClose, fixtures, navigate, onSelectFixture }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-start pt-[14vh] bg-black/55 backdrop-blur-md motion-safe:animate-fade-in" onClick={onClose}>
      <div
        className="mx-auto w-full max-w-lg bg-surface-raised/95 backdrop-blur-xl rounded-2xl border border-surface-border-hi overflow-hidden"
        style={{ boxShadow: "0 0 0 1px rgba(124,92,255,0.18), 0 24px 60px -12px rgba(0,0,0,0.7)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-surface-border flex items-center gap-2">
          <I.Sparkles size={14} className="text-accent-brand-glow" />
          <input
            autoFocus
            placeholder="Jump to case, fixture, action…"
            className="flex-1 bg-transparent text-sm text-ink-primary outline-none placeholder:text-ink-muted"
          />
          <kbd className="text-[10px] font-mono px-1.5 py-0.5 bg-surface-raised-hi text-ink-muted rounded border border-surface-border">esc</kbd>
        </div>
        <div className="py-2 max-h-[50vh] overflow-auto">
          <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-widest text-ink-muted">Demo Cases</div>
          {fixtures.map((fx) => (
            <button
              key={fx.name}
              onClick={() => { onSelectFixture(fx); navigate(`#/cases/${fx.case_id}`); }}
              className="w-full px-3 py-2 flex items-center gap-2 hover:bg-surface-raised-hi text-left text-sm text-ink-body"
            >
              <Pill tone={VERDICT_META[fx.expected_verdict].tone}>{fx.expected_verdict}</Pill>
              <span className="truncate">{fx.title}</span>
              <span className="ml-auto text-[10px] font-mono text-ink-muted">{fx.case_id}</span>
            </button>
          ))}
          <div className="px-3 py-1 mt-2 text-[10px] font-mono uppercase tracking-widest text-ink-muted">Navigation</div>
          <button onClick={() => navigate("#/")} className="w-full px-3 py-2 flex items-center gap-2 hover:bg-surface-raised-hi text-left text-sm text-ink-body">
            <I.ArrowLeft size={12} /> Home
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================
// Tweaks UI
// =============================================================
function TweaksUI({ tweaks, setTweak, onTriggerPHI, onShowTour }) {
  const { TweaksPanel, TweakSection, TweakSlider, TweakRadio, TweakSelect, TweakToggle, TweakButton } = window;
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection label="Demo">
        <TweakSelect
          label="Demo path"
          value={tweaks.demo_path}
          onChange={(v) => {
            setTweak("demo_path", v);
            const fx = window.CLINCASE_DATA.FIXTURES.find((f) => f.name === v);
            if (fx) window.location.hash = `#/cases/${fx.case_id}`;
          }}
          options={[
            { value: "her2_positive_approve", label: "APPROVE — HER2+ all met" },
            { value: "her2_positive_refer", label: "REFER — missing LVEF" },
            { value: "her2_negative_deny", label: "DENY — biomarker mismatch" },
          ]}
        />
        <TweakSlider
          label="Streaming speed (ms / agent)"
          value={tweaks.stream_speed_ms}
          onChange={(v) => setTweak("stream_speed_ms", v)}
          min={300} max={3500} step={100}
        />
      </TweakSection>

      <TweakSection label="Visuals">
        <TweakRadio
          label="Density"
          value={tweaks.density}
          onChange={(v) => setTweak("density", v)}
          options={[
            { value: "comfortable", label: "Comfortable" },
            { value: "compact", label: "Compact" },
          ]}
        />
        <TweakSlider
          label="Brand hue"
          value={tweaks.brand_hue}
          onChange={(v) => setTweak("brand_hue", v)}
          min={0} max={360} step={1}
        />
      </TweakSection>

      <TweakSection label="Behavior">
        <TweakToggle
          label="Show PHI guardrail banner on run"
          value={tweaks.show_phi_banner}
          onChange={(v) => setTweak("show_phi_banner", v)}
        />
        <TweakToggle
          label="Audit trail expanded after run"
          value={tweaks.audit_default_open}
          onChange={(v) => setTweak("audit_default_open", v)}
        />
        <TweakButton label="Trigger PHI banner now" onClick={onTriggerPHI} />
        <TweakButton label="Replay product tour" onClick={onShowTour} />
      </TweakSection>
    </TweaksPanel>
  );
}

// Mount
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

// Kick off the APPROVE demo automatically on first load (per brief)
if (!window.location.hash || window.location.hash === "#/") {
  // stay on home — the kinetic hero is the wow moment.
  // To auto-route into the APPROVE case, uncomment:
  // window.location.hash = "#/cases/case_8f4ad9c2";
}
