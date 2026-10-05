import { describe, expect, it } from "vitest";

import {
  browserTimeZone,
  coarsen,
  decodeLandRings,
  formatInZone,
  formatSolar,
  latLonToXYZ,
  solarOffsetHours,
  subsolarPoint,
  validCoordinates,
} from "../src/globe/geo";

describe("globe geo helpers", () => {
  it("validates coordinate ranges", () => {
    expect(validCoordinates(13.08, 80.27)).toBe(true);
    expect(validCoordinates(91, 0)).toBe(false);
    expect(validCoordinates(0, -181)).toBe(false);
    expect(validCoordinates(Number.NaN, 0)).toBe(false);
  });

  it("coarsens coordinates to ~1 km for privacy", () => {
    expect(coarsen(13.082691)).toBe(13.08);
    expect(coarsen(-80.2707, 1)).toBe(-80.3);
  });

  it("maps lat/lon onto the unit sphere", () => {
    const [x, y, z] = latLonToXYZ(37, -122, 1);
    expect(Math.hypot(x, y, z)).toBeCloseTo(1, 6);
    expect(latLonToXYZ(90, 0)[1]).toBeCloseTo(1, 6);
  });

  it("puts the sub-solar point at lon 0 at 12:00 UTC", () => {
    const s = subsolarPoint(new Date(Date.UTC(2026, 5, 21, 12, 0, 0)));
    expect(s.longitude).toBeCloseTo(0, 6);
    expect(s.latitude).toBeGreaterThan(22);
  });

  it("formats time across IANA zones", () => {
    const d = new Date(Date.UTC(2026, 9, 4, 3, 45));
    expect(formatInZone(d, "Asia/Kolkata")).toContain("09:15");
    expect(formatInZone(d, "UTC")).toContain("03:45");
    expect(formatInZone(d, "Not/AZone")).toBe("—");
    expect(browserTimeZone().length).toBeGreaterThan(0);
  });

  it("approximates solar time from longitude", () => {
    expect(solarOffsetHours(80.27)).toBe(5);
    expect(formatSolar(new Date(Date.UTC(2026, 0, 1, 0, 0)), 80)).toContain("05:00");
  });

  it("decodes a TopoJSON ring", () => {
    const rings = decodeLandRings({
      arcs: [
        [
          [0, 0],
          [10, 0],
          [0, 10],
          [-10, 0],
          [0, -10],
        ],
      ],
      objects: { land: { geometries: [{ type: "Polygon", arcs: [[0]] }] } },
    });
    expect(rings).toHaveLength(1);
    expect(rings[0][1]).toEqual([10, 0]);
  });
});
