/**
 * /agents — Agents Meta-View.
 *
 * Datadog-APM-style transparency into the 7 agents (and their sub-agents) that power ClinCase.
 * Each agent: purpose, input → output schema, 24h stats, recent invocations.
 *
 * When someone asks "how does it actually work?", show
 * them this page. Demonstrates the LangGraph DAG observability + per-agent
 * health metrics that prove the system is enterprise-grade.
 */
import clsx from "clsx";
import { useCallback, useMemo, useState } from "react";
import {
  Activity,
  Cpu,
  CheckCircle2,
  ChevronDown,
  Clock,
  DollarSign,
  ExternalLink,
  FileText,
  Loader2,
  Network,
  PlayCircle,
  Plug,
  Shield,
} from "lucide-react";
import { authHeader } from "../lib/auth";
import {
  buildAgents,
  conditionalBranches,
  mcpArgs,
  type AgentState,
  type AgentView,
  type AgentsManifest,
  type McpTool,
  type MetricsReport,
  type PipelineGraph,
} from "../lib/agentsModel";
import { getJson } from "../lib/agentsApi";
import { useLive } from "../lib/useLive";

interface AgentRun {
  id: string;
  case_id: string;
  started_at: string;
  finished_at: string | null;
  latency_ms: number | null;
  model_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error_text: string | null;
}

const STATE_DOT: Record<AgentState, string> = {
  healthy: "bg-accent-green",
  running: "bg-accent-brand animate-pulse-soft",
  error:   "bg-accent-red",
  idle:    "bg-ink-faint",
};

const STATE_LABEL: Record<AgentState, string> = {
  healthy: "HEALTHY",
  running: "RUNNING",
  error:   "ERROR",
  idle:    "NO RUNS IN WINDOW",
};

function formatMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const WINDOWS = [
  { hours: 24, label: "24 h" },
  { hours: 24 * 7, label: "7 d" },
  { hours: 24 * 30, label: "30 d" },
];
const POLL_MS = 30_000;

export default function Agents() {
  const [hours, setHours] = useState(24);
  const manifest = useLive<AgentsManifest>(() => getJson("/api/v1/agents/manifest", false), [], 0);
  const metrics = useLive<MetricsReport>(() => getJson(`/api/v1/agents/metrics?hours=${hours}`), [hours], POLL_MS);
  const mcp = useLive<{ tools: McpTool[]; endpoint: string; spec_version: string }>(() => getJson("/mcp/manifest", false), [], 0);
  const agents = useMemo(() => (manifest.data ? buildAgents(manifest.data, metrics.data) : []), [manifest.data, metrics.data]);
  const winLabel = WINDOWS.find((w) => w.hours === hours)?.label ?? `${hours} h`;
  const models = useMemo(() => [...new Set(Object.values(metrics.data?.agents ?? {}).map((a) => a.model_id).filter((m): m is string => !!m))], [metrics.data]);

  return (
    <div className="px-6 py-6" data-testid="agents-page">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
            <Cpu size={22} className="text-accent-brand" />
            Agents
          </h1>
          <p className="text-sm text-ink-muted mt-1" data-testid="agents-summary">
            <span className="text-mono-tech text-ink-body">{manifest.data?.n_agents ?? "—"}</span> parent agents
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech text-ink-body">{manifest.data?.n_sub_agents ?? "—"}</span> sub-agents
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech text-ink-body">{metrics.data ? metrics.data.totals.invocations.toLocaleString() : "—"}</span> invocations / {winLabel}
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech text-ink-body">{metrics.data ? `$${metrics.data.totals.cost_usd.toFixed(2)}` : "—"}</span> est. cost / {winLabel}
            {models.length > 0 && (
              <>
                <span className="mx-2 text-ink-faint">·</span>
                <span className="text-accent-cyan text-mono-tech">{models.join(", ")}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div role="group" aria-label="Metrics window" className="inline-flex rounded-md border border-surface-border overflow-hidden">
            {WINDOWS.map((w) => (
              <button key={w.hours} type="button" aria-pressed={hours === w.hours} onClick={() => setHours(w.hours)}
                className={`px-2.5 py-1 ${hours === w.hours ? "bg-accent-brand/15 text-ink-primary" : "text-ink-muted hover:text-ink-primary"}`}>
                {w.label}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => { manifest.reload(); metrics.reload(); }} aria-label="Refresh agent data"
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-surface-border text-ink-muted hover:text-ink-primary">
            {metrics.loading ? <Loader2 size={12} className="animate-spin" /> : null}
            {metrics.updatedAt ? metrics.updatedAt.toLocaleTimeString() : "Refresh"}
          </button>
        </div>
      </header>

      {manifest.error && (
        <div role="alert" data-testid="agents-manifest-error" className="mb-4 rounded-lg border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-sm">
          Could not load the agent manifest: {manifest.error} <button type="button" className="underline" onClick={manifest.reload}>Retry</button>
        </div>
      )}
      {metrics.error && (
        <div role="alert" data-testid="agents-metrics-error" className="mb-4 rounded-lg border border-accent-amber/40 bg-accent-amber/10 px-3 py-2 text-sm">
          Live metrics unavailable ({metrics.error}). Agent definitions below are still current; run statistics show “—”.
        </div>
      )}
      {!manifest.data && manifest.loading && <p className="text-sm text-ink-muted" role="status">Loading agents…</p>}
      {metrics.data && metrics.data.totals.invocations === 0 && (
        <p data-testid="agents-no-runs" className="mb-4 text-xs text-ink-muted">
          No agent runs recorded in the last {winLabel} for your organisation — run a case and live statistics will appear here.
        </p>
      )}

      {manifest.data && (
        <>
          {/* DAG visual */}
          <section className="bg-surface-raised border border-surface-border rounded-2xl p-5 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Network size={16} className="text-accent-brand" />
              <h3 className="text-sm font-semibold text-ink-primary">LangGraph DAG</h3>
              <span className="text-[10px] text-compact text-ink-muted">compiled from the running graph</span>
            </div>
            <DagVisual agents={agents} graph={manifest.data.graph} />
            {conditionalBranches(manifest.data.graph).length > 0 && (
              <p className="mt-2 text-[11px] text-mono-tech text-ink-muted" data-testid="dag-branches">
                Conditional branches: {conditionalBranches(manifest.data.graph).join(" · ")}
              </p>
            )}
          </section>

          {/* Agent cards */}
          <section className="space-y-4">
            {agents.map((a) => (
              <AgentMetaCard key={a.id} agent={a} windowLabel={winLabel} />
            ))}
          </section>
        </>
      )}

      {/* MCP tool surface */}
      {mcp.data && <MCPSection tools={mcp.data.tools} endpoint={mcp.data.endpoint} spec={mcp.data.spec_version} />}
      {mcp.error && <p className="mt-6 text-xs text-ink-muted">MCP tool list unavailable: {mcp.error}</p>}
    </div>
  );
}

// =============================================================================

// MCP server card
// =============================================================================

function MCPSection({ tools, endpoint, spec }: { tools: McpTool[]; endpoint: string; spec: string }) {
  return (
    <section className="mt-6 bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <Plug size={16} className="text-accent-cyan" />
          <h3 className="text-sm font-semibold text-ink-primary">
            MCP tool surface
          </h3>
          <span className="text-[10px] text-compact text-ink-muted hidden md:inline">
            Model Context Protocol · JSON-RPC 2.0 · spec {spec}
          </span>
        </div>
        <a
          href="/mcp/manifest"
          target="_blank"
          rel="noreferrer"
          className="text-[11px] text-mono-tech text-accent-cyan hover:underline flex items-center gap-1"
        >
          /mcp/manifest
          <ExternalLink size={10} />
        </a>
      </div>

      <div className="px-5 py-4 border-b border-surface-border bg-accent-cyan/5">
        <div className="flex items-start gap-2 text-xs text-ink-body leading-relaxed">
          <Shield size={14} className="text-accent-cyan shrink-0 mt-0.5" />
          <div>
            ClinCase is an{" "}
            <strong className="text-ink-primary">MCP-compliant tool server</strong>.
            Claude Desktop, Cursor, and the{" "}
            <span className="text-accent-cyan text-mono-tech">
              TriZetto AI Gateway
            </span>{" "}
            (announced at AWS re:Invent 2025, IND210 — "MCP-compliant agent
            control") can discover and invoke these {tools.length}
            tools without bespoke integration. Endpoint:{" "}
            <code className="text-mono-tech text-[11px] px-1 py-0.5 rounded bg-surface-panel">
              POST {endpoint}
            </code>
            .
          </div>
        </div>
      </div>

      <div className="divide-y divide-surface-border">
        {tools.map((t) => (
          <div key={t.name} className="px-5 py-3 flex items-start gap-4">
            <code className="text-[12px] text-mono-tech text-accent-cyan font-medium shrink-0 w-36">
              {t.name}
            </code>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-ink-body leading-snug">{t.description}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {mcpArgs(t).map((a) => (
                  <span
                    key={a.name}
                    className="text-[10px] text-mono-tech text-ink-muted bg-surface-panel border border-surface-border rounded px-1.5 py-0.5"
                  >
                    {a.name}
                    <span className="text-ink-faint">: {a.type}</span>
                    {a.required && <span className="text-accent-amber"> *</span>}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="px-5 py-3 border-t border-surface-border bg-surface-panel/40">
        <div className="text-[10px] text-compact text-ink-muted mb-1">
          Example invocation
        </div>
        <pre className="text-[11px] text-mono-tech text-ink-body bg-surface-panel border border-surface-border rounded p-2 overflow-x-auto">
{`curl -X POST http://localhost:8000/mcp \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "policy_lookup",
      "arguments": {"payer_id": "aetna", "treatment": "trastuzumab"}
    }
  }'`}
        </pre>
      </div>
    </section>
  );
}

// =============================================================================
// DAG visual (pure SVG)
// =============================================================================

function DagVisual({ agents, graph }: { agents: AgentView[]; graph: PipelineGraph | null }) {
  const conditionalInto = new Set((graph?.edges ?? []).filter((e) => e.conditional).map((e) => e.target));
  const nodeY = 50;
  const nodeWidth = 120;
  const nodeHeight = 56;
  const gap = 20;
  const totalWidth = agents.length * (nodeWidth + gap) - gap + 40;
  const appealsX = (agents.length - 1) * (nodeWidth + gap) + 20;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${totalWidth} 130`}
        className="min-w-[640px] w-full"
        style={{ height: 130 }}
      >
        {/* Edges */}
        {agents.slice(0, -1).map((_, i) => {
          const x1 = (i + 1) * (nodeWidth + gap) - gap + 20;
          const x2 = x1 + gap;
          const isConditional = conditionalInto.has(agents[i + 1].id);
          return (
            <g key={i}>
              <line
                x1={x1}
                y1={nodeY + nodeHeight / 2}
                x2={x2}
                y2={nodeY + nodeHeight / 2}
                stroke={isConditional ? "rgb(var(--accent-amber))" : "rgb(var(--accent-brand))"}
                strokeWidth={2}
                strokeDasharray={isConditional ? "4 3" : undefined}
                opacity={0.7}
              />
              <polygon
                points={`${x2 - 4},${nodeY + nodeHeight / 2 - 3} ${x2},${nodeY + nodeHeight / 2} ${x2 - 4},${nodeY + nodeHeight / 2 + 3}`}
                fill={isConditional ? "rgb(var(--accent-amber))" : "rgb(var(--accent-brand))"}
                opacity={0.7}
              />
              {isConditional && (
                <text
                  x={x1 + (x2 - x1) / 2}
                  y={nodeY + nodeHeight / 2 - 6}
                  textAnchor="middle"
                  fill="rgb(var(--accent-amber))"
                  fontSize={9}
                  fontFamily="monospace"
                >
                  conditional
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {agents.map((a, i) => {
          const x = i * (nodeWidth + gap) + 20;
          const fill =
            a.state === "running"
              ? "rgb(var(--accent-brand) / 0.15)"
              : a.state === "error"
                ? "rgb(var(--accent-red) / 0.15)"
                : a.state === "idle"
                  ? "rgb(var(--surface-panel) / 0.6)"
                  : "rgb(var(--accent-green) / 0.15)";
          const stroke =
            a.state === "running"
              ? "rgb(var(--accent-brand))"
              : a.state === "error"
                ? "rgb(var(--accent-red))"
                : a.state === "idle"
                  ? "rgb(var(--ink-faint))"
                  : "rgb(var(--accent-green))";
          const isAppeals = conditionalInto.has(a.id);
          return (
            <g key={a.id}>
              <rect
                x={x}
                y={nodeY}
                width={nodeWidth}
                height={nodeHeight}
                rx={8}
                ry={8}
                fill={fill}
                stroke={stroke}
                strokeWidth={1.5}
                strokeDasharray={isAppeals ? "5 3" : undefined}
              />
              <text
                x={x + nodeWidth / 2}
                y={nodeY + 22}
                textAnchor="middle"
                fill="rgb(var(--ink-primary))"
                fontSize={11}
                fontWeight={600}
              >
                {a.display.split(" ")[0]}
              </text>
              <text
                x={x + nodeWidth / 2}
                y={nodeY + 36}
                textAnchor="middle"
                fill="rgb(var(--ink-muted))"
                fontSize={9}
              >
                {a.display.split(" ")[1] ?? ""}
              </text>
              <circle
                cx={x + 12}
                cy={nodeY + 12}
                r={4}
                fill={stroke}
                opacity={a.state === "running" ? 1 : 0.7}
              >
                {a.state === "running" && (
                  <animate attributeName="opacity" values="1;0.4;1" dur="1.6s" repeatCount="indefinite" />
                )}
              </circle>
              <text
                x={x + nodeWidth - 8}
                y={nodeY + 14}
                textAnchor="end"
                fill="rgb(var(--ink-faint))"
                fontSize={8}
                fontFamily="monospace"
              >
                {String(a.index).padStart(2, "0")}
              </text>
            </g>
          );
        })}

        {/* END marker */}
        <text
          x={appealsX + nodeWidth + 8}
          y={nodeY + nodeHeight / 2 + 4}
          fill="rgb(var(--ink-faint))"
          fontSize={10}
          fontFamily="monospace"
        >
          END
        </text>
      </svg>
    </div>
  );
}

// =============================================================================
// Agent meta card
// =============================================================================

interface PromptResponse {
  agent_name: string;
  prompt_path: string;
  content: string | null;
  byte_size: number;
  line_count?: number;
  error?: string;
}

interface ContractCheck {
  name: string;
  passed: boolean;
  detail: string;
}

interface ContractResult {
  agent_name: string;
  status: "passed" | "failed";
  checks_passed: number;
  checks_failed: number;
  elapsed_ms: number;
  checks: ContractCheck[];
}

function AgentMetaCard({ agent, windowLabel }: { agent: AgentView; windowLabel: string }) {
  const [runsOpen, setRunsOpen] = useState(false);
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);

  const [promptOpen, setPromptOpen] = useState(false);
  const [prompt, setPrompt] = useState<PromptResponse | null>(null);
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);

  const [contractRunning, setContractRunning] = useState(false);
  const [contractResult, setContractResult] = useState<ContractResult | null>(null);
  const [contractError, setContractError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    if (runsOpen) { setRunsOpen(false); return; }
    setRunsOpen(true);
    if (runs !== null) return; // already loaded
    setRunsLoading(true);
    setRunsError(null);
    try {
      const res = await fetch(`/api/v1/agents/${agent.id}/runs?limit=10`, {
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRuns(json.runs ?? []);
    } catch (e) {
      setRunsError(e instanceof Error ? e.message : "Failed to load runs");
    } finally {
      setRunsLoading(false);
    }
  }, [agent.id, runsOpen, runs]);

  const openPrompt = useCallback(async () => {
    setPromptOpen(true);
    if (prompt !== null) return; // already loaded
    setPromptLoading(true);
    setPromptError(null);
    try {
      const res = await fetch(`/api/v1/agents/${agent.id}/prompt`, {
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: PromptResponse = await res.json();
      setPrompt(json);
    } catch (e) {
      setPromptError(e instanceof Error ? e.message : "Failed to load prompt");
    } finally {
      setPromptLoading(false);
    }
  }, [agent.id, prompt]);

  const runContractTest = useCallback(async () => {
    if (contractRunning) return;
    setContractRunning(true);
    setContractError(null);
    setContractResult(null);
    try {
      const res = await fetch(`/api/v1/agents/${agent.id}/contract-test`, {
        method: "POST",
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: ContractResult = await res.json();
      setContractResult(json);
    } catch (e) {
      setContractError(e instanceof Error ? e.message : "Failed to run test");
    } finally {
      setContractRunning(false);
    }
  }, [agent.id, contractRunning]);

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <span className="text-xs text-mono-tech text-ink-faint">{String(agent.index).padStart(2, "0")}</span>
          <h3 className="font-semibold text-ink-primary">{agent.display}</h3>
          <span className={clsx("w-1.5 h-1.5 rounded-full", STATE_DOT[agent.state])} />
          <span className="text-[10px] text-compact text-ink-muted">
            {STATE_LABEL[agent.state]}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-mono-tech text-ink-muted">
          <span className="flex items-center gap-1">
            <Cpu size={11} />
            {agent.models.length ? agent.models.join(" + ") : "deterministic"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-0 divide-y lg:divide-y-0 lg:divide-x divide-surface-border">
        {/* Left: purpose + I/O + prompt */}
        <div className="p-5 space-y-3">
          <div>
            <div className="text-[10px] text-compact text-ink-muted mb-1">
              Purpose
            </div>
            <p className="text-sm text-ink-body leading-relaxed">{agent.purpose}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[10px] text-compact text-ink-muted mb-1">
                Input
              </div>
              <code className="text-[11px] text-mono-tech text-ink-primary bg-surface-panel px-2 py-1 rounded block break-words">
                {agent.input_type}
              </code>
            </div>
            <div>
              <div className="text-[10px] text-compact text-ink-muted mb-1">
                Output
              </div>
              <code className="text-[11px] text-mono-tech text-accent-brand bg-surface-panel px-2 py-1 rounded block">
                {agent.output_type}
              </code>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={openPrompt}
              className="text-[11px] font-medium px-2.5 py-1 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center gap-1.5"
            >
              <FileText size={11} />
              View prompt
            </button>
            <span className="text-[10px] text-mono-tech text-ink-faint truncate">
              {agent.llm_backed ? "LLM-backed" : "deterministic"}
            </span>
          </div>

          <div className="flex items-center gap-2 pt-0.5 flex-wrap">
            <button
              type="button"
              onClick={runContractTest}
              disabled={contractRunning}
              className="text-[11px] font-medium px-2.5 py-1 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center gap-1.5 disabled:opacity-60"
            >
              {contractRunning ? <Loader2 size={11} className="animate-spin" /> : <PlayCircle size={11} />}
              {contractRunning ? "Running…" : "Run contract test"}
            </button>
            {contractResult && (
              <span className={clsx(
                "text-[10px] text-mono-tech flex items-center gap-1",
                contractResult.status === "passed" ? "text-accent-green" : "text-accent-red",
              )}>
                {contractResult.status === "passed" ? <CheckCircle2 size={10} /> : <span className="text-accent-red">✗</span>}
                {contractResult.checks_passed}/{contractResult.checks_passed + contractResult.checks_failed} checks · {contractResult.elapsed_ms}ms
              </span>
            )}
            {!contractResult && !contractRunning && !contractError && (
              <span data-testid="contract-not-run" className="text-[10px] text-mono-tech text-ink-faint">
                contract test not run yet
              </span>
            )}
            {contractError && (
              <span className="text-[10px] text-mono-tech text-accent-red">{contractError}</span>
            )}
          </div>
          {contractResult && contractResult.status === "failed" && (
            <ul className="text-[10px] text-mono-tech text-ink-muted space-y-0.5 ml-1">
              {contractResult.checks.filter(c => !c.passed).map((c, i) => (
                <li key={i} className="text-accent-red">✗ {c.name}: {c.detail}</li>
              ))}
            </ul>
          )}

          {/* Sub-agents — internal decomposition of the parent */}
          <div className="pt-2 border-t border-surface-border/60">
            <div className="text-[10px] text-compact text-ink-muted mb-1.5">
              Sub-agents ({agent.sub_agents.length})
            </div>
            <ul className="space-y-1">
              {agent.sub_agents.map((s) => (
                <li key={s.name} className="flex items-baseline gap-2 text-[11px] leading-tight">
                  <code className="text-mono-tech text-accent-cyan whitespace-nowrap shrink-0">
                    {s.name}
                  </code>
                  <span className="text-ink-muted">— {s.role}</span>
                  {s.metrics && (
                    <span className="ml-auto text-[10px] text-mono-tech text-ink-faint whitespace-nowrap">
                      {s.metrics.invocations} runs · {formatMs(s.metrics.p50_ms)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right: 24h stats */}
        <div className="p-5">
          <div className="text-[10px] text-compact text-ink-muted mb-3">
            Live stats — last {windowLabel}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Stat label="Invocations" value={agent.metrics ? agent.metrics.invocations.toLocaleString() : "—"} />
            <Stat
              label="Success"
              value={agent.metrics?.success_pct != null ? `${agent.metrics.success_pct.toFixed(1)}%` : "—"}
              accent={agent.metrics?.success_pct == null ? undefined : agent.metrics.success_pct === 100 ? "green" : agent.metrics.success_pct >= 90 ? "amber" : "red"}
            />
            <Stat label="p50 latency" value={formatMs(agent.metrics?.p50_ms ?? null)} icon={Clock} />
            <Stat label="p95 latency" value={formatMs(agent.metrics?.p95_ms ?? null)} icon={Clock} />
            <Stat
              label="Mean tokens (in / out)"
              value={agent.metrics?.mean_input_tokens != null ? `${agent.metrics.mean_input_tokens} / ${agent.metrics.mean_output_tokens ?? "—"}` : "—"}
              mono
            />
            <Stat label={`Est. cost / ${windowLabel}`} value={agent.metrics ? `$${agent.metrics.cost_usd.toFixed(2)}` : "—"} icon={DollarSign} accent="cyan" />
          </div>
          <button
            type="button"
            onClick={loadRuns}
            className="w-full mt-4 text-[11px] font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center justify-center gap-1.5"
          >
            <Activity size={11} />
            {runsOpen ? "Hide recent runs" : "View 10 most recent runs →"}
            <ChevronDown size={11} className={clsx("transition-transform", runsOpen && "rotate-180")} />
          </button>
        </div>
      </div>

      {/* Recent runs panel */}
      {runsOpen && (
        <div className="border-t border-surface-border px-5 py-4">
          <div className="text-[10px] text-compact text-ink-muted mb-2">
            Recent runs — {agent.display}
          </div>
          {runsLoading && (
            <p className="text-xs text-ink-muted">Loading…</p>
          )}
          {runsError && (
            <p className="text-xs text-accent-red">{runsError}</p>
          )}
          {!runsLoading && !runsError && runs !== null && runs.length === 0 && (
            <p className="text-xs text-ink-muted">No runs recorded yet.</p>
          )}
          {!runsLoading && !runsError && runs && runs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px] text-mono-tech">
                <thead>
                  <tr className="text-ink-faint border-b border-surface-border/60">
                    <th className="text-left pb-1 pr-4 font-normal">Case</th>
                    <th className="text-left pb-1 pr-4 font-normal">Started</th>
                    <th className="text-right pb-1 pr-4 font-normal">Latency</th>
                    <th className="text-right pb-1 pr-4 font-normal">Tokens</th>
                    <th className="text-left pb-1 font-normal">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/40">
                  {runs.map((r) => (
                    <tr key={r.id} className="text-ink-body">
                      <td className="py-1 pr-4 text-accent-cyan truncate max-w-[120px]">{r.case_id.slice(0, 8)}…</td>
                      <td className="py-1 pr-4 text-ink-muted whitespace-nowrap">{new Date(r.started_at).toLocaleTimeString()}</td>
                      <td className="py-1 pr-4 text-right">{r.latency_ms != null ? formatMs(r.latency_ms) : "—"}</td>
                      <td className="py-1 pr-4 text-right text-ink-muted">{r.input_tokens != null && r.output_tokens != null ? `${r.input_tokens}/${r.output_tokens}` : "—"}</td>
                      <td className="py-1">
                        {r.error_text ? (
                          <span className="text-accent-red">ERR</span>
                        ) : (
                          <span className="text-accent-green">OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Prompt modal */}
      {promptOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setPromptOpen(false)}
        >
          <div
            className="bg-surface-raised border border-surface-border rounded-2xl w-full max-w-3xl max-h-[80vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-ink-primary truncate">
                  {agent.display} — system prompt
                </div>
                <div className="text-[10px] text-mono-tech text-ink-faint truncate">
                  {prompt?.prompt_path ?? `prompts/${agent.id}`}
                  {prompt?.line_count && (
                    <span className="ml-2">· {prompt.line_count} lines · {prompt.byte_size.toLocaleString()} B</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {prompt?.content && (
                  <button
                    type="button"
                    onClick={() => navigator.clipboard.writeText(prompt.content!)}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors"
                  >
                    Copy
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setPromptOpen(false)}
                  className="w-7 h-7 grid place-items-center rounded-md border border-surface-border text-ink-muted hover:text-ink-primary hover:bg-surface-raised-hi transition-colors"
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-surface-bg">
              {promptLoading && (
                <div className="text-sm text-ink-muted flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  Loading prompt for {agent.id}…
                </div>
              )}
              {promptError && (
                <div className="text-sm text-accent-red">{promptError}</div>
              )}
              {prompt?.error && (
                <div className="text-sm text-accent-red mb-2">{prompt.error}</div>
              )}
              {prompt?.content && (
                <pre className="text-xs text-mono-tech text-ink-body whitespace-pre-wrap leading-relaxed">
                  {prompt.content}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon: Icon,
  accent,
  mono,
}: {
  label: string;
  value: string;
  icon?: typeof Clock;
  accent?: "green" | "cyan" | "amber" | "red";
  mono?: boolean;
}) {
  const accentClass =
    accent === "green" ? "text-accent-green" :
    accent === "cyan"  ? "text-accent-cyan"  :
    accent === "amber" ? "text-accent-amber" :
    accent === "red"   ? "text-accent-red"   :
                         "text-ink-primary";
  return (
    <div>
      <div className="text-[10px] text-compact text-ink-muted flex items-center gap-1">
        {Icon && <Icon size={9} />}
        {label}
      </div>
      <div className={clsx("text-sm font-semibold nums-tabular mt-0.5", accentClass, mono && "text-mono-tech text-xs")}>
        {value}
      </div>
    </div>
  );
}
