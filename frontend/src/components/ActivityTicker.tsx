/**
 * Live activity ticker — fixed-position scrolling band at the very top of the
 * app, above the TopBar. Ported 1:1 from the deployed clinical-healthcare
 * showcase (components.jsx ActivityTicker, lines 134-177).
 *
 * Layout:
 *   - Fixed top-0, h-7 (28px), full width
 *   - LIVE badge anchored left with solid backdrop + soft fade
 *   - Soft fade on right edge so the marquee disappears into the surface
 *   - Items duplicated [...items, ...items] for seamless loop via .marquee-track
 */
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Heart,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Tone = "emerald" | "amber" | "cyan" | "brand";

interface TickerItem {
  tone: Tone;
  Icon: LucideIcon;
  text: string;
}

const ITEMS: TickerItem[] = [
  { tone: "emerald", Icon: CheckCircle, text: "Deterministic demo fixtures available" },
  { tone: "brand",   Icon: Activity,    text: "Policy provenance is shown with each retrieved excerpt" },
  { tone: "amber",   Icon: AlertCircle, text: "Incomplete evidence routes to human review" },
  { tone: "emerald", Icon: Heart,       text: "Synthetic OncoTwin journey verified locally" },
  { tone: "cyan",    Icon: Zap,         text: "Production latency metrics require connected observability" },
  { tone: "brand",   Icon: Sparkles,    text: "Cloud document processing is disabled by default" },
  { tone: "emerald", Icon: ShieldCheck, text: "Live API status is shown in the landing health panel" },
];

const TONE_TEXT: Record<Tone, string> = {
  emerald: "text-accent-green",
  amber:   "text-accent-amber",
  cyan:    "text-accent-cyan",
  brand:   "text-accent-brand-glow",
};

export function ActivityTicker() {
  // Duplicate so the marquee loop is seamless.
  const all = [...ITEMS, ...ITEMS];

  return (
    <div className="fixed top-0 inset-x-0 z-40 h-7 overflow-hidden border-b border-surface-border bg-surface-raised/95 backdrop-blur-md hidden sm:block">
      {/* LIVE badge anchored left with solid backdrop above the marquee */}
      <div className="absolute left-0 top-0 bottom-0 z-20 flex items-center gap-1.5 pl-3 pr-4 bg-surface-raised">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-70 animate-ping" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent-green" />
        </span>
        <span className="text-[9px] text-compact text-ink-muted">Status</span>
        {/* Soft fade from solid badge backdrop into the scrolling track */}
        <span className="absolute inset-y-0 -right-6 w-6 bg-gradient-to-r from-surface-raised to-transparent pointer-events-none" />
      </div>

      {/* Right-edge fade so items dissolve into the surface */}
      <div className="absolute inset-y-0 right-0 z-10 w-24 pointer-events-none bg-gradient-to-l from-surface-raised via-surface-raised/70 to-transparent" />

      <div className="marquee-track flex items-center gap-10 h-full whitespace-nowrap pl-28">
        {all.map((it, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-2 text-[11px] text-mono-tech text-ink-body"
          >
            <it.Icon size={11} className={TONE_TEXT[it.tone]} />
            <span>{it.text}</span>
            <span className="text-ink-faint">—</span>
          </span>
        ))}
      </div>
    </div>
  );
}
