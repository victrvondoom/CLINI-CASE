// Reasoning Trace Panel + Agent cards + simulated SSE engine (dark aurora theme)
const { useState: useStateT, useEffect: useEffectT, useRef: useRefT, useMemo: useMemoT } = React;

// Simulate the LangGraph SSE stream
function runSimulatedStream({ fixtureName, speedMs, onEvent, onDone }) {
  const data = window.CLINCASE_DATA;
  const profile = data.buildAgentRuns(fixtureName);
  const verdict = data.DECISIONS[fixtureName].verdict;
  const agents = ["clinical_extractor", "policy_retriever", "necessity_reasoner", "decision_composer"];
  if (verdict === "DENY") agents.push("appeals_drafter");

  let idx = 0;
  let cancelled = false;
  const timers = [];

  const tick = () => {
    if (cancelled || idx >= agents.length) {
      if (!cancelled) timers.push(setTimeout(() => onDone && onDone(), 120));
      return;
    }
    const agent = agents[idx];
    const prof = profile[idx] || profile[profile.length - 1];
    onEvent({ type: "agent_started", agent_name: agent, ts: Date.now() });
    timers.push(
      setTimeout(() => {
        if (cancelled) return;
        onEvent({
          type: "agent_finished",
          agent_name: agent,
          ts: Date.now(),
          latency_ms: prof.ms,
          model_id: data.AGENT_SPECS.find((a) => a.key === agent).model,
          input_tokens: prof.in,
          output_tokens: prof.out,
        });
        idx += 1;
        timers.push(setTimeout(tick, speedMs * 0.18));
      }, speedMs)
    );
  };
  timers.push(setTimeout(tick, speedMs * 0.25));
  return () => {
    cancelled = true;
    timers.forEach(clearTimeout);
  };
}

function statusOf(events, agentKey) {
  let started = false, finished = false, run = null;
  for (const e of events) {
    if (e.agent_name !== agentKey) continue;
    if (e.type === "agent_started") started = true;
    if (e.type === "agent_finished") { finished = true; run = e; }
  }
  if (finished) return { status: "done", run };
  if (started) return { status: "running", run: null };
  return { status: "pending", run: null };
}

function AgentCard({ spec, status, run, fixtureName, index, expanded, onToggle }) {
  // Dark-themed shells
  const tones = {
    pending: "border-surface-border bg-surface-bg/60",
    running: "border-accent-brand/55 bg-surface-raised shadow-[0_0_0_1px_rgba(124,92,255,0.18),0_8px_28px_-12px_rgba(124,92,255,0.55)]",
    done:    "border-emerald-500/30 bg-surface-bg/60",
    error:   "border-rose-500/45 bg-surface-bg/60",
  };
  const pill = {
    pending: <Pill tone="slate">Pending</Pill>,
    running: <Pill tone="brand" className="animate-pulse-soft">Thinking…</Pill>,
    done:    <Pill tone="emerald">Completed</Pill>,
    error:   <Pill tone="rose">Error</Pill>,
  }[status];

  const statusIcon = {
    pending: <div className="w-5 h-5 rounded-full border border-dashed border-ink-faint" />,
    running: <I.Loader size={18} className="text-accent-brand-glow animate-spin" />,
    done:    <I.CheckCircle size={18} className="text-accent-green" />,
    error:   <I.AlertCircle size={18} className="text-accent-red" />,
  }[status];

  const modelShort = run?.model_id ? run.model_id.split("/").pop() : spec.model.split("/").pop();
  const sample = useMemoT(() => buildSampleOutput(spec.key, fixtureName), [spec.key, fixtureName]);

  return (
    <div
      className={`rounded-xl border-2 p-4 transition-all duration-300 ${tones[status]} ${status === "running" ? "motion-safe:animate-slide-in-right" : ""}`}
      data-screen-label={`agent-${index}-${spec.key}`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0">{statusIcon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[11px] font-mono text-ink-faint">0{index + 1}</span>
              <h3 className="font-semibold text-sm truncate text-ink-primary">{spec.name}</h3>
            </div>
            {pill}
          </div>
          <p className="text-xs text-ink-muted mt-1 leading-snug">{spec.description}</p>

          {(status === "running" || status === "done") && (
            <div className="mt-3 flex items-center gap-3 text-[11px] font-mono text-ink-muted flex-wrap">
              <span className="inline-flex items-center gap-1">
                <I.Clock size={12} />
                {run ? `${(run.latency_ms / 1000).toFixed(2)}s` : "…"}
              </span>
              <span className="inline-flex items-center gap-1">
                <I.Cpu size={12} />
                {modelShort}
              </span>
              {run && (
                <span className="text-ink-muted tabular-nums">
                  <span className="text-ink-body">{run.input_tokens.toLocaleString()}</span>
                  <span className="text-ink-faint"> in / </span>
                  <span className="text-ink-body">{run.output_tokens.toLocaleString()}</span>
                  <span className="text-ink-faint"> out</span>
                </span>
              )}
            </div>
          )}

          {status === "done" && (
            <button
              onClick={onToggle}
              className="mt-3 inline-flex items-center gap-1 text-[11px] font-mono text-accent-brand-glow hover:text-white transition-colors"
            >
              {expanded ? <I.ChevronDown size={12} /> : <I.ChevronRight size={12} />}
              {expanded ? "Hide output" : "Show output"}
            </button>
          )}
          {expanded && status === "done" && (
            <pre className="mt-2 max-h-64 overflow-auto bg-surface-bg border border-surface-border rounded-md p-2 text-[11px] font-mono leading-relaxed text-ink-body whitespace-pre-wrap">
{sample}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function buildSampleOutput(agentKey, fixtureName) {
  const d = window.CLINCASE_DATA;
  if (agentKey === "clinical_extractor") {
    const s = d.CLINICAL_SNAPSHOTS[fixtureName];
    return JSON.stringify({
      patient_age: s.patient_age,
      patient_sex: s.patient_sex,
      primary_diagnosis: s.primary_diagnosis,
      biomarkers: s.biomarkers,
      performance_status: s.performance_status,
    }, null, 2);
  }
  if (agentKey === "policy_retriever") return JSON.stringify(d.POLICY_EXCERPTS[fixtureName], null, 2);
  if (agentKey === "necessity_reasoner") return JSON.stringify(d.NECESSITY[fixtureName], null, 2);
  if (agentKey === "decision_composer") {
    const dec = d.DECISIONS[fixtureName];
    return JSON.stringify({ verdict: dec.verdict, confidence: dec.confidence, rationale: dec.rationale, risk_flags: dec.risk_flags }, null, 2);
  }
  if (agentKey === "appeals_drafter") {
    return JSON.stringify({
      length_words: d.APPEAL_DRAFT.appeal_body.split(/\s+/).length,
      structured_arguments: d.APPEAL_DRAFT.structured_arguments.length,
      attachments: d.APPEAL_DRAFT.attachments_referenced,
    }, null, 2);
  }
  return "{}";
}

// Dark SVG DAG mini-visualization
function DagViz({ agents, statuses }) {
  const W = 360, H = 64;
  const padX = 18;
  const n = agents.length;
  const xs = agents.map((_, i) => padX + (i * (W - 2 * padX)) / Math.max(1, n - 1));
  const cy = 26;

  const fillFor = (st) =>
    st === "done"    ? "var(--accent-green)" :
    st === "running" ? "var(--accent-brand)" :
                       "var(--surface-raised-hi)";
  const strokeFor = (st) =>
    st === "done"    ? "var(--accent-green)" :
    st === "running" ? "var(--accent-brand-glow)" :
                       "var(--surface-border-hi)";
  const labelFor = (st) =>
    st === "pending" ? "var(--ink-muted)" : "var(--ink-body)";

  return (
    <div className="px-3 pt-2 pb-1 border-b border-surface-border bg-surface-raised">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="64" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="edge-sweep-dark" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7c5cff" stopOpacity="0.05" />
            <stop offset="50%" stopColor="#a78bfa" stopOpacity="1" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        {agents.slice(0, -1).map((a, i) => {
          const next = agents[i + 1];
          const stThis = statuses[a.key];
          const stNext = statuses[next.key];
          const lit = stThis === "done";
          return (
            <g key={`edge-${i}`}>
              <line
                x1={xs[i] + 7} y1={cy}
                x2={xs[i + 1] - 7} y2={cy}
                stroke={lit ? "#34d39966" : "#2a314744"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              {lit && stNext !== "done" && (
                <line
                  x1={xs[i] + 7} y1={cy}
                  x2={xs[i + 1] - 7} y2={cy}
                  stroke="url(#edge-sweep-dark)"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeDasharray="20 200"
                >
                  <animate attributeName="stroke-dashoffset" from="0" to="-220" dur="1.4s" repeatCount="indefinite" />
                </line>
              )}
            </g>
          );
        })}
        {(() => {
          const allPending = agents.every((a) => (statuses[a.key] || "pending") === "pending");
          return agents.map((a, i) => {
            const st = statuses[a.key] || "pending";
            const isFirstIdle = allPending && i === 0;
            return (
              <g key={a.key} style={{ willChange: st === "running" ? "transform" : "auto" }}>
                {isFirstIdle && (
                  <React.Fragment>
                    <circle cx={xs[i]} cy={cy} r="10" fill="none" stroke="#22d3ee" strokeWidth="1" opacity="0.45">
                      <animate attributeName="r" from="6" to="13" dur="2.2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.55" to="0" dur="2.2s" repeatCount="indefinite" />
                    </circle>
                    <circle cx={xs[i]} cy={cy} r="7.5" fill="#22d3ee" opacity="0.12">
                      <animate attributeName="opacity" values="0.08;0.18;0.08" dur="2.2s" repeatCount="indefinite" />
                    </circle>
                  </React.Fragment>
                )}
                {st === "running" && (
                  <React.Fragment>
                    <circle cx={xs[i]} cy={cy} r="11" fill="none" stroke={strokeFor(st)} strokeWidth="1.25" opacity="0.5">
                      <animate attributeName="r" from="6" to="14" dur="1.6s" repeatCount="indefinite" />
                      <animate attributeName="opacity" from="0.7" to="0" dur="1.6s" repeatCount="indefinite" />
                    </circle>
                    <circle cx={xs[i]} cy={cy} r="9" fill={strokeFor(st)} opacity="0.18" />
                  </React.Fragment>
                )}
                <circle
                  cx={xs[i]} cy={cy} r="5.5"
                  fill={isFirstIdle ? "#22d3ee" : fillFor(st)}
                  stroke={isFirstIdle ? "#22d3ee" : strokeFor(st)}
                  strokeWidth="1.5"
                  style={{
                    transition: "fill 280ms ease, stroke 280ms ease",
                    filter: st === "running" ? "drop-shadow(0 0 6px #7c5cffcc)" : st === "done" ? "drop-shadow(0 0 4px #34d39988)" : isFirstIdle ? "drop-shadow(0 0 5px #22d3ee99)" : "none",
                  }}
                />
                {st === "done" && (
                  <path d={`M ${xs[i] - 2.5} ${cy} l 2 2 l 3.5 -4`} stroke="#ffffff" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                )}
                <text
                  x={xs[i]} y={H - 8}
                  textAnchor="middle"
                  fill={labelFor(st)}
                  fontSize="8.5"
                  fontFamily="JetBrains Mono, monospace"
                  style={{ textTransform: "uppercase", letterSpacing: "0.08em", transition: "fill 280ms ease" }}
                >
                  {a.name.split(" ")[0]}
                </text>
              </g>
            );
          });
        })()}
      </svg>
    </div>
  );
}

function ReasoningTracePanel({ events, fixtureName, isRunning, costRunning }) {
  const data = window.CLINCASE_DATA;
  const verdict = data.DECISIONS[fixtureName].verdict;
  const agents = data.AGENT_SPECS.filter((a) => verdict === "DENY" || a.key !== "appeals_drafter");

  const statuses = {};
  agents.forEach((a) => {
    statuses[a.key] = statusOf(events, a.key).status;
  });

  const done = agents.filter((a) => statuses[a.key] === "done").length;
  const total = agents.length;

  const [expanded, setExpanded] = useStateT({});
  const scrollRef = useRefT(null);
  const prevDoneRef = useRefT(0);

  // Animated cost ticker
  const [displayedCost, setDisplayedCost] = useStateT(0);
  const costFromRef = useRefT(0);
  const costToRef = useRefT(0);
  const rafRef = useRefT(null);
  useEffectT(() => {
    cancelAnimationFrame(rafRef.current);
    costFromRef.current = displayedCost;
    costToRef.current = costRunning;
    const start = performance.now();
    const dur = 600;
    const tick = (t) => {
      const k = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      const v = costFromRef.current + (costToRef.current - costFromRef.current) * eased;
      setDisplayedCost(v);
      if (k < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [costRunning]);

  useEffectT(() => {
    if (done > prevDoneRef.current && scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      prevDoneRef.current = done;
    }
  }, [done]);

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl flex flex-col overflow-hidden h-full">
      <div className="px-4 pt-3 pb-3 border-b border-surface-border bg-surface-raised flex items-center justify-between">
        <div className="flex items-center gap-2">
          <I.Sparkles size={16} className="text-accent-brand-glow" />
          <h2 className="font-semibold text-sm tracking-tight text-ink-primary">Reasoning Trace</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono tabular-nums text-accent-cyan font-semibold inline-flex items-center gap-1">
            <I.DollarSign size={11} className="opacity-70" />
            {displayedCost.toFixed(4)}
          </span>
          <span className="text-xs font-mono text-ink-muted">
            <span className="text-ink-primary font-semibold">{done}</span>/{total}
          </span>
        </div>
      </div>

      <DagViz agents={agents} statuses={statuses} />

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-surface-bg/40">
        {agents.map((a, i) => {
          const st = statusOf(events, a.key);
          return (
            <AgentCard
              key={a.key}
              spec={a}
              status={st.status}
              run={st.run}
              fixtureName={fixtureName}
              index={i}
              expanded={!!expanded[a.key]}
              onToggle={() => setExpanded((e) => ({ ...e, [a.key]: !e[a.key] }))}
            />
          );
        })}
        {!isRunning && events.length === 0 && (
          <div className="rounded-xl border border-dashed border-surface-border-hi p-4 text-xs text-ink-body leading-relaxed">
            Click <span className="font-semibold text-ink-primary">Run ClinCase</span> to start the 5-agent pipeline. Events will stream here in real time.
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ReasoningTracePanel, runSimulatedStream, statusOf });
