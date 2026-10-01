import { apertureColors } from "./tokens";

/**
 * Fixed background for the landing page.
 *
 * The low-tier counterpart to the WebGL scene in Aperture3D.tsx. Landing.tsx
 * picks between the two: this renders when there is no WebGL context, on small
 * viewports, on low core counts, and under prefers-reduced-motion, and it is
 * also the Suspense fallback while the 3D chunk downloads. Same chaos -> order
 * composition and the same grayscale value language as the 3D scene, so the
 * swap is never a visual jump: it costs nothing to paint and never stutters.
 */
/* ---------------------------------------------------------------------------
   DNA helix, precomputed once at module scope so the component stays a pure
   render. Mirrors the geometry of the 3D HelixSystem: two strands a half
   period apart with base-pair rungs between them, rungs fading where the
   strands cross so the structure reads as having depth rather than as a flat
   ribbon.
   --------------------------------------------------------------------------- */
const HELIX_CENTER_Y = 400;
const HELIX_AMPLITUDE = 96;
const HELIX_WAVELENGTH = 320;

function strandPath(phase: number): string {
  let d = "";
  for (let x = -40; x <= 1240; x += 10) {
    const y = HELIX_CENTER_Y + HELIX_AMPLITUDE * Math.sin((x / HELIX_WAVELENGTH) * Math.PI * 2 + phase);
    d += (x === -40 ? "M" : "L") + x + " " + y.toFixed(1) + " ";
  }
  return d.trim();
}

const STRAND_A = strandPath(0);
const STRAND_B = strandPath(Math.PI);

const RUNGS = Array.from({ length: 49 }, (_, i) => {
  const x = -40 + i * 26;
  const t = (x / HELIX_WAVELENGTH) * Math.PI * 2;
  const offset = HELIX_AMPLITUDE * Math.sin(t);
  // Rungs are edge-on (and so nearly invisible) exactly where the strands cross.
  return {
    x,
    y1: HELIX_CENTER_Y + offset,
    y2: HELIX_CENTER_Y - offset,
    o: Math.abs(Math.cos(t)),
    // Signed depth: which of the two strands is currently nearer the viewer.
    d: Math.cos(t),
  };
});

export default function ApertureBackdrop() {
  return (
    <div
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none" }}
    >
      <svg
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid slice"
        viewBox="0 0 1200 800"
      >
        <defs>
          <radialGradient id="ap-void" cx="50%" cy="45%" r="70%">
            <stop offset="0%" stopColor={apertureColors.ink} />
            <stop offset="100%" stopColor={apertureColors.void} />
          </radialGradient>
          <linearGradient id="ap-facet" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={apertureColors.ember} stopOpacity="0.25" />
            <stop offset="50%" stopColor={apertureColors.violet} stopOpacity="0.35" />
            <stop offset="100%" stopColor={apertureColors.cyan} stopOpacity="0.3" />
          </linearGradient>
        </defs>

        <rect width="1200" height="800" fill="url(#ap-void)" />

        {/* DNA spine — the structural through-line the whole page is built on.
            Sits in its own layer so it can drift slower than the foreground,
            which is what makes the background read as layered rather than flat. */}
        <g className="aperture-backdrop-helix">
          <path
            d={STRAND_A}
            fill="none"
            stroke={apertureColors.bone}
            strokeOpacity="0.3"
            strokeWidth="1.4"
          />
          <path
            d={STRAND_B}
            fill="none"
            stroke={apertureColors.violet}
            strokeOpacity="0.36"
            strokeWidth="1.4"
          />
          {RUNGS.map((r) => (
            <line
              key={`rung-${r.x}`}
              x1={r.x}
              y1={r.y1}
              x2={r.x}
              y2={r.y2}
              stroke={apertureColors.bone}
              strokeOpacity={0.05 + r.o * 0.15}
              strokeWidth="1"
            />
          ))}
          {RUNGS.map((r) => (
            <g key={`pair-${r.x}`}>
              <circle
                cx={r.x}
                cy={r.y1}
                r={2.1}
                fill={apertureColors.bone}
                opacity={0.16 + (0.5 + 0.5 * r.d) * 0.4}
              />
              <circle
                cx={r.x}
                cy={r.y2}
                r={2.1}
                fill={apertureColors.violet}
                opacity={0.16 + (0.5 - 0.5 * r.d) * 0.4}
              />
            </g>
          ))}
        </g>


        <g className="aperture-backdrop-drift">
          <polygon
            points="600,260 720,330 700,470 560,500 480,410 520,300"
            fill="url(#ap-facet)"
            stroke={apertureColors.violet}
            strokeOpacity="0.5"
            strokeWidth="1"
          />
          {/* Chaos: unstructured referrals arriving on the left. */}
          {Array.from({ length: 14 }).map((_, i) => (
            <circle
              key={`chaos-${i}`}
              cx={140 + (i % 7) * 34 + Math.sin(i) * 12}
              cy={340 + Math.floor(i / 7) * 60 + Math.cos(i) * 10}
              r={2.2}
              fill={apertureColors.ember}
              opacity={0.6}
            />
          ))}
          {/* Order: decided, cited cases leaving on the right. */}
          {Array.from({ length: 16 }).map((_, i) => (
            <circle
              key={`order-${i}`}
              cx={820 + (i % 8) * 30}
              cy={380 + Math.floor(i / 8) * 26}
              r={2}
              fill={apertureColors.cyan}
              opacity={0.65}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}
