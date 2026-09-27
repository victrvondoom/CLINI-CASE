/**
 * /aquahealth/one-health — the ecosystem → animal → community chain.
 *
 * One Health is the claim that the health of water, wildlife and people are
 * connected. That claim is easy to overstate, so this page is deliberately
 * careful: it shows *potential relevance* supported by named observations, and
 * never asserts that an environmental signal has caused a health effect.
 */
import { ArrowDown, Droplets, Fish, Users } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  Chip,
  EmptyState,
  ErrorNote,
  LoadingNote,
  PageHeader,
  StatusBadge,
  formatDate,
} from "../aquahealth/panels";
import type { OneHealthLayer, OneHealthView } from "../aquahealth/types";

const LAYER_ICON: Record<OneHealthLayer["layer"], ReactNode> = {
  ecosystem: <Droplets size={18} />,
  animal: <Fish size={18} />,
  community: <Users size={18} />,
};

const LAYER_ACCENT: Record<OneHealthLayer["layer"], string> = {
  ecosystem: "border-accent-cyan/40 bg-accent-cyan/5 text-accent-cyan",
  animal: "border-accent-green/40 bg-accent-green/5 text-accent-green",
  community: "border-accent-violet/40 bg-accent-violet/5 text-accent-violet",
};

export default function AquaOneHealth() {
  const [data, setData] = useState<OneHealthView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    aqua
      .oneHealth()
      .then(setData)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load the One Health view"),
      );
  }, []);

  if (error) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl">
        <ErrorNote message={error} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl">
        <LoadingNote label="Loading One Health view…" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <PageHeader
        eyebrow="AQUAHEALTH · ONE HEALTH"
        title="Ecosystem, animals and communities"
        description="How freshwater signals observed by citizens may relate to animal health and, potentially, to the people who use these waters."
      />

      <div className="space-y-5">
        {/* The chain */}
        <section>
          {data.chain.map((layer, i) => (
            <div key={layer.layer}>
              <div className={`rounded-2xl border p-5 ${LAYER_ACCENT[layer.layer]}`}>
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex items-center gap-2.5">
                    <span aria-hidden="true">{LAYER_ICON[layer.layer]}</span>
                    <h2 className="text-sm text-ink-primary">{layer.label}</h2>
                  </div>
                  <span className="text-data-numeric text-2xl text-ink-primary nums-tabular">
                    {layer.signal_count}
                    <span className="text-[11px] text-ink-muted ml-1.5">
                      signal{layer.signal_count === 1 ? "" : "s"}
                    </span>
                  </span>
                </div>

                <p className="text-[12px] text-ink-muted mt-2">{layer.description}</p>

                {Object.keys(layer.signals).length > 0 && (
                  <ul className="flex flex-wrap gap-1.5 mt-3">
                    {Object.entries(layer.signals).map(([k, n]) => (
                      <li key={k}>
                        <Chip className="bg-surface-raised text-ink-body border-surface-border">
                          {k.replace(/_/g, " ")} · {n}
                        </Chip>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {i < data.chain.length - 1 && (
                <div className="flex justify-center py-2" aria-hidden="true">
                  <ArrowDown size={18} className="text-ink-faint" />
                </div>
              )}
            </div>
          ))}
        </section>

        <div className="rounded-xl border border-accent-amber/30 bg-accent-amber/5 p-4">
          <p className="text-[11px] text-ink-muted">{data.disclaimer}</p>
        </div>

        {/* Pathways */}
        <section>
          <h2 className="text-sm text-ink-primary mb-3">
            Observations with potential community relevance
          </h2>

          {data.pathways.length === 0 ? (
            <EmptyState
              title="No potential pathways identified"
              detail="No observation currently reports a signal that the One Health agent links to animal or community relevance. That is a statement about the recorded observations, not a guarantee that no pathway exists."
            />
          ) : (
            <ul className="space-y-3">
              {data.pathways.map((p) => (
                <li
                  key={p.observation_id}
                  className="rounded-xl border border-surface-border bg-surface-raised p-4"
                >
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0">
                      <span className="text-mono-tech text-[11px] text-ink-muted">
                        {p.reference}
                      </span>
                      <span className="text-sm text-ink-primary ml-2">
                        {p.waterbody_name}
                      </span>
                      <div className="text-[10px] text-ink-faint mt-0.5">
                        {formatDate(p.observed_at)}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <StatusBadge status={p.status} size="sm" />
                      <Chip className="bg-surface-bg text-ink-muted border-surface-border">
                        {p.confidence} confidence
                      </Chip>
                    </div>
                  </div>

                  <p className="text-[12px] text-ink-body mt-3">{p.finding}</p>

                  {p.evidence.length > 0 && (
                    <div className="mt-2.5">
                      <div className="text-compact text-[10px] text-ink-faint">
                        Evidence
                      </div>
                      <ul className="mt-1 space-y-1">
                        {p.evidence.map((e, i) => (
                          <li
                            key={`${e.field}-${i}`}
                            className="text-[11px] text-ink-muted"
                          >
                            <span className="text-accent-cyan mr-1.5" aria-hidden="true">
                              •
                            </span>
                            <span className="text-ink-body">{e.label}</span> —{" "}
                            {e.interpretation}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {p.uncertainty && (
                    <p className="text-[11px] text-ink-faint mt-2.5 pt-2.5 border-t border-surface-border">
                      {p.uncertainty}
                    </p>
                  )}

                  <Link
                    to={`/aquahealth/observations/${p.observation_id}`}
                    className="mt-3 inline-block text-[11px] text-accent-cyan hover:underline"
                  >
                    Open full record
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
