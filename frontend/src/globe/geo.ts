/**
 * Pure geo/time helpers for the observation globe. No DOM, no three.js, so they are unit-testable.
 */

export interface LatLon {
  latitude: number;
  longitude: number;
}

export function validCoordinates(lat: number, lon: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
}

/** Privacy: coarsen a coordinate before displaying/sharing it. 2 decimals ≈ 1.1 km. */
export function coarsen(value: number, decimals = 2): number {
  const f = 10 ** decimals;
  return Math.round(value * f) / f;
}

/** Point on a sphere matching three.js SphereGeometry's equirectangular UV mapping. */
export function latLonToXYZ(lat: number, lon: number, radius = 1): [number, number, number] {
  const la = (lat * Math.PI) / 180;
  const phi = ((lon + 180) * Math.PI) / 180;
  return [-radius * Math.cos(la) * Math.cos(phi), radius * Math.sin(la), radius * Math.cos(la) * Math.sin(phi)];
}

/** Approximate sub-solar point (declination from day of year; no equation-of-time correction). */
export function subsolarPoint(date: Date): LatLon {
  const start = Date.UTC(date.getUTCFullYear(), 0, 0);
  const dayOfYear = Math.floor((date.getTime() - start) / 86_400_000);
  const latitude = 23.44 * Math.sin((2 * Math.PI * (dayOfYear - 81)) / 365);
  const hours = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  let longitude = -(hours - 12) * 15;
  if (longitude > 180) longitude -= 360;
  if (longitude < -180) longitude += 360;
  return { latitude, longitude };
}

/** Mean-solar UTC offset for a longitude. Approximation only; real zones follow political borders. */
export function solarOffsetHours(lon: number): number {
  return Math.round(lon / 15);
}

export function formatInZone(date: Date, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone,
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZoneName: "short",
    }).format(date);
  } catch {
    return "—";
  }
}

export function formatSolar(date: Date, lon: number): string {
  const off = solarOffsetHours(lon);
  const shifted = new Date(date.getTime() + off * 3_600_000);
  const hh = String(shifted.getUTCHours()).padStart(2, "0");
  const mm = String(shifted.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} (UTC${off >= 0 ? "+" : ""}${off}, solar)`;
}

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export const WORLD_CLOCK_ZONES = [
  "Asia/Kolkata",
  "Europe/Paris",
  "America/New_York",
  "Asia/Singapore",
  "Australia/Sydney",
  "Africa/Nairobi",
] as const;

export interface LandTopology {
  arcs: number[][][];
  transform?: { scale: [number, number]; translate: [number, number] };
  objects: Record<string, { geometries: Array<{ type: string; arcs: number[][][] | number[][] }> }>;
}

/** Decode a TopoJSON land object (world-atlas) into closed [lon, lat] rings. */
export function decodeLandRings(topo: LandTopology, object = "land"): Array<Array<[number, number]>> {
  const { scale, translate } = topo.transform ?? { scale: [1, 1], translate: [0, 0] };
  const arcs = topo.arcs.map((arc) => {
    let x = 0;
    let y = 0;
    return arc.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * scale[0] + translate[0], y * scale[1] + translate[1]] as [number, number];
    });
  });
  const ringOf = (indexes: number[]): Array<[number, number]> => {
    const out: Array<[number, number]> = [];
    for (const i of indexes) {
      const pts = i >= 0 ? arcs[i] : [...arcs[~i]].reverse();
      out.push(...(out.length ? pts.slice(1) : pts));
    }
    return out;
  };
  const rings: Array<Array<[number, number]>> = [];
  for (const g of topo.objects[object]?.geometries ?? []) {
    if (g.type === "Polygon") for (const r of g.arcs as number[][]) rings.push(ringOf(r));
    else if (g.type === "MultiPolygon")
      for (const poly of g.arcs as number[][][]) for (const r of poly) rings.push(ringOf(r));
  }
  return rings;
}
