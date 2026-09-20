import Reveal from "./Reveal";
import { DOMAINS } from "./tokens";
import { useSystemHealth } from "./useSystemHealth";

export default function Integrations() {
  const { capabilities } = useSystemHealth();
  const deployment = capabilities?.deployment;

  return (
    <section style={{ position: "relative", zIndex: 1, padding: "6rem 1.5rem" }}>
      <div style={{ maxWidth: "800px", margin: "0 auto", textAlign: "center" }}>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            letterSpacing: "0.14em",
            color: "var(--violet)",
            marginBottom: "0.75rem",
          }}
        >
          WORKS WITH THE CHART YOU ALREADY KEEP
        </p>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.6rem, 3vw, 2.2rem)",
            fontWeight: 400,
            marginBottom: "2rem",
          }}
        >
          One workflow, every cancer program.
        </h2>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            justifyContent: "center",
            marginBottom: "2rem",
          }}
        >
          {DOMAINS.map((d, i) => (
            <Reveal
              key={d.key}
              as="span"
              delay={i * 40}
              className="aperture-glass"
              style={{
                display: "inline-block",
                borderRadius: "999px",
                padding: "0.5rem 1rem",
                fontFamily: "var(--font-mono)",
                fontSize: "0.78rem",
              }}
            >
              {d.label}
            </Reveal>
          ))}
        </div>

        {deployment?.llm_provider && (
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", opacity: 0.55 }}>
            reasoning model in this instance: {deployment.llm_provider}
            {deployment.bedrock_model_id ? ` / ${deployment.bedrock_model_id}` : ""}
          </p>
        )}
      </div>
    </section>
  );
}
