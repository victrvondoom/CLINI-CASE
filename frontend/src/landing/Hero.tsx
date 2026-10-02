import { Link } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import Reveal from "./Reveal";
import { useSystemHealth } from "./useSystemHealth";

const primaryCta = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.85rem",
  padding: "0.85rem 1.5rem",
  borderRadius: "6px",
  background: "var(--cyan)",
  color: "var(--void)",
  fontWeight: 600,
  boxShadow: "0 0 28px var(--overlay-glow)",
} as const;

const secondaryCta = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.85rem",
  padding: "0.85rem 1.5rem",
  borderRadius: "6px",
  border: "1px solid var(--overlay-border)",
  color: "var(--bone)",
} as const;

export default function Hero() {
  const { health, capabilities, latencyMs, loading } = useSystemHealth();
  const { user } = useAuth();

  return (
    <section
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "6rem 1.5rem 8rem",
      }}
    >
      <div style={{ maxWidth: "760px", margin: "0 auto", textAlign: "center" }}>
        <Reveal
          as="p"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            letterSpacing: "0.14em",
            color: "var(--cyan)",
            marginBottom: "1.25rem",
          }}
        >
          CLINI-CASE / ONE CONNECTED EVIDENCE JOURNEY
        </Reveal>

        <Reveal
          as="h1"
          delay={80}
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2.6rem, 6vw, 4.4rem)",
            lineHeight: 1.08,
            fontWeight: 400,
            color: "var(--bone)",
            marginBottom: "1rem",
          }}
        >
          From Evidence to Action.
          <br />
          One Connected Clinical Journey.
        </Reveal>

        <Reveal
          as="p"
          delay={140}
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "clamp(1rem, 2vw, 1.25rem)",
            letterSpacing: "0.01em",
            color: "var(--cyan)",
            marginBottom: "1.5rem",
          }}
        >
          One Health Interoperability Gateway
        </Reveal>

        <Reveal
          as="p"
          delay={200}
          style={{
            fontSize: "1.05rem",
            lineHeight: 1.65,
            color: "var(--bone)",
            opacity: 0.85,
            marginBottom: "2.25rem",
          }}
        >
          CLINI-CASE connects intake, evidence, interoperability, review, clinical context and follow-up in one traceable workflow.
        </Reveal>

        <Reveal
          delay={260}
          style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}
        >
          {user ? (
            <Link to="/dashboard" style={primaryCta}>
              Go to dashboard
            </Link>
          ) : (
            <>
              <Link to="/signup" style={primaryCta}>
                Sign up
              </Link>
              <Link to="/login" style={secondaryCta}>
                Sign in
              </Link>
            </>
          )}
          <a href="#how-it-works" style={secondaryCta}>
            See how it works
          </a>
        </Reveal>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: "2rem",
          left: 0,
          right: 0,
          textAlign: "center",
          padding: "0 1.5rem",
          fontFamily: "var(--font-mono)",
          fontSize: "0.78rem",
          color: "var(--bone)",
          opacity: 0.55,
        }}
      >
        {loading ? (
          "checking this deployment..."
        ) : health ? (
          <>
            api {health.status} &middot; database {health.db} &middot; {latencyMs}ms
            {capabilities?.deployment?.llm_provider
              ? ` · reasoning on ${capabilities.deployment.llm_provider}`
              : ""}
          </>
        ) : (
          "backend unreachable -- start the API to see live status"
        )}
      </div>
    </section>
  );
}
