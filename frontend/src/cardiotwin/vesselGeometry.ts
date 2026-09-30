/**
 * Procedural schematic heart + coronary paths.
 *
 * Why procedural: no redistributable, vessel-segmented heart mesh was available to this project, and a generic
 * unsegmented .glb would force us to fake which triangles are "LAD". Here every vessel is its own object with a
 * semantic id (LAD / LCX / RCA) that is the SAME id the model outputs use — so the model-output ↔ anatomy
 * correspondence is 1:1 by construction and the scene costs ~10k triangles and zero downloads.
 *
 * To swap in a licensed mesh later, only this file changes: replace `vesselCurve` / the decor with glTF nodes
 * named "LAD", "LCX", "RCA" (see docs/CARDIOTWIN.md § 3D pipeline).
 *
 * This is a SCHEMATIC. Vessel paths follow the textbook grooves (LAD: anterior interventricular groove,
 * LCX: left atrioventricular groove, RCA: right atrioventricular groove); they are not patient anatomy.
 */
import * as THREE from "three";

import type { VesselId } from "./types";

export const HEART_RADII = { a: 1.0, b: 1.3, c: 0.9 } as const;
export const VESSEL_RADIUS = 0.05;
export const SURFACE_OFFSET = 0.03;
/** rotate the heart so the apex points to the patient's left (viewer's right) and down */
export const HEART_TILT_Z = 0.45;

const smooth = (e0: number, e1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

/** Point on (or just outside) the ventricular body. theta: 0 = base/top … π = apex; phi: π/2 = anterior. */
export function surfacePoint(theta: number, phi: number, offset = 0): THREE.Vector3 {
  const { a, b, c } = HEART_RADII;
  const taper = 1 - 0.68 * Math.pow(smooth(0.3, 1, theta / Math.PI), 1.2);
  const x = a * Math.sin(theta) * Math.cos(phi) * taper;
  const z = c * Math.sin(theta) * Math.sin(phi) * taper;
  const y = b * Math.cos(theta);
  const p = new THREE.Vector3(x, y, z);
  if (offset !== 0) {
    const n = new THREE.Vector3(x / (a * a), y / (b * b), z / (c * c));
    if (n.lengthSq() > 0) p.addScaledVector(n.normalize(), offset);
  }
  return p;
}

const PI = Math.PI;

/** (theta, phi) control points per vessel — anatomical grooves on the schematic surface. */
export const VESSEL_PATHS: Record<VesselId, [number, number][]> = {
  LAD: [
    [0.3 * PI, 1.28],
    [0.42 * PI, 1.36],
    [0.56 * PI, 1.42],
    [0.7 * PI, 1.47],
    [0.84 * PI, 1.5],
    [0.95 * PI, 1.53],
  ],
  LCX: [
    [0.3 * PI, 1.22],
    [0.36 * PI, 0.75],
    [0.4 * PI, 0.35],
    [0.44 * PI, -0.05],
    [0.47 * PI, -0.5],
    [0.5 * PI, -0.95],
  ],
  RCA: [
    [0.3 * PI, 1.8],
    [0.36 * PI, 2.25],
    [0.42 * PI, 2.7],
    [0.47 * PI, 3.2],
    [0.52 * PI, 3.65],
    [0.58 * PI, 4.05],
  ],
};

export function vesselCurve(id: VesselId): THREE.CatmullRomCurve3 {
  const pts = VESSEL_PATHS[id].map(([t, p]) => surfacePoint(t, p, SURFACE_OFFSET));
  return new THREE.CatmullRomCurve3(pts, false, "centripetal");
}

/** Where the floating label for each vessel is anchored (a point along the vessel, pushed outward). */
export function labelAnchor(id: VesselId): THREE.Vector3 {
  const u: Record<VesselId, number> = { LAD: 0.72, LCX: 0.55, RCA: 0.5 };
  const p = vesselCurve(id).getPointAt(u[id]);
  const n = new THREE.Vector3(p.x, p.y * 0.4, p.z).normalize();
  return p.clone().addScaledVector(n, 0.32);
}

export function tubeGeometry(id: VesselId, radius: number, radial = 10, tubular = 64): THREE.TubeGeometry {
  return new THREE.TubeGeometry(vesselCurve(id), tubular, radius, radial, false);
}

export function bodyGeometry(): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(1, 56, 40);
  const pos = g.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    const theta = Math.acos(THREE.MathUtils.clamp(v.y, -1, 1));
    const phi = Math.atan2(v.z, v.x);
    const q = surfacePoint(theta, phi);
    pos.setXYZ(i, q.x, q.y, q.z);
  }
  g.computeVertexNormals();
  return g;
}

/** Non-target structures drawn in neutral tone for orientation only. */
export function aortaCurve(): THREE.CatmullRomCurve3 {
  return new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(-0.05, 0.85, 0.05),
      new THREE.Vector3(-0.05, 1.5, 0.05),
      new THREE.Vector3(0.25, 1.95, -0.05),
      new THREE.Vector3(0.8, 1.9, -0.3),
      new THREE.Vector3(1.1, 1.4, -0.35),
    ],
    false,
    "centripetal",
  );
}

export function pulmonaryCurve(): THREE.CatmullRomCurve3 {
  return new THREE.CatmullRomCurve3(
    [new THREE.Vector3(0.35, 0.85, 0.5), new THREE.Vector3(0.45, 1.4, 0.45), new THREE.Vector3(0.75, 1.75, 0.2)],
    false,
    "centripetal",
  );
}
