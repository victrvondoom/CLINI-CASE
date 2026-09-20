import { Loader2, RotateCw } from "lucide-react";

import Reveal from "./Reveal";
import { HEALTH_URL, useSystemHealth } from "./useSystemHealth";

/**
 * A real, unauthenticated call to this deployment's health endpoint — the
 * landing page's one claim a visitor can verify without an account.
 */
export default function LiveStatus() {
  const { health, capabilities, latencyMs, loading, error, checkedAt, refresh } =
    useSystemHealth();

  return (
    <section
      id="live-status"
      style={{ position: "relative", zIndex: 1, padding: "6rem 1.5rem", scrollMarginTop: "5rem" }}
    >
      <div style={{ maxWidth: "760px", margin: "0 auto" }}>
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
          TRY IT
        </p>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.6rem, 3vw, 2.2rem)",
            fontWeight: 400,
            textAlign: "center",
            marginBottom: "2rem",
          }}
        >
          A real call to the running system, right now.
        </h2>

        <Reveal
          className="aperture-glass"
          style={{
            borderRadius: "8px",
            padding: "1.5rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.85rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "1rem",
              marginBottom: "1rem",
              flexWrap: "wrap",
            }}
          >
            <span style={{ opacity: 0.5 }}>~ curl {HEALTH_URL}</span>
            <button
              type="button"
              onClick={refresh}
              disabled={loading}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                background: "none",
                border: "1px solid rgba(236, 236, 236,0.15)",
                borderRadius: "4px",
                padding: "0.3rem 0.6rem",
                color: "var(--bone)",
                opacity: 0.8,
                fontFamily: "var(--font-mono)",
                fontSize: "0.72rem",
                cursor: loading ? "default" : "pointer",
              }}
            >
              {loading ? (
                <Loader2 size={12} className="aperture-spin" />
              ) : (
                <RotateCw size={12} />
              )}
              run again
            </button>
          </div>

          {loading && <div style={{ opacity: 0.6 }}>connecting...</div>}

          {error && !loading && (
            <div style={{ color: "var(--ember)" }}>
              request failed: {error}
              <div style={{ opacity: 0.5, marginTop: "0.5rem", fontSize: "0.78rem" }}>
                the backend isn&rsquo;t reachable from here -- start the API and hit
                &ldquo;run again&rdquo;.
              </div>
            </div>
          )}

          {health && !loading && !error && (
            <>
              <div style={{ color: "var(--cyan)", marginBottom: "0.6rem" }}>
                &#8618; {latencyMs}ms &middot; status: {health.status} &middot; db:{" "}
                {health.db}
                {checkedAt ? ` · ${new Date(checkedAt).toLocaleTimeString()}` : ""}
              </div>
              <pre
                style={{
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  opacity: 0.75,
                  lineHeight: 1.6,
                }}
              >
                {JSON.stringify(
                  {
                    healthz: health,
                    ...(capabilities
                      ? {
                          deployment: capabilities.deployment,
                          compliance: capabilities.compliance,
                        }
                      : {}),
                  },
                  null,
                  2,
                )}
              </pre>
            </>
          )}
        </Reveal>
      </div>
    </section>
  );
}
