import type { ReactNode } from "react";

import CountUp from "./CountUp";
import Reveal from "./Reveal";
import { DOMAINS, LIFECYCLE_STEPS } from "./tokens";
import { useSystemHealth } from "./useSystemHealth";

export default function Metrics() {
  const { health, capabilities, latencyMs, loading } = useSystemHealth();

  const cards: { label: string; display: ReactNode }[] = [
    {
      label: "cancer programs covered",
      display: <CountUp value={DOMAINS.length} />,
    },
    {
      label: "lifecycle stages per case",
      display: <CountUp value={LIFECYCLE_STEPS.length} />,
    },
    {
      label: "CMS-0057-F clauses tracked",
      display: (
        <CountUp value={capabilities?.compliance?.cms_0057f_clauses_tracked ?? null} />
      ),
    },
    {
      label: "this health check",
      display: latencyMs != null ? `${latencyMs}ms` : "--",
    },
  ];

  return (
    <section
      id="metrics"
      style={{ position: "relative", zIndex: 1, padding: "6rem 1.5rem", scrollMarginTop: "5rem" }}
    >
      <div style={{ maxWidth: "900px", margin: "0 auto" }}>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            letterSpacing: "0.14em",
            color: "var(--cyan)",
            marginBottom: "0.75rem",
            textAlign: "center",
          }}
        >
          LIVE, NOT ROUNDED
        </p>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.6rem, 3vw, 2.2rem)",
            fontWeight: 400,
            marginBottom: "0.75rem",
            textAlign: "center",
          }}
        >
          Numbers from this running instance.
        </h2>
        <p
          style={{
            textAlign: "center",
            opacity: 0.6,
            marginBottom: "2.5rem",
            fontSize: "0.92rem",
          }}
        >
          {loading
            ? "fetching..."
            : health
              ? "read from this deployment just now -- refresh to see them change."
              : "backend unreachable right now."}
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "1.5rem",
          }}
        >
          {cards.map((card, i) => (
            <Reveal
              key={card.label}
              delay={i * 50}
              className="aperture-glass"
              style={{ borderRadius: "8px", padding: "1.5rem", textAlign: "center" }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "1.8rem",
                  color: "var(--cyan)",
                  marginBottom: "0.4rem",
                }}
              >
                {card.display}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.72rem",
                  opacity: 0.6,
                  letterSpacing: "0.04em",
                }}
              >
                {card.label}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
