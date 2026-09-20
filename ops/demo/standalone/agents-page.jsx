/* global window, React */
const { useState: useStateA, useEffect: useEffectA, useMemo: useMemoA } = React;

// ============================================================================
// Agents Meta-View (P1)
// 5-agent LangGraph DAG, animated traversal, click for details.
// ============================================================================

function AgentsPage({ navigate }) {
  const data = window.CLINCASE_DATA;
  const A = window.CLINCASE_AGENTS;
  const specs = data.AGENT_SPECS;

  const [selected, setSelected] = useStateA("necessity_reasoner");

  const sel = specs.find((s) => s.key === selected);
  const stats = A.STATS[selected];
  const recent = A.RECENT[selected];
  const prompt = A.SYSTEM_PROMPTS[selected];

  return (
    <div data-screen-label="agents" className="space-y-5">
      {/* Header */}
      <header>
        <Eyebrow>Knowledge · Agents</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          5-agent LangGraph DAG
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          Neuro-SAN <span className="font-mono text-ink-muted">AAOSA-aligned</span> · bounded responsibility · stateful continuity.
          Each agent owns one job, hands off a typed payload, and writes its trace to the audit ledger before exiting.
        </p>
      </header>

      {/* Two-column body — topology + details */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-5">
        <AgentTopology specs={specs} selected={selected} onSelect={setSelected} />
        <AgentDetail spec={sel} stats={stats} recent={recent} prompt={prompt} />
      </div>

      {/* Bottom KPI strip — one tile per agent */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        {specs.map((s) => (
          <AgentMiniTile
            key={s.key}
            spec={s}
            stats={A.STATS[s.key]}
            spark={A.SPARKS[s.key]}
            selected={s.key === selected}
            onSelect={() => setSelected(s.key)}
          />
        ))}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Topology — SVG nodes + edges with an animated dot traversing the path.
// Layout (5 nodes on a 720×360 grid):
//   CE --> PR --> NR --> DC --+--> (end)
//                              \--> AD (DENY branch, lower-right)
// ----------------------------------------------------------------------------
const NODES = [
  { key: "clinical_extractor", x: 100, y: 180, label: "Clinical\nExtractor", short: "CE" },
  { key: "policy_retriever",   x: 270, y: 180, label: "Policy\nRetriever",  short: "PR" },
  { key: "necessity_reasoner", x: 440, y: 180, label: "Necessity\nReasoner", short: "NR" },
  { key: "decision_composer",  x: 610, y: 180, label: "Decision\nComposer", short: "DC" },
  { key: "appeals_drafter",    x: 610, y: 320, label: "Appeals\nDrafter",   short: "AD" },
];
const EDGES = [
  { from: "clinical_extractor", to: "policy_retriever"   },
  { from: "policy_retriever",   to: "necessity_reasoner" },
  { from: "necessity_reasoner", to: "decision_composer"  },
  { from: "decision_composer",  to: "appeals_drafter", branch: "DENY" },
];

function AgentTopology({ specs, selected, onSelect }) {
  const byKey = (k) => NODES.find((n) => n.key === k);

  // 4-second loop. We traverse 4 edges = 4 segments at 1s each.
  // Use SMIL <animateMotion> on the dot along a single composite path.
  const compositePath = useMemoA(() => {
    // Path: CE -> PR -> NR -> DC -> AD, then jump back invisibly (handled via repeat).
    const pts = [
      byKey("clinical_extractor"),
      byKey("policy_retriever"),
      byKey("necessity_reasoner"),
      byKey("decision_composer"),
      byKey("appeals_drafter"),
    ];
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      // Last segment bends down to appeals drafter
      if (i === 4) {
        d += ` L ${pts[i].x} ${pts[i].y}`;
      } else {
        d += ` L ${pts[i].x} ${pts[i].y}`;
      }
    }
    return d;
  }, []);

  return (
    <section className="relative rounded-2xl bg-surface-raised border border-surface-border overflow-hidden">
      <div className="px-5 pt-4 pb-2 flex items-center justify-between border-b border-surface-border">
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">graph</div>
          <div className="text-[14px] font-semibold text-ink-primary">DAG topology</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-ink-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
            live · 4s loop
          </span>
        </div>
      </div>

      <div className="p-2">
        <svg viewBox="0 0 720 380" className="w-full h-auto" style={{ minHeight: 320 }}>
          <defs>
            <marker id="agent-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-faint)" />
            </marker>
            <filter id="agent-node-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Edges */}
          {EDGES.map((e, i) => {
            const a = byKey(e.from);
            const b = byKey(e.to);
            // Stop short of the node circles (radius 38) so the arrowhead lands cleanly.
            const dx = b.x - a.x, dy = b.y - a.y;
            const len = Math.hypot(dx, dy) || 1;
            const ux = dx / len, uy = dy / len;
            const x1 = a.x + ux * 42, y1 = a.y + uy * 42;
            const x2 = b.x - ux * 42, y2 = b.y - uy * 42;
            return (
              <g key={i}>
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="var(--surface-border-hi)"
                  strokeWidth="2"
                  strokeDasharray={e.branch === "DENY" ? "6 5" : "none"}
                  markerEnd="url(#agent-arrow)"
                />
                {e.branch && (
                  <text
                    x={(x1 + x2) / 2 + 12}
                    y={(y1 + y2) / 2 - 4}
                    fontSize="10"
                    fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                    fill="var(--accent-red)"
                    fontWeight="600"
                  >
                    if DENY
                  </text>
                )}
              </g>
            );
          })}

          {/* Animated traversal dot — invisible motion path + visible dot */}
          <path id="agent-dag-path" d={compositePath} fill="none" stroke="none" />
          <circle r="6" fill="var(--accent-cyan)" filter="url(#agent-node-glow)">
            <animateMotion dur="4s" repeatCount="indefinite" rotate="auto">
              <mpath href="#agent-dag-path" />
            </animateMotion>
            <animate attributeName="opacity" values="0.2;1;1;1;0.2" keyTimes="0;0.05;0.5;0.95;1" dur="4s" repeatCount="indefinite" />
          </circle>

          {/* Nodes */}
          {NODES.map((n) => {
            const isSel = n.key === selected;
            return (
              <g
                key={n.key}
                onClick={() => onSelect(n.key)}
                style={{ cursor: "pointer" }}
              >
                {/* Selection ring */}
                {isSel && (
                  <circle
                    cx={n.x} cy={n.y} r="46"
                    fill="none"
                    stroke="var(--accent-brand-glow)"
                    strokeWidth="2"
                    opacity="0.55"
                  >
                    <animate attributeName="r" values="46;52;46" dur="2.4s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.55;0.15;0.55" dur="2.4s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle
                  cx={n.x} cy={n.y} r="38"
                  fill={isSel ? "var(--brand-50)" : "var(--surface-raised-hi)"}
                  stroke={isSel ? "var(--accent-brand)" : "var(--surface-border-hi)"}
                  strokeWidth={isSel ? 2 : 1.5}
                />
                <text
                  x={n.x} y={n.y - 2}
                  textAnchor="middle"
                  fontSize="13"
                  fontWeight="700"
                  fill={isSel ? "var(--accent-brand)" : "var(--ink-primary)"}
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                >
                  {n.short}
                </text>
                <text
                  x={n.x} y={n.y + 12}
                  textAnchor="middle"
                  fontSize="9"
                  fill={isSel ? "var(--accent-brand)" : "var(--ink-muted)"}
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                >
                  {n.key.split("_").map((w) => w[0].toUpperCase()).join("")}
                </text>

                {/* Label below */}
                <text
                  x={n.x} y={n.y + 60}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--ink-primary)"
                >
                  {n.label.split("\n")[0]}
                </text>
                <text
                  x={n.x} y={n.y + 74}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--ink-primary)"
                >
                  {n.label.split("\n")[1]}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Caption strip */}
      <div className="px-5 py-3 border-t border-surface-border bg-surface-bg/50 flex items-center justify-between">
        <div className="text-[11px] font-mono text-ink-muted">
          Click a node → details pane updates · Animated dot = current traversal
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="inline-flex items-center gap-1.5 text-ink-muted">
            <span className="inline-block w-3 h-px bg-surface-border-hi" /> happy path
          </span>
          <span className="inline-flex items-center gap-1.5 text-ink-muted">
            <span className="inline-block w-3 h-px border-t border-dashed border-accent-red" /> DENY branch
          </span>
        </div>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// Details pane — selected agent: name, model, prompt preview, 24h stats, recent
// ----------------------------------------------------------------------------
function AgentDetail({ spec, stats, recent, prompt }) {
  return (
    <aside className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-surface-border">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">{spec.key}</div>
            <h2 className="mt-0.5 text-[18px] font-semibold text-ink-primary truncate">{spec.name}</h2>
          </div>
          <Pill tone="violet">
            <I.Cpu className="w-3 h-3" /> Sonnet 4.6
          </Pill>
        </div>
        <p className="mt-2 text-[12.5px] text-ink-body leading-relaxed">{spec.description}</p>
      </div>

      {/* Stats grid */}
      <div className="px-5 py-4 border-b border-surface-border grid grid-cols-3 gap-3">
        <DetailStat label="calls / 24h"   value={stats.calls_24h.toLocaleString()} />
        <DetailStat label="median"        value={`${(stats.median_ms / 1000).toFixed(2)}s`} />
        <DetailStat label="p95"           value={`${(stats.p95_ms / 1000).toFixed(2)}s`} />
        <DetailStat label="error rate"    value={`${(stats.error_rate * 100).toFixed(2)}%`}
          accent={stats.error_rate > 0.005 ? "amber" : "green"} />
        <DetailStat label="cost / 24h"    value={`$${stats.cost_24h.toFixed(2)}`} />
        <DetailStat label="tokens out"    value={`${(stats.tokens_out / 1000).toFixed(0)}k`} />
      </div>

      {/* System prompt preview */}
      <div className="px-5 py-3 border-b border-surface-border">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">system_prompt</div>
          <button className="text-[11px] font-mono text-ink-muted hover:text-ink-primary inline-flex items-center gap-1">
            <I.FileText className="w-3 h-3" /> view full
          </button>
        </div>
        <pre className="text-[11px] leading-[1.6] font-mono text-ink-body bg-surface-bg rounded-lg border border-surface-border p-3 overflow-x-auto whitespace-pre-wrap">
{prompt}
        </pre>
      </div>

      {/* Last 3 invocations */}
      <div className="px-5 py-3 flex-1">
        <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted mb-2">recent invocations</div>
        <div className="divide-y divide-surface-border">
          {recent.map((r, i) => {
            const tone = r.verdict === "DENY" ? "red"
                       : r.verdict === "REFER" ? "amber"
                       : r.verdict === "APPROVE" ? "green"
                       : r.verdict === "ambiguous" ? "amber"
                       : r.verdict === "drafted" ? "violet"
                       : "slate";
            return (
              <div key={i} className="py-2.5 flex items-start gap-3">
                <div className="font-mono text-[11px] text-ink-muted w-[110px] shrink-0">{r.case_id}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <Pill tone={tone}>{r.verdict}</Pill>
                    <span className="text-[10px] font-mono text-ink-faint">{ago(r.ts)}</span>
                    <span className="text-[10px] font-mono text-ink-faint">· {r.ms}ms</span>
                  </div>
                  <div className="text-[12px] text-ink-body truncate">{r.note}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

function DetailStat({ label, value, accent }) {
  const color = accent === "green" ? "text-accent-green"
              : accent === "amber" ? "text-accent-amber"
              : accent === "red"   ? "text-accent-red"
              : "text-ink-primary";
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">{label}</div>
      <div className={`mt-0.5 text-[16px] font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function ago(iso) {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

// ----------------------------------------------------------------------------
// Bottom strip — one mini-KPI tile per agent
// ----------------------------------------------------------------------------
function AgentMiniTile({ spec, stats, spark, selected, onSelect }) {
  return (
    <button
      onClick={onSelect}
      className={`text-left rounded-xl border px-3.5 py-3 transition-colors ${
        selected
          ? "bg-brand-50 border-accent-brand"
          : "bg-surface-raised border-surface-border hover:border-surface-border-hi"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-ink-muted truncate">{spec.key.replace(/_/g, " ")}</div>
        <span className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${stats.error_rate > 0.005 ? "bg-accent-amber" : "bg-accent-green"}`} />
      </div>
      <div className="mt-1 text-[15px] font-semibold text-ink-primary truncate">{spec.name}</div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <div>
          <div className="text-[18px] font-semibold tabular-nums text-ink-primary">{stats.calls_24h}</div>
          <div className="text-[10px] font-mono text-ink-muted">calls · {(stats.median_ms / 1000).toFixed(1)}s med</div>
        </div>
        <Sparkline values={spark} color="var(--accent-brand-glow)" />
      </div>
    </button>
  );
}

window.AgentsPage = AgentsPage;
