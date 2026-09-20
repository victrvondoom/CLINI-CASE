/**
 * Kinetic heading — fades + rises each word in sequence. Words wrapped in
 * an "accent" array get the safe gradient text style (no invisibility bug
 * in light mode — falls back to solid accent-brand if background-clip fails).
 */
import clsx from "clsx";
import type { ReactNode } from "react";

interface Props {
  /** Array of word groups. Strings render plain; { accent: "minutes," } renders gradient. */
  parts: (string | { accent: string })[];
  className?: string;
  /** Per-word stagger in ms */
  staggerMs?: number;
  as?: "h1" | "h2" | "h3";
}

export function KineticHeading({
  parts,
  className,
  staggerMs = 60,
  as: Tag = "h1",
}: Props) {
  // Flatten to render units (a unit = a string OR an accented chunk).
  // Each word inside a unit becomes a separately-staggered <span>.
  const units = parts.map((p, i) => ({
    accent: typeof p === "object",
    text: typeof p === "object" ? p.accent : p,
    key: `${i}-${typeof p === "object" ? p.accent : p}`,
  }));

  let wordIndex = 0;
  const renderWords = (text: string, accent: boolean): ReactNode => {
    return text.split(/(\s+)/).map((tok, i) => {
      if (/^\s+$/.test(tok)) return <span key={i}>{tok}</span>;
      const idx = wordIndex++;
      return (
        <span
          key={i}
          className={clsx("kinetic-word", accent && "gradient-text-anim")}
          style={{ "--delay": `${idx * staggerMs}ms` } as React.CSSProperties}
        >
          {tok}
        </span>
      );
    });
  };

  return (
    <Tag className={className}>
      {units.map((u) => renderWords(u.text, u.accent))}
    </Tag>
  );
}
