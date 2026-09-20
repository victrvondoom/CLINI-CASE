/**
 * Aurora background — three drifting blurred gradient blobs + a central
 * pulse blob. Used behind the Dashboard hero, the About page, etc.
 *
 * Tuned for visibility (not subtlety): 35-50% opacity, large blurs, two
 * concurrent animations (drift + pulse) so the hero feels alive even on a
 * static screenshot. Honors prefers-reduced-motion via the global CSS guard
 * applied to motion-safe:* classes.
 */
export function AuroraBackground() {
  return (
    <div
      aria-hidden
      className="absolute inset-0 overflow-hidden pointer-events-none"
    >
      {/* Indigo blob — top-left, drifts. Tasteful 18%. */}
      <div
        className="aurora-blob bg-accent-brand animate-aurora-drift"
        style={{
          width: 620,
          height: 620,
          top: -180,
          left: -120,
          opacity: 0.18,
          animationDelay: "0s",
        }}
      />
      {/* Cyan blob — top-right, drifts. Tasteful 14%. */}
      <div
        className="aurora-blob bg-accent-cyan animate-aurora-drift"
        style={{
          width: 520,
          height: 520,
          top: -80,
          right: -160,
          opacity: 0.14,
          animationDelay: "-12s",
        }}
      />
      {/* Violet blob — middle, drifts. Tasteful 12%. */}
      <div
        className="aurora-blob bg-accent-violet animate-aurora-drift"
        style={{
          width: 460,
          height: 460,
          top: 220,
          left: "30%",
          opacity: 0.12,
          animationDelay: "-22s",
        }}
      />
    </div>
  );
}
