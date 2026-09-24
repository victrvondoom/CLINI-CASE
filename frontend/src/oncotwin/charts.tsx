/**
 * OncoTwin time-series chart — pure SVG, monochrome by design (ClinCase tokens):
 * series identity is carried by dash pattern + stroke weight + direct labels +
 * legend, never by colour alone. One y-axis per chart (no dual axes).
 *
 * Layers: horizontal reference bands (personal baseline / tier thresholds),
 * uncertainty bands, lines, point markers, vertical markers (now, events),
 * and a crosshair that snaps to the nearest day with a tooltip listing every
 * series at that day. A table view exposes the same numbers without hovering.
 */
import { Table2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export interface ChartLine {
  key: string;
  label: string;
  x: number[];
  y: (number | null)[];
  dash?: string;
  weight?: number;
  opacity?: number;
  points?: boolean;       // draw point markers (sparse data e.g. labs)
  directLabel?: boolean;
}

export interface ChartBand {
  key: string;
  label: string;
  x: number[];
  lo: (number | null)[];
  hi: (number | null)[];
  opacity?: number;
}

export interface HBand {
  from: number;
  to: number;
  label?: string;
  opacity?: number;
}

export interface VMark {
  x: number;
  label?: string;
  kind: "now" | "event" | "moment" | "alert";
}

interface Props {
  title?: string;
  lines: ChartLine[];
  bands?: ChartBand[];
  hbands?: HBand[];
  hlines?: { y: number; label: string }[];
  vmarks?: VMark[];
  xDomain: [number, number];
  yDomain?: [number, number];
  height?: number;
  format?: (v: number) => string;
  unit?: string;
  compact?: boolean;
  shadeAfter?: number;     // x after which the plot is a forecast
  ariaLabel: string;
}

function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(600);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => setW(Math.max(160, entries[0].contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function niceDomain(values: number[]): [number, number] {
  if (!values.length) return [0, 1];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08;
  return [lo - pad, hi + pad];
}

export function TimeChart({
  title, lines, bands = [], hbands = [], hlines = [], vmarks = [], xDomain, yDomain, height = 200,
  format = (v) => v.toFixed(1), unit = "", compact = false, shadeAfter, ariaLabel,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hoverX, setHoverX] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const m = compact ? { t: 6, r: 8, b: 16, l: 34 } : { t: 12, r: 92, b: 22, l: 44 };
  const W = width;
  const H = height;
  const iw = Math.max(10, W - m.l - m.r);
  const ih = Math.max(10, H - m.t - m.b);

  const [y0, y1] = useMemo(() => {
    if (yDomain) return yDomain;
    const vals: number[] = [];
    lines.forEach((l) => l.y.forEach((v) => v != null && vals.push(v)));
    bands.forEach((b) => { b.lo.forEach((v) => v != null && vals.push(v)); b.hi.forEach((v) => v != null && vals.push(v)); });
    hbands.forEach((h) => vals.push(h.from, h.to));
    return niceDomain(vals);
  }, [lines, bands, hbands, yDomain]);

  const sx = (x: number) => m.l + ((x - xDomain[0]) / Math.max(1e-9, xDomain[1] - xDomain[0])) * iw;
  const sy = (y: number) => m.t + ih - ((Math.min(Math.max(y, y0), y1) - y0) / Math.max(1e-9, y1 - y0)) * ih;

  const path = (xs: number[], ys: (number | null)[]) => {
    let d = "";
    let pen = false;
    xs.forEach((x, i) => {
      const y = ys[i];
      if (y == null || Number.isNaN(y)) { pen = false; return; }
      d += `${pen ? "L" : "M"}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const area = (xs: number[], lo: (number | null)[], hi: (number | null)[]) => {
    const pts = xs.map((x, i) => [x, lo[i], hi[i]] as const).filter(([, a, b]) => a != null && b != null);
    if (pts.length < 2) return "";
    const top = pts.map(([x, , b]) => `${sx(x).toFixed(1)},${sy(b as number).toFixed(1)}`).join("L");
    const bot = [...pts].reverse().map(([x, a]) => `${sx(x).toFixed(1)},${sy(a as number).toFixed(1)}`).join("L");
    return `M${top}L${bot}Z`;
  };

  const ticksY = useMemo(() => {
    const n = compact ? 3 : 4;
    return Array.from({ length: n + 1 }, (_, i) => y0 + ((y1 - y0) * i) / n);
  }, [y0, y1, compact]);
  const ticksX = useMemo(() => {
    const span = xDomain[1] - xDomain[0];
    const step = span > 14 ? 7 : span > 6 ? 2 : 1;
    const out: number[] = [];
    for (let x = Math.ceil(xDomain[0] / step) * step; x <= xDomain[1]; x += step) out.push(x);
    return out;
  }, [xDomain]);

  const allX = useMemo(() => {
    const s = new Set<number>();
    lines.forEach((l) => l.x.forEach((x) => s.add(x)));
    bands.forEach((b) => b.x.forEach((x) => s.add(x)));
    return [...s].sort((a, b) => a - b);
  }, [lines, bands]);

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = xDomain[0] + ((e.clientX - rect.left - m.l) / iw) * (xDomain[1] - xDomain[0]);
    let best: number | null = null;
    for (const cand of allX) if (best === null || Math.abs(cand - x) < Math.abs(best - x)) best = cand;
    setHoverX(best);
  };

  const readout = (x: number) => {
    const rows: { label: string; value: string; dash?: string }[] = [];
    lines.forEach((l) => {
      const i = l.x.indexOf(x);
      if (i >= 0 && l.y[i] != null) rows.push({ label: l.label, value: `${format(l.y[i] as number)}${unit}`, dash: l.dash });
    });
    bands.forEach((b) => {
      const i = b.x.indexOf(x);
      if (i >= 0 && b.lo[i] != null && b.hi[i] != null)
        rows.push({ label: b.label, value: `${format(b.lo[i] as number)}–${format(b.hi[i] as number)}${unit}` });
    });
    return rows;
  };

  const directLabels = compact ? [] : lines.filter((l) => l.directLabel).flatMap((l) => {
    let i = l.y.length - 1;
    while (i >= 0 && l.y[i] == null) i--;
    return i >= 0 ? [{ l, x: l.x[i], y: l.y[i] as number }] : [];
  });

  return (
    <div className="relative" ref={ref}>
      {(title || !compact) && (
        <div className="flex items-center justify-between mb-1">
          {title ? <div className="text-[11px] text-compact text-ink-muted">{title}</div> : <span />}
          {!compact && (
            <button type="button" onClick={() => setTable((v) => !v)}
              className="text-[10px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-accent-brand rounded px-1"
              aria-pressed={table} aria-label={table ? "Show chart" : "Show data table"}>
              <Table2 size={11} aria-hidden /> {table ? "Chart" : "Table"}
            </button>
          )}
        </div>
      )}
      {table ? (
        <DataTable lines={lines} bands={bands} format={format} />
      ) : (
        <svg width={W} height={H} role="img" aria-label={ariaLabel} className="text-ink-primary select-none block"
          onPointerMove={onMove} onPointerLeave={() => setHoverX(null)}>
          {shadeAfter != null && shadeAfter < xDomain[1] && (
            <rect x={sx(Math.max(shadeAfter, xDomain[0]))} y={m.t}
              width={Math.max(0, sx(xDomain[1]) - sx(Math.max(shadeAfter, xDomain[0])))}
              height={ih} fill="currentColor" opacity={0.035} />
          )}
          {hbands.map((h, i) => (
            <g key={`hb${i}`}>
              <rect x={m.l} width={iw} y={sy(Math.max(h.from, h.to))}
                height={Math.max(0, sy(Math.min(h.from, h.to)) - sy(Math.max(h.from, h.to)))}
                fill="currentColor" opacity={h.opacity ?? 0.07} />
              {h.label && !compact && (
                <text x={m.l + iw + 4} y={sy((h.from + h.to) / 2) + 3} fontSize={9} className="fill-ink-muted">{h.label}</text>
              )}
            </g>
          ))}
          {ticksY.map((t) => (
            <g key={`ty${t}`}>
              <line x1={m.l} x2={m.l + iw} y1={sy(t)} y2={sy(t)} stroke="currentColor" strokeOpacity={0.07} />
              <text x={m.l - 4} y={sy(t) + 3} fontSize={9} textAnchor="end" className="fill-ink-muted">{format(t)}</text>
            </g>
          ))}
          {ticksX.map((t) => (
            <text key={`tx${t}`} x={sx(t)} y={H - 6} fontSize={9} textAnchor="middle" className="fill-ink-muted">D{t}</text>
          ))}
          {hlines.map((h, i) => (
            <g key={`hl${i}`}>
              <line x1={m.l} x2={m.l + iw} y1={sy(h.y)} y2={sy(h.y)} stroke="currentColor" strokeOpacity={0.45} strokeDasharray="4 3" />
              {!compact && <text x={m.l + iw + 4} y={sy(h.y) + 3} fontSize={9} className="fill-ink-muted">{h.label}</text>}
            </g>
          ))}
          {bands.map((b) => (
            <path key={b.key} d={area(b.x, b.lo, b.hi)} fill="currentColor" opacity={b.opacity ?? 0.12} />
          ))}
          {lines.map((l) => (
            <g key={l.key} opacity={l.opacity ?? 1}>
              <path d={path(l.x, l.y)} fill="none" stroke="currentColor" strokeWidth={l.weight ?? 2}
                strokeDasharray={l.dash} strokeLinecap="round" strokeLinejoin="round" />
              {l.points && l.x.map((x, i) => l.y[i] != null && (
                <circle key={i} cx={sx(x)} cy={sy(l.y[i] as number)} r={4} fill="currentColor"
                  stroke="rgb(var(--surface-raised))" strokeWidth={2} />
              ))}
            </g>
          ))}
          {directLabels.map(({ l, x, y }) => (
            <text key={`dl${l.key}`} x={Math.min(sx(x) + 6, m.l + iw + 4)} y={sy(y) + 3} fontSize={10} className="fill-ink-body">
              {l.label}
            </text>
          ))}
          {vmarks.map((v, i) => (
            <g key={`vm${i}`}>
              <line x1={sx(v.x)} x2={sx(v.x)} y1={m.t} y2={m.t + ih} stroke="currentColor"
                strokeOpacity={v.kind === "now" ? 0.8 : 0.35} strokeWidth={v.kind === "now" ? 1.5 : 1}
                strokeDasharray={v.kind === "now" ? undefined : v.kind === "alert" ? "1 2" : "3 3"} />
              {v.kind === "alert" && <path d={`M${sx(v.x)},${m.t + 1}l4,-6h-8z`} fill="currentColor" />}
              {v.label && !compact && (
                <text x={sx(v.x) + 3} y={m.t + 8} fontSize={9} className="fill-ink-muted">{v.label}</text>
              )}
            </g>
          ))}
          {hoverX != null && (
            <line x1={sx(hoverX)} x2={sx(hoverX)} y1={m.t} y2={m.t + ih} stroke="currentColor" strokeOpacity={0.5} strokeWidth={1} />
          )}
        </svg>
      )}
      {!table && hoverX != null && (
        <div
          className="pointer-events-none absolute z-20 rounded-md border border-surface-border bg-surface-raised px-2.5 py-1.5 text-[11px]"
          style={{ left: Math.min(Math.max(sx(hoverX) + 10, 0), Math.max(0, W - 200)), top: 18, minWidth: 150, boxShadow: "var(--shadow-pop)" }}
          role="status"
        >
          <div className="text-[10px] text-mono-tech text-ink-muted mb-0.5">Day {hoverX}</div>
          {readout(hoverX).map((r) => (
            <div key={r.label} className="flex items-center gap-2">
              <svg width="14" height="6" aria-hidden className="text-ink-primary shrink-0">
                <line x1="0" x2="14" y1="3" y2="3" stroke="currentColor" strokeWidth={2} strokeDasharray={r.dash} />
              </svg>
              <span className="text-ink-primary font-semibold nums-tabular">{r.value}</span>
              <span className="text-ink-muted truncate">{r.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DataTable({ lines, bands, format }: { lines: ChartLine[]; bands: ChartBand[]; format: (v: number) => string }) {
  const xs = [...new Set([...lines.flatMap((l) => l.x), ...bands.flatMap((b) => b.x)])].sort((a, b) => a - b);
  return (
    <div className="max-h-56 overflow-auto border border-surface-border rounded-md">
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-surface-panel">
          <tr>
            <th className="text-left px-2 py-1 font-medium text-ink-muted">Day</th>
            {lines.map((l) => <th key={l.key} className="text-right px-2 py-1 font-medium text-ink-muted">{l.label}</th>)}
            {bands.map((b) => <th key={b.key} className="text-right px-2 py-1 font-medium text-ink-muted">{b.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {xs.map((x) => (
            <tr key={x} className="border-t border-surface-border/60">
              <td className="px-2 py-0.5 text-mono-tech">D{x}</td>
              {lines.map((l) => {
                const i = l.x.indexOf(x);
                const v = i >= 0 ? l.y[i] : null;
                return <td key={l.key} className="text-right px-2 py-0.5 nums-tabular">{v == null ? "—" : format(v)}</td>;
              })}
              {bands.map((b) => {
                const i = b.x.indexOf(x);
                const ok = i >= 0 && b.lo[i] != null && b.hi[i] != null;
                return (
                  <td key={b.key} className="text-right px-2 py-0.5 nums-tabular">
                    {ok ? `${format(b.lo[i] as number)}–${format(b.hi[i] as number)}` : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; dash?: string; kind?: "line" | "band" | "point" }[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-ink-muted">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <svg width="16" height="8" aria-hidden className="text-ink-primary">
            {it.kind === "band" ? <rect x="0" y="0" width="16" height="8" fill="currentColor" opacity={0.15} />
              : it.kind === "point" ? <circle cx="8" cy="4" r="3.5" fill="currentColor" />
              : <line x1="0" x2="16" y1="4" y2="4" stroke="currentColor" strokeWidth={2} strokeDasharray={it.dash} />}
          </svg>
          {it.label}
        </span>
      ))}
    </div>
  );
}
