import { Link } from "react-router-dom";

import { DOMAINS } from "./tokens";

export default function Footer() {
  return (
    <footer
      style={{
        position: "relative",
        zIndex: 1,
        borderTop: "1px solid rgba(236, 236, 236,0.08)",
        padding: "3rem 1.5rem 2rem",
        fontFamily: "var(--font-mono)",
        fontSize: "0.75rem",
        color: "var(--bone)",
        opacity: 0.7,
      }}
    >
      <div
        style={{
          maxWidth: "1100px",
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          gap: "2.5rem",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div style={{ marginBottom: "0.6rem", letterSpacing: "0.08em" }}>CLINCASE</div>
          <div style={{ opacity: 0.6, maxWidth: "280px", lineHeight: 1.6 }}>
            You treat patients. We&rsquo;ll take the calls &mdash; prior authorization
            across {DOMAINS.length} cancer programs.
          </div>
        </div>
        <div style={{ display: "flex", gap: "3rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <span style={{ opacity: 0.5, marginBottom: "0.25rem" }}>PRODUCT</span>
            <a href="#how-it-works" className="aperture-nav-link">How it works</a>
            <a href="#live-status" className="aperture-nav-link">Live status</a>
            <a href="#metrics" className="aperture-nav-link">Metrics</a>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <span style={{ opacity: 0.5, marginBottom: "0.25rem" }}>ACCOUNT</span>
            <Link to="/login" className="aperture-nav-link">Sign in</Link>
            <Link to="/signup" className="aperture-nav-link">Sign up</Link>
          </div>
        </div>
      </div>
      <div style={{ maxWidth: "1100px", margin: "2rem auto 0", opacity: 0.4 }}>
        &copy; {new Date().getFullYear()} ClinCase.
      </div>
    </footer>
  );
}
