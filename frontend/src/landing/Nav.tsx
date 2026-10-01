import { Moon, Sun } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import { useTheme } from "../lib/theme";

const ctaBase = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.78rem",
  padding: "0.5rem 0.95rem",
  border: "1px solid var(--cyan)",
  borderRadius: "6px",
  color: "var(--cyan)",
  boxShadow: "0 0 18px rgba(255, 255, 255,0.18)",
} as const;

export default function Nav() {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <header
      className="aperture-glass"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
        padding: "0.9rem 1.5rem",
        flexWrap: "wrap",
      }}
    >
      <Link
        to="/"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
          fontFamily: "var(--font-mono)",
          fontSize: "0.85rem",
          letterSpacing: "0.08em",
          color: "var(--bone)",
        }}
      >
        <img src="/clincase-mark.svg" alt="" width={20} height={20} aria-hidden="true" />
        CLINCASE
      </Link>

      <nav style={{ display: "flex", alignItems: "center", gap: "1.5rem", flexWrap: "wrap" }}>
        <a href="#how-it-works" className="aperture-nav-link">How it works</a>
        <a href="#live-status" className="aperture-nav-link">Live status</a>
        <a href="#metrics" className="aperture-nav-link">Metrics</a>
        <Link to="/interop" className="aperture-nav-link">Interop Gateway - Track 7</Link>
        <Link to="/onehealth" className="aperture-nav-link">One Health · Track 7</Link>

        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={theme === "dark" ? "Switch to light" : "Switch to dark"}
          style={{
            display: "inline-grid",
            placeItems: "center",
            width: "2rem",
            height: "2rem",
            borderRadius: "6px",
            border: "1px solid var(--overlay-border-faint)",
            background: "transparent",
            color: "var(--bone)",
            opacity: 0.75,
            cursor: "pointer",
          }}
        >
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        </button>

        {user ? (
          <Link to="/dashboard" style={ctaBase}>
            Go to dashboard
          </Link>
        ) : (
          <>
            <Link
              to="/login"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.78rem",
                color: "var(--bone)",
                opacity: 0.75,
              }}
            >
              Sign in
            </Link>
            <Link to="/signup" style={ctaBase}>
              Sign up
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
