import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import type { TraceEvent } from "../lib/types";
import { AgentCard, type AgentStatus } from "./AgentCard";

const AGENT_ORDER = [
  "clinical_extractor",
  "policy_retriever",
  "necessity_reasoner",
  "decision_composer",
  "appeals_drafter",
] as const;

const AGENT_DISPLAY: Record<string, string> = {
  clinical_extractor: "Clinical Extractor",
  policy_retriever: "Policy Retriever",
  necessity_reasoner: "Necessity Reasoner",
  decision_composer: "Decision Composer",
  appeals_drafter: "Appeals Drafter",
};

const AGENT_DESCRIPTIONS: Record<string, string> = {
  clinical_extractor: "Parses FHIR + physician notes into a structured clinical snapshot.",
  policy_retriever: "Retrieves payer-specific medical policy excerpts for the requested treatment.",
  necessity_reasoner: "Matches every policy criterion against the clinical evidence.",
  decision_composer: "Produces APPROVE / DENY / REFER with a full citation chain.",
  appeals_drafter: "Activated on DENY — drafts an evidence-grounded appeal letter.",
};

interface AgentState {
  name: string;
  status: AgentStatus;
  startedAt?: number;
  finishedAt?: number;
  latencyMs?: number;
  modelId?: string | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  output?: Record<string, unknown>;
  error?: string;
}

interface Props {
  events: TraceEvent[];
  isRunning: boolean;
}

export function ReasoningTracePanel({ events, isRunning }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Reduce events into per-agent state
  const agents = useMemo(() => {
    const map = new Map<string, AgentState>();

    // Pre-populate the canonical 4 agents (extractor → retriever → reasoner → decision).
    // Appeals only appears if it actually runs (DENY path).
    for (const name of AGENT_ORDER.slice(0, 4)) {
      map.set(name, { name, status: "pending" });
    }

    for (const ev of events) {
      switch (ev.type) {
        case "agent_started": {
          map.set(ev.agent_name, {
            ...(map.get(ev.agent_name) ?? { name: ev.agent_name }),
            name: ev.agent_name,
            status: "running",
            startedAt: ev.ts,
          });
          break;
        }
        case "agent_finished": {
          const prev = map.get(ev.agent_name);
          map.set(ev.agent_name, {
            ...(prev ?? { name: ev.agent_name }),
            name: ev.agent_name,
            status: "done",
            finishedAt: ev.ts,
            latencyMs: ev.latency_ms,
            modelId: ev.model_id,
            output: ev.output,
            inputTokens:
              ((ev.output as { input_tokens?: number })?.input_tokens as number) ??
              null,
            outputTokens:
              ((ev.output as { output_tokens?: number })?.output_tokens as number) ??
              null,
          });
          break;
        }
        case "agent_error": {
          const prev = map.get(ev.agent_name);
          map.set(ev.agent_name, {
            ...(prev ?? { name: ev.agent_name }),
            name: ev.agent_name,
            status: "error",
            error: ev.error,
          });
          break;
        }
        case "done":
          break;
      }
    }

    // Sort: known agents in canonical order first, then any extras
    const known = AGENT_ORDER.filter((n) => map.has(n)).map((n) => map.get(n)!);
    const extras = Array.from(map.values()).filter(
      (a) => !AGENT_ORDER.includes(a.name as (typeof AGENT_ORDER)[number]),
    );
    return [...known, ...extras];
  }, [events]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [agents]);

  return (
    <div className="bg-neutral-50 border border-neutral-200 rounded-xl flex flex-col h-full">
      <div className="px-5 py-3 border-b border-neutral-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-brand-600" />
          <h3 className="font-semibold text-neutral-900">Reasoning Trace</h3>
        </div>
        <div className="text-xs text-neutral-500 text-mono-tech">
          {agents.filter((a) => a.status === "done").length} / {agents.length} done
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto p-4 space-y-3">
        {!isRunning && agents.every((a) => a.status === "pending") && (
          <div className="text-center py-12 text-neutral-400">
            <p className="text-sm">Click "Run ClinCase" to start the agent pipeline.</p>
          </div>
        )}

        {agents.map((agent) => (
          <AgentCard
            key={agent.name}
            name={agent.name}
            displayName={AGENT_DISPLAY[agent.name] ?? agent.name}
            description={AGENT_DESCRIPTIONS[agent.name]}
            status={agent.status}
            latencyMs={agent.latencyMs ?? null}
            modelId={agent.modelId ?? null}
            inputTokens={agent.inputTokens ?? null}
            outputTokens={agent.outputTokens ?? null}
            error={agent.error ?? null}
            output={agent.output}
          />
        ))}
      </div>
    </div>
  );
}
