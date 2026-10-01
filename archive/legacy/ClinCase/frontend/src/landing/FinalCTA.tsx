import { Link } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import Reveal from "./Reveal";

const primaryCta = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.85rem",
  padding: "0.85rem 1.5rem",
  borderRadius: "6px",
  background: "var(--cyan)",
  color: "var(--void)",
  fontWeight: 600,
  boxShadow: "0 0 28px rgba(255, 255, 255,0.28)",
} as const;

const secondaryCta = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.85rem",
  padding: "0.85rem 1.5rem",
  borderRadius: "6px",
  border: "1px solid rgba(236, 236, 236,0.2)",
  color: "var(--bone)",
} as const;

export default function FinalCTA() {
  const { user } = useAuth();

  return (
    <section
      style={{ position: "relative", zIndex: 1, padding: "8rem 1.5rem", textAlign: "center" }}
    >
      <Reveal style={{ maxWidth: "640px", margin: "0 auto" }}>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2rem, 4.5vw, 3.2rem)",
            fontWeight: 400,
            lineHeight: 1.15,
            marginBottom: "1rem",
          }}
        >
          Give the calls back to us.
        </h2>
        <p style={{ opacity: 0.75, fontSize: "1rem", lineHeight: 1.7, marginBottom: "2rem" }}>
          Start with one regimen and one payer. Watch a case go from referral to submitted
          authorization in a single sitting.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
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
        </div>
      </Reveal>
    </section>
  );
}
