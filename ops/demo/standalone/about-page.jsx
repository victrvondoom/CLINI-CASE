/* global window, React */
/* ============================================================
   ABOUT PAGE — self-pitch for the 2026 hackathon judges.

   8 scroll-anchored sections, each with brand-coloured ambient blobs
   and section-specific accent glow. Floating progress rail on the right
   tracks position. Designed to be readable in < 2 minutes by a busy
   judge while still providing depth on every section.

   Tone: enterprise-formal · evidence-cited · no fluff.
   Layout: ~3500px tall on a typical monitor; smooth-scrolls cleanly.
   ============================================================ */
const { useState: useSA, useEffect: useEA, useRef: useRA } = React;

function AboutPage({ navigate }) {
  const D = window.CLINCASE_ABOUT;
  const sectionRefs = useRA([]);
  const [active, setActive] = useSA(0);

  const SECTIONS = [
    { id: "hero",         label: "Hero" },
    { id: "problem",      label: "Problem" },
    { id: "solution",     label: "Solution" },
    { id: "intake",       label: "Document Intake" },
    { id: "architecture", label: "Architecture" },
    { id: "strategic-fit",    label: "Strategic Fit" },
    { id: "team",         label: "Team AeroFyta" },
    { id: "ask",          label: "The Ask" },
  ];

  // Track which section is in view
  useEA(() => {
    const onScroll = () => {
      const y = window.scrollY + 200;
      for (let i = sectionRefs.current.length - 1; i >= 0; i--) {
        const el = sectionRefs.current[i];
        if (el && el.offsetTop <= y) { setActive(i); break; }
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (i) => {
    sectionRefs.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div data-screen-label="about" className="relative">
      {/* ---- Floating section rail (right side) ---- */}
      <nav
        aria-label="About sections"
        className="hidden lg:flex fixed right-6 top-1/2 -translate-y-1/2 z-30 flex-col gap-2.5 bg-surface-raised/70 backdrop-blur-md border border-surface-border rounded-full px-2 py-3 shadow-lg"
      >
        {SECTIONS.map((s, i) => (
          <button
            key={s.id}
            onClick={() => scrollTo(i)}
            title={s.label}
            aria-label={`Jump to ${s.label}`}
            className={`group relative flex items-center justify-center w-2.5 h-2.5 rounded-full transition-all
              ${active === i ? "bg-accent-brand-glow scale-150" : "bg-ink-faint hover:bg-ink-muted"}`}
          >
            <span className="absolute right-full mr-3 px-2 py-1 rounded-md bg-surface-raised border border-surface-border text-[10px] font-mono text-ink-primary opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none transition-opacity">
              {s.label}
            </span>
          </button>
        ))}
      </nav>

      {/* =================== SECTION 1 — HERO =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[0] = el)}
        id="hero"
        ambient="brand"
        eyebrow="ABOUT CLINCASE · TEAM AEROFYTA · THE 2026 HACKATHON"
      >
        <h1 className="text-[clamp(40px,7vw,80px)] font-semibold tracking-tight leading-[1.05] display-tight">
          Approve cancer treatment in
          <span className="block">
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(120deg, var(--accent-brand) 0%, var(--accent-cyan) 50%, var(--accent-violet) 100%)" }}>
              minutes, not weeks.
            </span>
          </span>
        </h1>
        <p className="mt-5 text-[16.5px] text-ink-body leading-[1.7] max-w-[68ch]">
          ClinCase is a provider-side oncology prior-authorisation copilot. Seven specialised agents
          read the FHIR bundle (or the handwritten Indian Rx, the scanned echo, the faxed denial),
          match it against payer policy, and ship a citation-grounded verdict — APPROVE, DENY, or
          REFER — in under seven minutes. On denial, an NCCN-cited appeal letter is drafted
          automatically. Every claim traces back to a FHIR resource id and a payer policy section.
        </p>

        <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-3.5">
          {D.HERO_KPIS.map((k, i) => (
            <KpiTile key={i} {...k} />
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <button
            onClick={() => navigate?.("#/cases/case_8f4ad9c2")}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent-brand text-ink-invert font-medium text-[14px] shadow-lg shadow-accent-brand/30 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent-brand/40 transition-all"
          >
            <I.Play size={14} /> Run a live case
          </button>
          <button
            onClick={() => navigate?.("#/intake")}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface-raised border border-surface-border text-ink-primary font-medium text-[14px] hover:border-accent-brand/40 hover:bg-surface-raised-hi transition-all"
          >
            <I.Upload size={14} /> Drop a handwritten Rx
          </button>
          <button
            onClick={() => navigate?.("#/agents")}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface-raised border border-surface-border text-ink-primary font-medium text-[14px] hover:border-accent-brand/40 hover:bg-surface-raised-hi transition-all"
          >
            <I.Cpu size={14} /> See the 7-agent DAG
          </button>
        </div>

        <div className="mt-10 flex flex-wrap gap-2 items-center text-[10.5px] font-mono">
          <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-accent-green border border-emerald-500/30">SOC 2 type II</span>
          <span className="px-2.5 py-1 rounded-md bg-cyan-500/10 text-accent-cyan border border-cyan-500/30">HIPAA · zero PHI in logs</span>
          <span className="px-2.5 py-1 rounded-md bg-indigo-500/10 text-accent-brand-glow border border-indigo-500/30">CMS-0057-F § IV.A audited</span>
          <span className="px-2.5 py-1 rounded-md bg-violet-500/10 text-accent-violet border border-violet-500/30">AWS Bedrock + Sonnet 4.6 + Haiku 4.5</span>
        </div>
      </Section>

      {/* =================== SECTION 2 — THE PROBLEM =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[1] = el)}
        id="problem"
        ambient="rose"
        eyebrow="01 · THE PROBLEM"
        title="The prior-auth fight is killing the oncology workflow."
        kicker="Coordinators spend 14 hours per oncology case fighting payers. Patients wait weeks for therapy that the data already supports. The system runs on faxes, phone calls, and PDFs."
      >
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
          {D.PROBLEM_FACTS.map((f, i) => (
            <FactCard key={i} {...f} />
          ))}
        </div>
      </Section>

      {/* =================== SECTION 3 — THE SOLUTION =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[2] = el)}
        id="solution"
        ambient="indigo"
        eyebrow="02 · THE SOLUTION"
        title="Seven specialised agents, one citation-grounded verdict."
        kicker="ClinCase is a LangGraph DAG orchestrating seven LLM and deterministic agents. Each agent owns one bounded responsibility, writes its inputs and outputs to an audit ledger, and emits an SSE trace event the coordinator can watch in real time."
      >
        <div className="mt-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {D.AGENTS.map((a) => (
            <AgentCard key={a.n} agent={a} />
          ))}
          <div className="col-span-2 md:col-span-3 lg:col-span-4 mt-2 rounded-xl border border-surface-border bg-surface-bg/50 px-4 py-3 text-[13px] text-ink-body italic">
            <strong className="text-ink-primary not-italic">Neuro-SAN AAOSA-aligned.</strong>
            {" "}Bounded responsibility · stateful continuity · per-tenant adaptation · observability of every hop.
            Every agent has a Pydantic input/output schema, a versioned prompt, a contract test, and a 5-field GraderScore.
          </div>
        </div>
      </Section>

      {/* =================== SECTION 4 — DOCUMENT INTAKE =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[3] = el)}
        id="intake"
        ambient="cyan"
        eyebrow="03 · INDIA-READY · DOCUMENT INTAKE"
        title="Handwritten Rx, scanned reports, faxed denials. Same DAG."
        kicker="Real-world prior-auth submissions don't arrive as clean FHIR. They arrive as phone-camera scans of pathology slips, doctor's-pad prescriptions in mixed English-Hindi, and faxed denial letters. The Document Intake layer turns the mess into a typed ClinicalSnapshot in one Bedrock multimodal call."
      >
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
          {D.INTAKE_INPUTS.map((it, i) => (
            <div key={i} className="rounded-xl border border-surface-border bg-surface-raised p-4 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-accent-cyan/10 transition-all">
              <div className="text-[28px]">{it.icon}</div>
              <div className="mt-2 text-[13px] font-semibold text-ink-primary">{it.label}</div>
              <div className="mt-1 text-[11px] text-ink-muted font-mono leading-[1.5]">{it.desc}</div>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-xl border border-cyan-500/30 bg-cyan-500/5 px-5 py-4">
          <div className="text-[11px] font-mono text-accent-cyan uppercase tracking-widest mb-1">Pipeline</div>
          <div className="text-[14px] text-ink-body">
            <span className="font-mono">PIL classifier</span> →
            <span className="font-mono"> Claude Sonnet 4.6 vision (Bedrock)</span> →
            <span className="font-mono"> partial ClinicalSnapshot</span> →
            <span className="text-accent-brand-glow font-mono"> 7-agent DAG</span>
          </div>
          <div className="mt-2 text-[11.5px] text-ink-muted">
            Per-field confidence. Below 0.7 OR a binding field missing → REFER + Reviewer queue. The model never silently APPROVES on a smudged biomarker.
          </div>
        </div>
      </Section>

      {/* =================== SECTION 5 — ARCHITECTURE =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[4] = el)}
        id="architecture"
        ambient="violet"
        eyebrow="04 · ARCHITECTURE"
        title="Six concentric layers. One responsibility each."
        kicker="The architecture maps directly to the partner's published Neuro-SAN AAOSA pattern: bounded responsibility per layer, top-down dependency only, no upper layer reaching down past its neighbour. Every layer is a real running module — not a slide artifact."
      >
        <div className="mt-2 space-y-2">
          {D.LAYERS.map((l) => (
            <div key={l.num} className="flex items-stretch gap-3 rounded-lg border border-surface-border bg-surface-raised hover:-translate-x-0.5 transition-transform">
              <div className={`flex items-center justify-center w-20 font-mono font-bold text-white text-[15px]
                ${l.color === "emerald" ? "bg-emerald-600" :
                  l.color === "sky"     ? "bg-sky-600" :
                  l.color === "cyan"    ? "bg-cyan-600" :
                  l.color === "indigo"  ? "bg-indigo-600" :
                  l.color === "violet"  ? "bg-violet-600" :
                                          "bg-slate-800"} rounded-l-lg`}>
                {l.num}
              </div>
              <div className="flex-1 py-3 pr-4">
                <div className="text-[14px] font-semibold text-ink-primary">{l.name}</div>
                <div className="text-[12px] text-ink-body font-mono mt-0.5">{l.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 grid md:grid-cols-2 gap-3">
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-3">
            <div className="text-[11px] font-mono uppercase tracking-widest text-accent-green">CMS-0057-F § IV.A · Audit trail</div>
            <div className="text-[12.5px] text-ink-body mt-1">Every agent_runs row carries SHA-256 input hash, model_id, latency, cost. A scanned-fax verdict reconstructs from the ledger alone.</div>
          </div>
          <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 px-4 py-3">
            <div className="text-[11px] font-mono uppercase tracking-widest text-accent-violet">5-field GraderScore</div>
            <div className="text-[12.5px] text-ink-body mt-1">Correctness · Grounding · Completeness · Format · Safety. Per-agent + composite. Replaces "did the LLM do well?" with cohort-level deltas.</div>
          </div>
        </div>
      </Section>

      {/* =================== SECTION 6 — STRATEGIC FIT =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[5] = el)}
        id="strategic-fit"
        ambient="amber"
        eyebrow="05 · WHY THIS STACK WINS WITH CLINCASE"
        title="Built on the exact stack the payer organization sells today."
        kicker="This isn't a bet on a new technology — it's the canonical implementation of the Anthropic enterprise partnership applied to prior-auth, ready to slot into the existing distribution channel."
      >
        <div className="mt-3 grid md:grid-cols-2 gap-3.5">
          {D.STRATEGIC_FIT.map((c, i) => (
            <div key={i} className="rounded-xl border border-surface-border bg-surface-raised p-4 hover:border-accent-amber/40 transition-colors">
              <div className="text-[10.5px] font-mono uppercase tracking-widest text-accent-amber">{c.tag}</div>
              <div className="mt-1 text-[15px] font-semibold text-ink-primary">{c.claim}</div>
              <div className="mt-1 text-[12.5px] text-ink-body leading-[1.6]">{c.detail}</div>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-xl border border-surface-border bg-surface-bg/50 px-4 py-3">
          <div className="text-[10.5px] font-mono uppercase tracking-widest text-ink-muted mb-2">Compliance posture</div>
          <div className="flex flex-wrap gap-2">
            {D.COMPLIANCE.map((c, i) => (
              <span key={i} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[11px] font-mono">
                <span className="text-accent-green">●</span>
                <span className="text-ink-primary font-semibold">{c.code}</span>
                <span className="text-ink-muted">{c.title}</span>
              </span>
            ))}
          </div>
        </div>
      </Section>

      {/* =================== SECTION 7 — TEAM =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[6] = el)}
        id="team"
        ambient="green"
        eyebrow="06 · TEAM AEROFYTA"
        title="Four engineers. One product. Sixty-two days from blank repo to verdict."
        kicker="Chennai Institute of Technology · Class of 2027 · all four members shipped code that runs in this demo."
      >
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
          {D.TEAM.map((m, i) => (
            <TeamCard key={i} {...m} />
          ))}
        </div>
      </Section>

      {/* =================== SECTION 8 — THE ASK =================== */}
      <Section
        innerRef={(el) => (sectionRefs.current[7] = el)}
        id="ask"
        ambient="indigo"
        eyebrow="07 · THE ASK"
        title="From hackathon win to enterprise production push."
        kicker="Three concrete next steps — each unlocks the next."
      >
        <div className="mt-3 space-y-3">
          {D.THE_ASK.map((a) => (
            <div key={a.tier} className="flex items-start gap-4 rounded-xl border border-surface-border bg-surface-raised p-5 hover:border-accent-brand/40 transition-colors">
              <div className="w-12 h-12 rounded-full bg-accent-brand text-ink-invert flex items-center justify-center font-mono font-bold text-[18px] shrink-0">
                {a.tier}
              </div>
              <div>
                <div className="text-[16px] font-semibold text-ink-primary">{a.title}</div>
                <div className="mt-1 text-[13px] text-ink-body leading-[1.6]">{a.detail}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-7 rounded-xl border border-accent-brand/30 bg-accent-brand/5 p-5 text-center">
          <div className="text-[11px] font-mono uppercase tracking-widest text-accent-brand-glow mb-2">TRY IT NOW</div>
          <div className="text-[18px] font-semibold text-ink-primary mb-1">
            Run a real verdict in 7 minutes — no install, no login.
          </div>
          <div className="text-[13px] text-ink-muted mb-4">
            Drop the synthetic Indian oncology Rx into the intake page and watch the 7-agent pipeline run end-to-end.
          </div>
          <button
            onClick={() => navigate?.("#/intake")}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-accent-brand text-ink-invert font-semibold text-[14px] shadow-lg shadow-accent-brand/30 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent-brand/40 transition-all"
          >
            <I.Upload size={15} /> Drop a scan
          </button>
        </div>

        {/* Sources footer */}
        <div className="mt-8 pt-6 border-t border-surface-border">
          <div className="text-[10px] font-mono uppercase tracking-widest text-ink-faint mb-2">Sources & citations · all claims verifiable</div>
          <div className="text-[11px] text-ink-muted leading-[1.7] font-mono">
            {D.SOURCES.join(" · ")}
          </div>
        </div>
      </Section>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* SUB-COMPONENTS                                                          */
/* ---------------------------------------------------------------------- */

function Section({ innerRef, id, ambient, eyebrow, title, kicker, children }) {
  const ambientColor = {
    brand:  "from-accent-brand/15 via-transparent to-accent-cyan/10",
    rose:   "from-rose-500/10 via-transparent to-amber-500/5",
    indigo: "from-accent-brand/15 via-transparent to-accent-violet/10",
    cyan:   "from-accent-cyan/15 via-transparent to-accent-brand/8",
    violet: "from-accent-violet/15 via-transparent to-accent-brand/8",
    amber:  "from-amber-500/10 via-transparent to-rose-500/5",
    green:  "from-emerald-500/10 via-transparent to-accent-cyan/8",
  }[ambient] || "from-accent-brand/15 via-transparent to-accent-cyan/10";

  return (
    <section
      ref={innerRef}
      id={id}
      className="relative isolate min-h-screen flex items-center px-5 md:px-10 lg:px-16 py-20 scroll-mt-20 overflow-hidden"
    >
      {/* Ambient backdrop */}
      <div aria-hidden="true" className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${ambientColor}`} />
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 -right-32 w-[560px] h-[560px] rounded-full bg-accent-brand/10 blur-[120px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 -left-32 w-[480px] h-[480px] rounded-full bg-accent-cyan/10 blur-[120px]" />

      <div className="relative z-10 w-full max-w-[1100px] mx-auto">
        {eyebrow && (
          <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-accent-brand-glow mb-3">{eyebrow}</div>
        )}
        {title && (
          <h2 className="text-[clamp(28px,4.5vw,48px)] font-semibold tracking-tight text-ink-primary leading-[1.1] display-tight">
            {title}
          </h2>
        )}
        {kicker && (
          <p className="mt-3 text-[14.5px] text-ink-body max-w-[68ch] leading-[1.7]">
            {kicker}
          </p>
        )}
        {children}
      </div>
    </section>
  );
}

function KpiTile({ value, label, source, tone }) {
  const toneClass = {
    indigo: "text-accent-brand-glow",
    cyan:   "text-accent-cyan",
    rose:   "text-rose-400",
    green:  "text-accent-green",
  }[tone] || "text-ink-primary";
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised/80 backdrop-blur-sm p-4 hover:-translate-y-1 hover:shadow-xl hover:shadow-accent-brand/10 transition-all">
      <div className={`text-[clamp(28px,3vw,38px)] font-bold tracking-tight ${toneClass} display-tight`}>{value}</div>
      <div className="text-[11.5px] text-ink-body font-medium mt-1 leading-[1.4]">{label}</div>
      <div className="text-[10px] font-mono text-ink-faint mt-2 italic leading-[1.4]">{source}</div>
    </div>
  );
}

function FactCard({ headline, detail, source }) {
  return (
    <div className="rounded-xl border border-rose-500/30 bg-rose-500/[0.05] p-4 hover:border-rose-500/50 transition-colors">
      <div className="text-[18px] font-semibold text-rose-300 leading-tight">{headline}</div>
      <div className="text-[13px] text-ink-body mt-2 leading-[1.6]">{detail}</div>
      <div className="text-[10px] font-mono text-ink-muted mt-2 italic">{source}</div>
    </div>
  );
}

function AgentCard({ agent }) {
  const accentClass = {
    emerald: "border-emerald-500/40 hover:bg-emerald-500/5",
    blue:    "border-blue-500/40    hover:bg-blue-500/5",
    violet:  "border-violet-500/40  hover:bg-violet-500/5",
    indigo:  "border-indigo-500/40  hover:bg-indigo-500/5",
    amber:   "border-amber-500/40   hover:bg-amber-500/5",
    rose:    "border-rose-500/40    hover:bg-rose-500/5",
    cyan:    "border-cyan-500/40    hover:bg-cyan-500/5",
  }[agent.color] || "border-surface-border";
  const numClass = {
    emerald: "bg-emerald-500/15 text-emerald-300",
    blue:    "bg-blue-500/15 text-blue-300",
    violet:  "bg-violet-500/15 text-violet-300",
    indigo:  "bg-indigo-500/15 text-indigo-300",
    amber:   "bg-amber-500/15 text-amber-300",
    rose:    "bg-rose-500/15 text-rose-300",
    cyan:    "bg-cyan-500/15 text-cyan-300",
  }[agent.color] || "bg-ink-muted/15 text-ink-muted";
  return (
    <div className={`rounded-xl border bg-surface-raised p-3.5 transition-all ${accentClass}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-7 h-7 rounded-md flex items-center justify-center font-mono font-bold text-[12px] ${numClass}`}>{agent.n}</span>
        <span className="text-[13px] font-semibold text-ink-primary">{agent.name}</span>
      </div>
      <div className="text-[11px] text-ink-body font-mono leading-[1.5]">{agent.role}</div>
      <div className="mt-2 text-[10px] font-mono text-ink-muted">model: {agent.model}</div>
    </div>
  );
}

function TeamCard({ initials, name, role, owns, contact, org }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5 hover:border-accent-brand/40 hover:-translate-y-0.5 transition-all">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-accent-brand to-accent-cyan text-ink-invert font-mono font-bold flex items-center justify-center text-[14px] shadow-lg">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-semibold text-ink-primary">{name}</div>
          <div className="text-[10.5px] font-mono uppercase tracking-widest text-accent-brand-glow">{role}</div>
        </div>
      </div>
      <div className="mt-3 text-[12px] text-ink-body leading-[1.6]"><span className="text-ink-muted font-mono text-[10.5px] uppercase tracking-widest">Owns </span>{owns}</div>
      <div className="mt-2 flex items-center justify-between text-[10.5px] font-mono">
        <span className="text-ink-muted">{contact}</span>
        <span className="text-ink-faint">{org}</span>
      </div>
    </div>
  );
}

window.AboutPage = AboutPage;
