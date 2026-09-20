// Result panels — dark aurora theme
const { useState: useStateR, useEffect: useEffectR, useRef: useRefR, useMemo: useMemoR } = React;

// ---------- Clinical Summary ----------
function ClinicalSummaryCard({ snapshot }) {
  if (!snapshot) return null;
  const dx = snapshot.primary_diagnosis;
  return (
    <section className="bg-surface-raised border border-surface-border rounded-2xl p-6 motion-safe:animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <I.FileText size={16} className="text-ink-body" />
        <h3 className="font-semibold tracking-tight text-ink-primary">Clinical Snapshot</h3>
        <Pill tone="cyan" className="ml-auto">FHIR R4</Pill>
      </div>

      <p className="text-[13.5px] text-ink-body leading-relaxed">{snapshot.free_text_summary}</p>

      <div className="grid sm:grid-cols-2 gap-5 mt-5 pt-5 border-t border-surface-border">
        <div>
          <Eyebrow>Patient</Eyebrow>
          <div className="mt-1.5 text-sm text-ink-body">
            <span className="font-semibold text-ink-primary">{snapshot.patient_age}</span>
            <span className="text-ink-muted"> y/o · </span>
            <span className="font-semibold capitalize text-ink-primary">{snapshot.patient_sex}</span>
            <span className="text-ink-muted"> · </span>
            <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised-hi border border-surface-border text-ink-body">{snapshot.performance_status || "ECOG —"}</span>
          </div>
        </div>
        <div>
          <Eyebrow>Diagnosis</Eyebrow>
          <div className="mt-1.5 text-sm flex items-center gap-1.5 flex-wrap" data-evidence-target={dx.source_resource_id}>
            <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised-hi border border-surface-border text-ink-body">{dx.icd10_code}</span>
            <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised-hi border border-surface-border text-ink-body">Stage {dx.stage}</span>
            <span className="text-ink-body truncate">{dx.description}</span>
          </div>
        </div>
      </div>

      <div className="mt-5 pt-5 border-t border-surface-border">
        <Eyebrow>Biomarkers ({snapshot.biomarkers.length})</Eyebrow>
        <div className="flex flex-wrap gap-1.5 mt-2.5">
          {snapshot.biomarkers.map((b, i) => (
            <span
              key={i}
              data-evidence-target={b.source_resource_id}
              title={`Source: ${b.source_resource_id}`}
              className="text-xs font-mono px-2 py-1 bg-surface-bg border border-surface-border rounded-md text-ink-body hover:border-accent-brand/45 hover:bg-accent-brand/10 transition-colors cursor-default"
            >
              <span className="text-ink-muted">{b.name}</span>
              <span className="text-ink-faint mx-1">=</span>
              <span className="text-ink-primary">{b.value}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="mt-5 pt-5 border-t border-surface-border flex items-center justify-between gap-2 flex-wrap">
        <Eyebrow>Requested Treatment</Eyebrow>
        <div className="text-sm flex items-center gap-2">
          <I.Pill size={14} className="text-ink-muted" />
          <span className="font-semibold text-ink-primary">{snapshot.requested_treatment.name}</span>
          <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised-hi border border-surface-border text-ink-body">{snapshot.requested_treatment.j_code}</span>
          <span className="text-ink-muted text-xs hidden sm:inline">{snapshot.requested_treatment.regimen}</span>
        </div>
      </div>
    </section>
  );
}

// ---------- Confidence ring (full circle, dark) ----------
function ConfidenceRing({ value, color }) {
  const pct = Math.max(0, Math.min(1, value));
  const r = 28;
  const c = 2 * Math.PI * r;
  const dash = c * pct;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: 76, height: 76 }}>
      <svg width="76" height="76" viewBox="0 0 76 76" className="-rotate-90">
        <circle cx="38" cy="38" r={r} fill="none" stroke="var(--surface-border)" strokeWidth="6" />
        <circle
          cx="38" cy="38" r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          style={{ transition: "stroke-dasharray 700ms cubic-bezier(0.16,1,0.3,1)", filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[15px] font-semibold tabular-nums text-ink-primary">{Math.round(pct * 100)}<span className="text-[10px] text-ink-muted ml-0.5">%</span></span>
      </div>
    </div>
  );
}

// ---------- Decision Badge ----------
function useCountUp(target, duration = 800, deps = []) {
  const [value, setValue] = useStateR(0);
  useEffectR(() => {
    let raf;
    const start = performance.now();
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) { setValue(target); return; }
    const tick = (t) => {
      const k = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - k, 5);
      setValue(target * eased);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line
  }, deps);
  return value;
}

function DecisionBadge({ decision, hasAppeal }) {
  if (!decision) return null;
  const meta = VERDICT_META[decision.verdict];
  const Ico = meta.icon;
  const animatedConfidence = useCountUp(decision.confidence, 800, [decision.verdict]);

  return (
    <section
      className={`relative overflow-hidden border ${meta.border} rounded-2xl p-5 sm:p-6 motion-safe:animate-decision-reveal`}
      style={{
        background: `linear-gradient(135deg, ${meta.glow} 0%, transparent 55%), var(--surface-raised)`,
      }}
      data-screen-label={`decision-${decision.verdict.toLowerCase()}`}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 motion-safe:animate-decision-pulse"
        style={{ background: `radial-gradient(circle at 50% 30%, ${meta.color}55 0%, transparent 60%)`, opacity: 0 }}
      />
      {decision.verdict === "APPROVE" && window.Particles && (
        <window.Particles count={10} colors={["", "cyan", ""]} className="opacity-70" />
      )}
      <div className="relative flex items-start gap-4 sm:gap-5">
        <div className="relative shrink-0 w-11 h-11 sm:w-12 sm:h-12 rounded-xl grid place-items-center"
             style={{ background: `${meta.color}1f`, border: `1px solid ${meta.color}66`, boxShadow: `0 0 24px -4px ${meta.color}80` }}>
          <Ico size={26} style={{ color: meta.color }} />
          <window.RippleBurst tone={decision.verdict === "APPROVE" ? "green" : decision.verdict === "DENY" ? "red" : "amber"} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-mono uppercase tracking-widest" style={{ color: meta.color }}>{decision.verdict}</span>
            <span className="text-[11px] font-mono text-ink-muted tabular-nums">· confidence {Math.round(animatedConfidence * 100)}%</span>
            {hasAppeal && (
              <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/40 text-accent-red">
                <I.Loader size={10} className="animate-spin" />
                Appeal drafted
              </span>
            )}
          </div>
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight mt-1 text-ink-primary display-tight">
            ClinCase recommends <span style={{ color: meta.color }}>{meta.label}</span>
          </h3>
          <p className="text-[13px] sm:text-[14px] leading-relaxed mt-2 sm:mt-2.5 text-ink-body max-w-[68ch]">{decision.rationale}</p>
          {decision.risk_flags && decision.risk_flags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-4">
              {decision.risk_flags.map((f) => (
                <span key={f} className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-surface-bg border border-surface-border text-ink-body">
                  <I.AlertTriangle size={10} style={{ color: meta.color }} />
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="hidden sm:flex flex-col items-center gap-1 shrink-0">
          <ConfidenceRing value={animatedConfidence} color={meta.color} />
          <span className="text-[9px] font-mono uppercase tracking-widest text-ink-muted mt-1">confidence</span>
        </div>
      </div>
    </section>
  );
}

// ---------- Citation chips + evidence connector ----------
function CitationChip({ kind, text, pointer, onHover }) {
  const tone =
    kind === "clinical"
      ? "bg-blue-500/10 border-blue-500/30 text-accent-blue hover:bg-blue-500/15 hover:border-blue-500/50"
      : "bg-violet-500/10 border-violet-500/30 text-accent-violet hover:bg-violet-500/15 hover:border-violet-500/50";
  const dot = kind === "clinical" ? "bg-accent-blue" : "bg-accent-violet";
  const Ico = kind === "clinical" ? I.Stethoscope : I.FileText;
  const trimmedPointer = pointer.length > 30 ? pointer.slice(0, 28) + "…" : pointer;
  return (
    <span
      data-evidence-source={pointer}
      title={`${kind}: ${text} · ${pointer}`}
      onMouseEnter={(e) => onHover && onHover(pointer, e.currentTarget)}
      onMouseLeave={() => onHover && onHover(null, null)}
      onFocus={(e) => onHover && onHover(pointer, e.currentTarget)}
      onBlur={() => onHover && onHover(null, null)}
      tabIndex={0}
      className={`inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-1 rounded-md border ${tone} cursor-default transition-all max-w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      <Ico size={11} />
      <span className="opacity-75">{kind}:</span>
      <span className="font-semibold truncate">{trimmedPointer}</span>
    </span>
  );
}

function CitationChain({ citations }) {
  const [hovered, setHovered] = useStateR(null);
  const [line, setLine] = useStateR(null);

  const onHover = (pointer, el) => {
    if (!pointer) { setHovered(null); setLine(null); return; }
    setHovered({ pointer, el });
    const target = document.querySelector(`[data-evidence-target="${CSS.escape(pointer)}"]`);
    if (!target || !el) { setLine(null); return; }
    const a = el.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const x1 = a.left + a.width / 2 + window.scrollX;
    const y1 = a.top + window.scrollY;
    const x2 = b.left + b.width / 2 + window.scrollX;
    const y2 = b.top + b.height + window.scrollY;
    setLine({ x1, y1, x2, y2, kind: pointer.startsWith("policy") || pointer.startsWith("nccn") || pointer.startsWith("asco") ? "policy" : "clinical" });
    target.classList.add("evidence-flash");
    setTimeout(() => target.classList.remove("evidence-flash"), 800);
  };

  if (!citations) return null;
  return (
    <React.Fragment>
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-6">
        <div className="flex items-center gap-2">
          <Eyebrow>Citation Chain ({citations.length})</Eyebrow>
          <span className="ml-auto text-[10px] font-mono text-ink-faint">hover to trace</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {citations.map((c, i) => (
            <CitationChip key={i} kind={c.kind} text={c.text} pointer={c.pointer} onHover={onHover} />
          ))}
        </div>
      </section>
      {line && (
        <svg
          aria-hidden="true"
          style={{ position: "absolute", left: 0, top: 0, width: "100%", height: document.documentElement.scrollHeight, pointerEvents: "none", zIndex: 40 }}
        >
          <path
            d={`M ${line.x1} ${line.y1} C ${line.x1} ${(line.y1 + line.y2) / 2}, ${line.x2} ${(line.y1 + line.y2) / 2}, ${line.x2} ${line.y2}`}
            stroke={line.kind === "clinical" ? "#60a5fa" : "#c084fc"}
            strokeWidth="1.75"
            fill="none"
            strokeDasharray="6 5"
            strokeLinecap="round"
            opacity="0.85"
          >
            <animate attributeName="stroke-dashoffset" from="44" to="0" dur="450ms" fill="freeze" />
          </path>
          <circle cx={line.x2} cy={line.y2} r="4" fill={line.kind === "clinical" ? "#60a5fa" : "#c084fc"} />
        </svg>
      )}
    </React.Fragment>
  );
}

// ---------- Appeal letter (printed-letter feel) ----------
//
// "Download PDF" prints the letter via the browser's native print → save-as-
// PDF flow. The standalone runs from S3 with no backend, so we can't call the
// server-side `/appeals/render.pdf` endpoint here — print() is the universal
// fallback. Triggering print() also cleanly hides every other panel/sidebar
// thanks to the `@media print` rules in ClinCase.html → `body.is-printing-appeal`.
function AppealLetterEditor({ draft }) {
  const [view, setView] = useStateR("letter");
  if (!draft) return null;
  const wordCount = draft.appeal_body.split(/\s+/).filter(Boolean).length;

  // Force the "letter" view + a body class while the print dialog is open
  // so the on-screen toolbar / sidebar / topbar disappear in the PDF output.
  const handleDownload = () => {
    const prevView = view;
    setView("letter");
    document.body.classList.add("is-printing-appeal");
    const onAfter = () => {
      document.body.classList.remove("is-printing-appeal");
      setView(prevView);
      window.removeEventListener("afterprint", onAfter);
    };
    window.addEventListener("afterprint", onAfter);
    // Defer to next tick so React commits the view + body-class change first.
    setTimeout(() => window.print(), 60);
  };

  // Synthetic letterhead values mirror app/render/appeal_pdf.py so the
  // standalone print output looks like the same letter the backend
  // ReportLab path produces. PRODUCTION: pull from `tenants` row.
  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });
  const payerBlock = {
    aetna:  ["Aetna Health Inc.", "Attn: Medical Director · Oncology Appeals", "P.O. Box 14079", "Lexington, KY 40512"],
    uhc:    ["UnitedHealthcare Insurance Company", "Attn: Medical Director · Pharmacy Appeals", "P.O. Box 30432", "Salt Lake City, UT 84130"],
    humana: ["Humana Inc.", "Attn: Medical Director · Oncology Appeals", "P.O. Box 14601", "Lexington, KY 40512"],
  }[(draft.payer_id || "").toLowerCase()] || [
    `${(draft.payer_id || "").toUpperCase() || "Payer"}`,
    "Attn: Medical Director · Appeals",
    "[address on file]",
  ];

  return (
    <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden appeal-letter-card">
      {/* accent top border */}
      <div className="h-0.5 w-full" style={{ background: "linear-gradient(90deg, #7c5cff 0%, #22d3ee 100%)" }} />

      <div className="px-5 py-3 border-b border-surface-border flex items-center gap-2 flex-wrap no-print">
        <I.Mail size={16} className="text-ink-body" />
        <h3 className="font-semibold tracking-tight text-ink-primary">Drafted Appeal Letter</h3>
        <Pill tone="slate" className="ml-1">{wordCount} words</Pill>
        <div className="ml-auto inline-flex items-center gap-1.5">
          <div className="inline-flex bg-surface-bg rounded-md p-0.5 text-xs font-medium border border-surface-border">
            <button
              onClick={() => setView("letter")}
              className={`px-2.5 py-1 rounded transition-colors ${view === "letter" ? "bg-surface-raised-hi text-ink-primary" : "text-ink-muted hover:text-ink-body"}`}
            >Letter</button>
            <button
              onClick={() => setView("structured")}
              className={`px-2.5 py-1 rounded transition-colors ${view === "structured" ? "bg-surface-raised-hi text-ink-primary" : "text-ink-muted hover:text-ink-body"}`}
            >Structured</button>
          </div>
          <button
            onClick={handleDownload}
            title="Open the browser print dialog. Choose 'Save as PDF' → produces a payer-grade letter."
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border border-surface-border bg-accent-brand/10 text-accent-brand-glow hover:bg-accent-brand/20 transition-colors"
          >
            <I.Download size={14} />
            <span>Download PDF</span>
          </button>
        </div>
      </div>

      {view === "letter" ? (
        <div className="px-6 py-6 bg-surface-bg/40 appeal-letter-printable">
          {/*
            "appeal-letter-printable" + the @media print rules in
            ClinCase.html together produce a clean letter on paper:
            letterhead block + date + payer block + body, no sidebar.
          */}
          <header className="appeal-letterhead">
            <h2 className="font-serif text-[20px] font-semibold text-ink-primary">ClinCase Medical Associates</h2>
            <div className="text-[11px] text-accent-brand mt-0.5">Provider-Side Prior Authorization · Oncology</div>
            <div className="text-[10.5px] text-ink-muted mt-1">
              1 Care Square, Suite 400 · San Francisco, CA 94105 · Tel (415) 555-0140 · NPI 1234567890
            </div>
            <hr className="mt-2 mb-3 border-accent-brand/40" />
          </header>
          <div className="appeal-meta text-[12.5px] text-ink-body">
            <div className="mb-2">{today}</div>
            <div className="mb-3 leading-[1.5]">
              {payerBlock.map((line, i) => (<div key={i}>{line}</div>))}
            </div>
            <div className="font-semibold text-ink-primary mb-2">
              Re: Prior Authorization Appeal — Patient {draft.patient_initials || "—"} — {draft.requested_treatment || "—"}
            </div>
            <table className="text-[11.5px] mb-3 border-t border-b border-surface-border">
              <tbody>
                <tr><td className="font-semibold pr-3 py-1 text-ink-primary">Patient initials:</td><td>{draft.patient_initials || "—"}</td></tr>
                <tr><td className="font-semibold pr-3 py-1 text-ink-primary">Treatment requested:</td><td>{draft.requested_treatment || "—"}</td></tr>
                <tr><td className="font-semibold pr-3 py-1 text-ink-primary">Original denial date:</td><td>{draft.denial_date || "—"}</td></tr>
                <tr><td className="font-semibold pr-3 py-1 text-ink-primary">Payer:</td><td>{(draft.payer_id || "—").toUpperCase()}</td></tr>
              </tbody>
            </table>
          </div>
          <div className="max-w-[680px] mx-auto max-h-[480px] overflow-auto appeal-body-scroll">
            <p className="font-serif text-[14.5px] text-ink-body mb-3">Dear Medical Director,</p>
            <pre className="whitespace-pre-wrap font-serif text-[15px] leading-[1.7] text-ink-body">{draft.appeal_body}</pre>
          </div>
          <div className="appeal-signature mt-3 text-[12.5px] text-ink-body">
            <p className="mb-1">Respectfully submitted,</p>
            <div className="h-10" />
            <p className="font-semibold text-ink-primary">ClinCase Clinical Authorization Team</p>
            <p className="text-[10.5px] text-ink-muted">On behalf of the requesting provider</p>
          </div>
        </div>
      ) : (
        <div className="px-5 py-4 space-y-3">
          {draft.structured_arguments.map((a, i) => (
            <div key={i} className="border border-surface-border rounded-xl p-4 bg-surface-bg/40">
              <Eyebrow>Contested Criterion · {a.contested_criterion}</Eyebrow>
              <div className="grid sm:grid-cols-2 gap-3 mt-2">
                <div className="border-l-2 border-rose-500/50 pl-3">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-accent-red">Payer Position</div>
                  <p className="text-[13px] text-ink-body mt-1">{a.payer_position}</p>
                </div>
                <div className="border-l-2 border-emerald-500/50 pl-3">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-accent-green">Counter Position</div>
                  <p className="text-[13px] text-ink-body mt-1">{a.counter_position}</p>
                </div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted">Cited Evidence</div>
                <ul className="list-disc list-inside text-xs text-ink-body mt-1 space-y-0.5">
                  {a.cited_evidence.map((ev, j) => <li key={j} className="font-mono">{ev}</li>)}
                </ul>
              </div>
              <div className="mt-2">
                <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/30 text-accent-violet">
                  <span aria-hidden>📖</span> {a.cited_guideline}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="px-5 py-3 border-t border-surface-border flex flex-wrap items-center gap-1.5">
        <Eyebrow>Attachments</Eyebrow>
        {draft.attachments_referenced.map((a, i) => (
          <span key={i} className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-bg text-ink-body border border-surface-border">{a}</span>
        ))}
      </div>

      <div className="px-5 py-3 border-t border-surface-border bg-accent-brand/[0.06]">
        <Eyebrow className="text-accent-brand-glow">Requested Action</Eyebrow>
        <p className="text-[13.5px] text-ink-body mt-1">{draft.requested_action}</p>
      </div>
    </section>
  );
}

// ---------- Audit Log ----------
function AuditLogViewer({ events, fixtureName, defaultOpen, totalCost, totalWallclock }) {
  const [open, setOpen] = useStateR(!!defaultOpen);
  useEffectR(() => setOpen(!!defaultOpen), [defaultOpen]);

  const data = window.CLINCASE_DATA;
  const verdict = data.DECISIONS[fixtureName].verdict;
  const agents = data.AGENT_SPECS.filter((a) => verdict === "DENY" || a.key !== "appeals_drafter");

  const rows = agents.map((a, i) => {
    const finished = events.find((e) => e.type === "agent_finished" && e.agent_name === a.key);
    return {
      idx: i + 1,
      name: a.name,
      latency: finished ? finished.latency_ms : null,
      input: finished ? finished.input_tokens : null,
      output: finished ? finished.output_tokens : null,
      model: finished ? finished.model_id : a.model,
      ok: !!finished,
    };
  });

  const totalIn = rows.reduce((s, r) => s + (r.input || 0), 0);
  const totalOut = rows.reduce((s, r) => s + (r.output || 0), 0);

  return (
    <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-5 py-3 flex items-center gap-2 text-left hover:bg-surface-raised-hi transition-colors"
      >
        <I.FileText size={16} className="text-ink-body" />
        <h3 className="font-semibold tracking-tight text-ink-primary">Audit Trail</h3>
        <span className="text-[11px] font-mono text-ink-muted hidden sm:inline">
          (every input, every output, every token — reproducible)
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs font-mono text-ink-muted">
          {rows.filter((r) => r.ok).length}/{rows.length} runs
          <I.ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </div>
      </button>

      {open && (
        <div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-bg text-ink-muted font-mono uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Agent</th>
                  <th className="px-4 py-2 text-right">Latency</th>
                  <th className="px-4 py-2 text-right">Tokens (in / out)</th>
                  <th className="px-4 py-2 text-left">Model</th>
                  <th className="px-4 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.idx} className={`border-t border-surface-border hover:bg-surface-raised-hi ${r.idx % 2 === 0 ? "bg-surface-bg/40" : ""}`}>
                    <td className="px-4 py-2 font-mono text-ink-muted">{r.idx}</td>
                    <td className="px-4 py-2 font-medium text-ink-primary">{r.name}</td>
                    <td className="px-4 py-2 font-mono text-right tabular-nums text-ink-body">
                      {r.latency ? `${(r.latency / 1000).toFixed(2)}s` : "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-right tabular-nums text-ink-body">
                      {r.input ? `${r.input.toLocaleString()} / ${r.output.toLocaleString()}` : "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-ink-body">
                      {r.model.split("/").pop()}
                    </td>
                    <td className="px-4 py-2">
                      {r.ok ? <Pill tone="emerald">OK</Pill> : <Pill tone="slate">Pending</Pill>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-5 py-3 border-t border-surface-border bg-surface-bg flex flex-wrap items-center gap-x-6 gap-y-1 text-xs font-mono">
            <span className="text-ink-muted">wall-clock <span className="text-ink-primary font-semibold tabular-nums">{(totalWallclock / 1000).toFixed(2)}s</span></span>
            <span className="text-ink-muted">tokens <span className="text-ink-primary font-semibold tabular-nums">{(totalIn + totalOut).toLocaleString()}</span></span>
            <span className="text-ink-muted">cost <span className="text-accent-cyan font-semibold tabular-nums">${totalCost.toFixed(4)}</span></span>
            <span className="ml-auto text-ink-faint">Sonnet 4.6 · $3/M in · $15/M out</span>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------- PHI Banner ----------
function PHIBanner({ visible, onClose }) {
  if (!visible) return null;
  return (
    <React.Fragment>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-20 pointer-events-none motion-safe:animate-phi-backdrop"
        style={{
          background: "radial-gradient(circle at 50% 0%, rgba(251,113,133,0.22) 0%, transparent 60%)",
          opacity: 0,
        }}
      />
      <div
        className="relative z-30 rounded-xl p-3 flex items-start gap-3 motion-safe:animate-slide-in-down"
        style={{
          background: "linear-gradient(135deg, rgba(251,113,133,0.16) 0%, rgba(251,113,133,0.04) 100%)",
          border: "1px solid rgba(251,113,133,0.45)",
          boxShadow: "0 0 0 1px rgba(251,113,133,0.15), 0 12px 32px -12px rgba(251,113,133,0.45)",
        }}
      >
        <div className="motion-safe:animate-shield-spin">
          <I.Shield size={18} className="text-accent-red mt-0.5 shrink-0" />
        </div>
        <div className="flex-1 text-sm">
          <span className="font-semibold text-rose-200">GUARDRAIL FIRED</span>
          <span className="text-rose-100/85"> — 7 PHI entities redacted before LLM call: </span>
          <span className="font-mono text-xs text-rose-100">SSN, DOB, MRN, ADDRESS, PHONE × 2, INSURANCE_ID</span>
          <span className="block text-[11px] font-mono text-rose-300/80 mt-1">amazon-bedrock-guardrails · clincase-clinical-v1</span>
        </div>
        <button
          onClick={onClose}
          className="text-rose-200 hover:text-white shrink-0 w-11 h-11 -my-1 -mr-1 grid place-items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-red"
          aria-label="Dismiss guardrail notice"
        >
          <I.X size={14} />
        </button>
      </div>
    </React.Fragment>
  );
}

// ---------- Risk meter (Case Detail header) ----------
function RiskMeter({ fixtureName, done, verdict }) {
  // map fixture -> base risk score 0..1 (1 = high)
  const baseRisk = {
    her2_positive_approve: 0.18,
    her2_positive_refer:   0.55,
    her2_negative_deny:    0.86,
  }[fixtureName] ?? 0.4;

  // After completion, snap risk to verdict
  const finalRisk = done
    ? (verdict === "APPROVE" ? 0.15 : verdict === "DENY" ? 0.88 : 0.55)
    : baseRisk;

  const tier = finalRisk < 0.34 ? "low" : finalRisk < 0.67 ? "moderate" : "high";
  const tierMeta = {
    low:      { color: "var(--accent-green)", label: "Low",      tone: "emerald" },
    moderate: { color: "var(--accent-amber)", label: "Moderate", tone: "amber"   },
    high:     { color: "var(--accent-rose)",  label: "High",     tone: "rose"    },
  }[tier];

  const segs = 3;
  return (
    <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-bg border border-surface-border" title={`Denial-risk score: ${(finalRisk*100).toFixed(0)}%`}>
      <I.AlertTriangle size={12} className="text-ink-muted" />
      <div className="flex flex-col gap-0.5 leading-tight">
        <span className="text-[9px] font-mono uppercase tracking-widest text-ink-muted">Denial risk</span>
        <div className="flex items-center gap-1.5">
          <div className="flex items-center gap-0.5">
            {[0, 1, 2].map((i) => {
              const filled = (tier === "low" && i === 0) ||
                             (tier === "moderate" && i <= 1) ||
                             (tier === "high" && i <= 2);
              return (
                <span
                  key={i}
                  className="w-3 h-1.5 rounded-sm transition-colors"
                  style={{ background: filled ? tierMeta.color : "var(--surface-border-hi)" }}
                />
              );
            })}
          </div>
          <span className="text-[11px] font-medium" style={{ color: tierMeta.color }}>{tierMeta.label}</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  ClinicalSummaryCard,
  DecisionBadge,
  CitationChain,
  AppealLetterEditor,
  AuditLogViewer,
  PHIBanner,
  ConfidenceRing,
  RiskMeter,
});
