/**
 * Tiny inline SVG sparkline. No chart library; pure path commands.
 * Uses the brand accent. Last point gets a small filled dot.
 */
import clsx from "clsx";

interface Props {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;     // tailwind color via currentColor; pass via className
  className?: string;
}

export function Sparkline({
  values,
  width = 100,
  height = 28,
  className,
}: Props) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (width - 4) + 2;
    const y = height - 2 - ((v - min) / range) * (height - 4);
    return [x, y] as const;
  });

  const path = points
    .map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`))
    .join(" ");

  const [lastX, lastY] = points[points.length - 1];

  return (
    <svg
      width={width}
      height={height}
      className={clsx("inline-block", className)}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden
    >
      <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={2.5} fill="currentColor" />
    </svg>
  );
}
