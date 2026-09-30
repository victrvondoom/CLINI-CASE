import { describe, expect, it } from "vitest";
import * as THREE from "three";

import { HEART_RADII, VESSEL_PATHS, labelAnchor, surfacePoint, vesselCurve } from "../src/cardiotwin/vesselGeometry";
import {
  bandFor,
  pct,
  probabilityColor,
  probabilityRgb,
  signedPct,
  vesselRenderState,
} from "../src/cardiotwin/vesselMapping";
import { VESSELS, type VesselViz } from "../src/cardiotwin/types";

const viz = (p: Partial<VesselViz> = {}): VesselViz => ({ id: "LAD", probability: 0.5, band: "intermediate", confidence: "high", halo: 0.1, ...p });

describe("probability → colour", () => {
  it("runs neutral → amber → red and clamps", () => {
    expect(probabilityRgb(0)).toEqual([138, 161, 181]);
    expect(probabilityRgb(0.5)).toEqual([242, 169, 0]);
    expect(probabilityRgb(1)).toEqual([200, 16, 46]);
    expect(probabilityRgb(-3)).toEqual(probabilityRgb(0));
    expect(probabilityRgb(7)).toEqual(probabilityRgb(1));
    expect(probabilityRgb(Number.NaN)).toEqual(probabilityRgb(0));
    expect(probabilityColor(0.5)).toBe("#f2a900");
  });
  it("bands match the backend display bands", () => {
    expect([0, 0.32, 0.33, 0.65, 0.66, 1].map(bandFor)).toEqual(["low", "low", "intermediate", "intermediate", "elevated", "elevated"]);
  });
  it("formats percentages and deltas", () => {
    expect(pct(0.814)).toBe("81%");
    expect(signedPct(-0.117)).toBe("-11.7 pp");
    expect(signedPct(0.05)).toBe("+5.0 pp");
  });
});

describe("visual encoding rules (clinical honesty)", () => {
  it("maps the model probability to a distinct colour per vessel", () => {
    const a = vesselRenderState(viz({ id: "LAD", probability: 0.81 }));
    const c = vesselRenderState(viz({ id: "RCA", probability: 0.12 }));
    expect(a.color).not.toBe(c.color);
    expect(a.id).toBe("LAD");
    expect(a.label).toMatch(/LAD: estimated stenosis probability 81%/);
    expect(a.label).not.toMatch(/blockage|diagnos/i);
  });
  it("uncertainty widens the halo; confidence strengthens the outline", () => {
    const narrow = vesselRenderState(viz({ halo: 0.05 }));
    const wide = vesselRenderState(viz({ halo: 0.6 }));
    expect(wide.haloScale).toBeGreaterThan(narrow.haloScale);
    expect(wide.haloOpacity).toBeGreaterThan(narrow.haloOpacity);
    const hi = vesselRenderState(viz({ confidence: "high" })).outlineOpacity;
    const mid = vesselRenderState(viz({ confidence: "moderate" })).outlineOpacity;
    const lo = vesselRenderState(viz({ confidence: "low" })).outlineOpacity;
    expect(hi).toBeGreaterThan(mid);
    expect(mid).toBeGreaterThan(lo);
  });
  it("never encodes probability as vessel thickness (would imply anatomical narrowing)", () => {
    const keys = Object.keys(vesselRenderState(viz()));
    expect(keys.some((k) => /radius|thick|width|narrow/i.test(k))).toBe(false);
  });
});

describe("schematic anatomy geometry", () => {
  it("has exactly the three target vessels, each its own curve", () => {
    expect(Object.keys(VESSEL_PATHS).sort()).toEqual([...VESSELS].sort());
    const lengths = VESSELS.map((v) => vesselCurve(v).getLength());
    lengths.forEach((l) => expect(l).toBeGreaterThan(1));
    expect(new Set(lengths.map((l) => l.toFixed(3))).size).toBe(3);
  });
  it("keeps every vessel on (just outside) the ventricular surface", () => {
    const { a, b, c } = HEART_RADII;
    for (const v of VESSELS) {
      const curve = vesselCurve(v);
      for (let t = 0; t <= 1; t += 0.1) {
        const p = curve.getPoint(t);
        const r = Math.hypot(p.x / a, p.y / b, p.z / c);
        expect(r).toBeGreaterThan(0.2); // never collapses into the centre
        expect(r).toBeLessThan(1.12); // never floats away from the wall
      }
    }
  });
  it("puts the LAD on the anterior surface and the RCA on the patient's right", () => {
    expect(vesselCurve("LAD").getPointAt(0.5).z).toBeGreaterThan(0.3); // anterior (+z faces the viewer)
    expect(vesselCurve("RCA").getPointAt(0.3).x).toBeLessThan(0); // patient's right = viewer's left
    expect(vesselCurve("LCX").getPointAt(0.3).x).toBeGreaterThan(0); // patient's left
  });
  it("gives each vessel a distinct label anchor away from the others", () => {
    const pts = VESSELS.map(labelAnchor);
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) expect(pts[i].distanceTo(pts[j])).toBeGreaterThan(0.4);
  });
  it("surfacePoint offset pushes outward", () => {
    const on = surfacePoint(1.2, 1.4, 0);
    const out = surfacePoint(1.2, 1.4, 0.1);
    expect(out.length()).toBeGreaterThan(on.length());
    expect(out.distanceTo(on)).toBeCloseTo(0.1, 5);
    expect(new THREE.Vector3().copy(on)).toBeTruthy();
  });
});
