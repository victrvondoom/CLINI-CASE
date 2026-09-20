/**
 * /architecture — live 5-layer enterprise architecture surface.
 *
 * Renders GET /api/v1/architecture/layers — the live descriptor of the
 * Experience / Orchestration & Policy Engine / Context Retrieval / GenAI
 * Gateway / Telemetry & Governance layers, plus External Integrations and
 * the AWS Foundation block.
 *
 * Doc pair: ops/architecture/TARGET_ARCHITECTURE.md
 *           ops/architecture/BUSINESS_USE_CASE.md
 *
 * The page is the single answer to "show me the architecture mapped to what's
 * actually running in this build, not on a slide."
 */
import {
  Activity,
  CircuitBoard,
  Cloud,
  Database,
  GitMerge,
  Layers as LayersIcon,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api, type ArchitectureDescriptor, type ArchitectureLayer } from "../lib/api";

const LAYER_ICON: Record<string, React.ReactNode> = {
  experience: <Activity size={14} />,
  orchestration: <GitMerge size={14} />,
  "context-retrieval": <Database size={14} />,
  "genai-gateway": <CircuitBoard size={14} />,
  "telemetry-governance": <ShieldCheck size={14} />,
  "external-integrations": <Network size={14} />,
};

const LAYER_ACCENT: Record<string, string> = {
  experience: "border-accent-cyan/40 bg-accent-cyan/5 text-accent-cyan",
  orchestration: "border-accent-brand/40 bg-accent-brand-soft/40 text-accent-brand",
  "context-retrieval": "border-accent-amber/40 bg-accent-amber/5 text-accent-amber",
  "genai-gateway": "border-accent-green/40 bg-accent-green/5 text-accent-green",
  "telemetry-governance": "border-accent-red/40 bg-accent-red/5 text-accent-red",
  "external-integrations": "border-surface-border bg-surface-panel/40 text-ink-body",
};

export default function Architecture() {
  const [arch, setArch] = useState<ArchitectureDescriptor | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getArchitectureLayers()
      .then(setArch)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="px-6 py-6 space-y-6">
      <header>
        <div className="text-compact text-[10px] text-accent-brand mb-1">
          CLINCASE · TARGET ENTERPRISE ARCHITECTURE
        </div>
        <h1 className="text-display-secondary text-2xl text-ink-primary leading-tight">
          5 named layers · live introspection
        </h1>
        <p className="text-ui-secondary text-sm text-ink-muted mt-1 max-w-3xl">
          Live descriptor from{" "}
          <code className="text-mono-tech text-xs">GET /api/v1/architecture/layers</code>. Every
          component listed below is in the running build — no mocks. Doc pair:{" "}
          <code className="text-mono-tech text-xs">ops/architecture/TARGET_ARCHITECTURE.md</code>.
        </p>
      </header>

      {error && (
        <div className="text-sm text-accent-red bg-accent-red/10 border border-accent-red/30 rounded p-3">
          {error}
        </div>
      )}

      {/* KPIs */}
      {arch && (
        <section className="bg-surface-raised border border-surface-border rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={14} className="text-accent-brand" />
            <h2 className="text-sm font-semibold text-ink-primary">Primary KPIs</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
            {arch.primary_kpis.map((k) => (
              <div
                key={k.id}
                className="border border-surface-border rounded-lg px-3 py-2 bg-surface-panel/40"
                title={`Baseline: ${k.baseline}\nMeasured at: ${k.measurement_endpoint}`}
              >
                <div className="text-[11px] font-medium text-ink-primary truncate">{k.name}</div>
                <div className="text-base font-semibold text-accent-green tabular-nums truncate mt-0.5">
                  {k.target_range}
                </div>
                <div className="text-[10px] text-mono-tech text-ink-faint truncate" title={k.baseline}>
                  vs {k.baseline}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Layers */}
      {arch &&
        arch.layers.map((layer) => (
          <LayerCard key={layer.id} layer={layer} />
        ))}

      {/* AWS Foundation */}
      {arch && (
        <section className="bg-surface-raised border border-surface-border rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Cloud size={14} className="text-ink-body" />
            <h2 className="text-sm font-semibold text-ink-primary">
              {arch.aws_foundation.name}
            </h2>
            <span className="ml-2 text-[10px] text-mono-tech px-2 py-1 rounded bg-surface-border text-ink-muted">
              region: {arch.aws_foundation.region_primary}
            </span>
          </div>
          <p className="text-[11px] text-ink-muted mb-2">{arch.aws_foundation.purpose}</p>
          <div className="flex flex-wrap gap-1.5">
            {arch.aws_foundation.services.map((s) => (
              <span
                key={s}
                className="text-[10px] text-mono-tech px-2 py-1 rounded bg-surface-panel border border-surface-border text-ink-body"
              >
                {s}
              </span>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-surface-border text-[10px] text-mono-tech text-ink-faint">
            Terraform modules:{" "}
            {arch.aws_foundation.terraform_modules.map((m, i) => (
              <span key={m}>
                <code className="text-accent-cyan">{m}</code>
                {i < arch.aws_foundation.terraform_modules.length - 1 ? " · " : ""}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Platform alignment */}
      {arch && (
        <section className="bg-accent-brand-soft/40 border border-accent-brand/30 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <LayersIcon size={14} className="text-accent-brand" />
            <h2 className="text-sm font-semibold text-ink-primary">Platform alignment</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            <AlignmentRow
              label="AI velocity gap addressed"
              value={arch.cognizant_alignment.ai_velocity_gap_addressed ? "yes" : "no"}
            />
            <AlignmentRow
              label="Three Vector Strategy"
              value={arch.cognizant_alignment.vector_strategy_classification.join(" · ")}
            />
            <AlignmentRow
              label="Agent Foundry stage"
              value={arch.cognizant_alignment.agent_foundry_stage}
            />
            <AlignmentRow
              label="Neuro-SAN compatible"
              value={arch.cognizant_alignment.neuro_san_compatible ? "yes" : "no"}
            />
            <AlignmentRow
              label="TriZetto AI Gateway native"
              value={arch.cognizant_alignment.trizetto_ai_gateway_native ? "yes" : "no"}
            />
            <AlignmentRow
              label="Anthropic partnership alignment"
              value={arch.cognizant_alignment.anthropic_partnership_alignment}
            />
          </div>
        </section>
      )}

      {arch && (
        <div className="text-[10px] text-mono-tech text-ink-faint">
          Generated {new Date(arch.asof_iso).toLocaleString()} · clincase {arch.clincase_version}
        </div>
      )}
    </div>
  );
}

function LayerCard({ layer }: { layer: ArchitectureLayer }) {
  const accent = LAYER_ACCENT[layer.id] ?? LAYER_ACCENT["external-integrations"];
  return (
    <section className={`border-2 rounded-2xl p-5 ${accent}`}>
      <div className="flex items-center gap-2 mb-2">
        {LAYER_ICON[layer.id] ?? <LayersIcon size={14} />}
        <h2 className="text-sm font-semibold text-ink-primary">{layer.name}</h2>
      </div>
      <p className="text-[12px] text-ink-body leading-snug mb-3">{layer.purpose}</p>

      {/* Specific quick facts per layer */}
      {layer.agents && (
        <div className="mb-3 text-[11px] text-mono-tech text-ink-body bg-surface-panel/40 border border-surface-border rounded px-2 py-1">
          {layer.agents.parents} parents · {layer.agents.sub_agents} sub-agents (
          {layer.agents.llm_backed_sub_agents} LLM · {layer.agents.deterministic_sub_agents}{" "}
          deterministic · {layer.agents.reflection_enabled_sub_agents} reflection)
        </div>
      )}
      {layer.active_backend && (
        <div className="mb-3 text-[11px] text-mono-tech text-ink-body bg-surface-panel/40 border border-surface-border rounded px-2 py-1">
          active backend: <code className="text-accent-amber">{layer.active_backend}</code>
        </div>
      )}
      {layer.models && (
        <div className="mb-3 text-[11px] text-mono-tech text-ink-body bg-surface-panel/40 border border-surface-border rounded px-2 py-1">
          primary <code className="text-accent-green">{layer.models.primary}</code> · fallback{" "}
          <code className="text-accent-green">{layer.models.fallback}</code>
        </div>
      )}
      {layer.compliance && (
        <div className="mb-3 text-[11px] text-mono-tech text-ink-body bg-surface-panel/40 border border-surface-border rounded px-2 py-1">
          {layer.compliance.in_force_today} of{" "}
          {layer.compliance.cms_0057f_clauses_tracked +
            layer.compliance.state_ai_laws_tracked.length}{" "}
          regulatory clauses in force today
        </div>
      )}

      <div className="text-[10px] text-compact text-ink-muted mb-1.5">
        Components ({layer.components.length})
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 mb-3">
        {layer.components.map((c) => (
          <div
            key={`${layer.id}-${c.name}`}
            className="text-[11px] bg-surface-panel/40 border border-surface-border rounded px-2 py-1"
          >
            <div className="text-ink-primary font-medium">{c.name}</div>
            <code className="text-[10px] text-mono-tech text-ink-muted">{c.path}</code>
          </div>
        ))}
      </div>

      {layer.endpoints && layer.endpoints.length > 0 && (
        <>
          <div className="text-[10px] text-compact text-ink-muted mb-1.5">
            API surface ({layer.endpoints.length})
          </div>
          <div className="flex flex-wrap gap-1 mb-3">
            {layer.endpoints.map((e) => (
              <code
                key={e}
                className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-surface-panel border border-surface-border text-ink-body"
              >
                {e}
              </code>
            ))}
          </div>
        </>
      )}

      <div className="pt-3 border-t border-surface-border">
        <div className="text-[10px] text-compact text-ink-muted mb-1">
          Business outcome
        </div>
        <p className="text-[11px] text-ink-body leading-snug">{layer.business_outcome}</p>
      </div>
    </section>
  );
}

function AlignmentRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-baseline gap-3 py-1 border-b border-accent-brand/20 last:border-0">
      <span className="text-ink-muted">{label}</span>
      <span className="text-ink-primary font-medium text-mono-tech text-[11px] text-right">{value}</span>
    </div>
  );
}
