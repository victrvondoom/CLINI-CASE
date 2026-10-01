import Reveal from "./Reveal";

export default function ProblemSection() {
  return (
    <section
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "70vh",
        display: "flex",
        alignItems: "center",
        padding: "6rem 1.5rem",
      }}
    >
      <Reveal style={{ maxWidth: "520px", marginLeft: "clamp(1.5rem, 8vw, 8rem)" }}>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            letterSpacing: "0.14em",
            color: "var(--ember)",
            marginBottom: "1rem",
          }}
        >
          WITHOUT CLINCASE
        </p>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.8rem, 3.4vw, 2.6rem)",
            fontWeight: 400,
            lineHeight: 1.15,
            marginBottom: "1.25rem",
          }}
        >
          The regimen is decided on Monday. The approval lands three weeks later.
        </h2>
        <p style={{ fontSize: "1rem", lineHeight: 1.75, opacity: 0.8 }}>
          A nurse navigator rebuilds the same clinical story for every payer, in every
          portal, on every call. A criterion is buried on page 9 of a policy that was
          revised last month. A denial arrives citing documentation that was in the chart
          the whole time &mdash; and the appeal starts the clock over. Meanwhile the
          patient waits, and the disease does not.
        </p>
      </Reveal>
    </section>
  );
}
