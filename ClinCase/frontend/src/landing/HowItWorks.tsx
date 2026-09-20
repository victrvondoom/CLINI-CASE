import Reveal from "./Reveal";
import { useApertureOptional } from "./ApertureContext";
import { LIFECYCLE_STEPS } from "./tokens";

export default function HowItWorks() {
  // The one place the DOM content and the 3D object talk to each other:
  // hovering a lifecycle step makes the crystal visibly ripple. Optional so
  // the section still renders if it is ever used outside the provider.
  const aperture = useApertureOptional();

  return (
    <section
      id="how-it-works"
      style={{ position: "relative", zIndex: 1, padding: "6rem 1.5rem", scrollMarginTop: "5rem" }}
    >
      <div
        style={{
          maxWidth: "520px",
          marginLeft: "auto",
          marginRight: "clamp(1.5rem, 8vw, 8rem)",
        }}
      >
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            letterSpacing: "0.14em",
            color: "var(--violet)",
            marginBottom: "1.5rem",
          }}
        >
          01&ndash;06 &middot; AUTHORIZATION LIFECYCLE
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
          {LIFECYCLE_STEPS.map((step, i) => (
            <Reveal
              key={step.n}
              delay={i * 60}
              style={{ display: "flex", gap: "1rem" }}
              onMouseEnter={aperture?.triggerPulse}
              onFocus={aperture?.triggerPulse}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                  color: "var(--cyan)",
                  opacity: 0.7,
                  paddingTop: "0.15rem",
                }}
              >
                {step.n}
              </span>
              <div>
                <h3
                  style={{
                    fontSize: "1.05rem",
                    fontWeight: 600,
                    marginBottom: "0.35rem",
                    color: "var(--bone)",
                  }}
                >
                  {step.title}
                </h3>
                <p style={{ fontSize: "0.92rem", lineHeight: 1.6, opacity: 0.72 }}>
                  {step.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
