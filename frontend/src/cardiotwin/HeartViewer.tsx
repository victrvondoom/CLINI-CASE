/**
 * Interactive 3D coronary view (React Three Fiber). Performance posture for GPU-less browsers:
 * on-demand rendering (`frameloop="demand"` — frames are drawn only on interaction / state change / colour
 * transition), capped DPR, no textures, no shadows, ~10k triangles, lazily loaded by the route.
 *
 * Every vessel is a separately selectable object keyed by the semantic id shared with the model output.
 */
import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Component, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import {
  HEART_TILT_Z,
  VESSEL_RADIUS,
  aortaCurve,
  bodyGeometry,
  labelAnchor,
  pulmonaryCurve,
  tubeGeometry,
} from "./vesselGeometry";
import { type VesselRenderState, pct, vesselRenderState } from "./vesselMapping";
import { VESSELS, type VesselId, type VesselViz } from "./types";

export interface HeartViewerProps {
  viz: Record<VesselId, VesselViz> | null;
  selected: VesselId | null;
  onSelect: (id: VesselId | null) => void;
}

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

const NEUTRAL: VesselRenderState = vesselRenderState({ id: "LAD", probability: 0, band: "low", confidence: "low", halo: 0 });

function Vessel({
  id,
  state,
  probability,
  selected,
  hovered,
  onSelect,
  onHover,
}: {
  id: VesselId;
  state: VesselRenderState;
  probability: number | null;
  selected: boolean;
  hovered: boolean;
  onSelect: (id: VesselId) => void;
  onHover: (id: VesselId | null) => void;
}) {
  const invalidate = useThree((s) => s.invalidate);
  const core = useMemo(() => tubeGeometry(id, VESSEL_RADIUS), [id]);
  const pick = useMemo(() => tubeGeometry(id, VESSEL_RADIUS * 2.6, 6, 32), [id]);
  const outline = useMemo(() => tubeGeometry(id, VESSEL_RADIUS * 1.32), [id]);
  const haloKey = Math.round(state.haloScale * 20);
  const halo = useMemo(() => tubeGeometry(id, VESSEL_RADIUS * (haloKey / 20), 12, 48), [id, haloKey]);
  const anchor = useMemo(() => labelAnchor(id), [id]);
  const mat = useRef<THREE.MeshStandardMaterial>(null);
  const target = useMemo(() => new THREE.Color(state.color), [state.color]);

  useEffect(() => invalidate(), [state, selected, hovered, invalidate]);
  useFrame((_, dt) => {
    const m = mat.current;
    if (!m) return;
    const d = Math.abs(m.color.r - target.r) + Math.abs(m.color.g - target.g) + Math.abs(m.color.b - target.b);
    if (d > 0.004) {
      m.color.lerp(target, Math.min(1, dt * 9));
      m.emissive.copy(m.color);
      invalidate();
    }
  });

  return (
    <group name={id}>
      {/* uncertainty halo: radius ∝ 80% ensemble interval width */}
      <mesh geometry={halo} raycast={() => null}>
        <meshBasicMaterial color={state.color} transparent opacity={state.haloOpacity} depthWrite={false} />
      </mesh>
      {/* confidence outline (stronger = higher confidence); selection = cyan */}
      <mesh geometry={outline} raycast={() => null}>
        <meshBasicMaterial
          color={selected ? "#22d3ee" : "#0f172a"}
          side={THREE.BackSide}
          transparent
          opacity={selected ? 1 : hovered ? 0.85 : state.outlineOpacity * 0.7}
        />
      </mesh>
      <mesh geometry={core}>
        <meshStandardMaterial
          ref={mat}
          color={NEUTRAL.color}
          emissive={NEUTRAL.color}
          emissiveIntensity={state.emissive}
          roughness={0.45}
          metalness={0.05}
        />
      </mesh>
      {/* generous invisible hit target so thin vessels are easy to pick */}
      <mesh
        geometry={pick}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          onHover(null);
          document.body.style.cursor = "";
        }}
      >
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      <Html position={anchor} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
        <button
          type="button"
          tabIndex={-1}
          aria-label={state.label}
          className={`ct-vessel-tag ${selected ? "ct-vessel-tag--sel" : ""}`}
          style={{ pointerEvents: "auto" }}
          onClick={() => onSelect(id)}
        >
          <b>{id}</b>
          <span>{probability == null ? "—" : pct(probability)}</span>
        </button>
      </Html>
    </group>
  );
}

function Heart({ viz, selected, onSelect }: HeartViewerProps) {
  const body = useMemo(() => bodyGeometry(), []);
  const aorta = useMemo(() => new THREE.TubeGeometry(aortaCurve(), 40, 0.2, 12, false), []);
  const pulm = useMemo(() => new THREE.TubeGeometry(pulmonaryCurve(), 24, 0.17, 12, false), []);
  const [hover, setHover] = useState<VesselId | null>(null);
  return (
    <group
      rotation={[0, 0, HEART_TILT_Z]}
      // Deselect only on a genuine click on empty canvas — clicks on the HTML vessel tags bubble to the same
      // container and must not count as "missed".
      onPointerMissed={(e) => {
        if ((e.target as HTMLElement | null)?.tagName === "CANVAS") onSelect(null);
      }}
    >
      <mesh geometry={body}>
        <meshStandardMaterial color="#9c6470" roughness={0.75} metalness={0} transparent opacity={0.94} />
      </mesh>
      <mesh geometry={aorta}>
        <meshStandardMaterial color="#b98a92" roughness={0.7} />
      </mesh>
      <mesh geometry={pulm}>
        <meshStandardMaterial color="#8f6a86" roughness={0.7} />
      </mesh>
      <mesh position={[-0.72, 0.82, -0.08]} scale={[0.5, 0.42, 0.42]}>
        <sphereGeometry args={[1, 24, 18]} />
        <meshStandardMaterial color="#a67680" roughness={0.75} />
      </mesh>
      <mesh position={[0.62, 0.98, -0.02]} scale={[0.34, 0.3, 0.3]}>
        <sphereGeometry args={[1, 20, 14]} />
        <meshStandardMaterial color="#a67680" roughness={0.75} />
      </mesh>
      {VESSELS.map((id) => (
        <Vessel
          key={id}
          id={id}
          state={viz ? vesselRenderState(viz[id]) : NEUTRAL}
          probability={viz ? viz[id].probability : null}
          selected={selected === id}
          hovered={hover === id}
          onSelect={onSelect}
          onHover={setHover}
        />
      ))}
    </group>
  );
}

function Scene(props: HeartViewerProps) {
  const controls = useRef<{ saveState: () => void } | null>(null);
  useEffect(() => controls.current?.saveState(), []);
  return (
    <>
      <ambientLight intensity={0.85} />
      <directionalLight position={[3, 4, 5]} intensity={1.1} />
      <directionalLight position={[-4, -1, -3]} intensity={0.35} />
      <Heart {...props} />
      <OrbitControls
        ref={controls as never}
        makeDefault
        enablePan={false}
        enableDamping={false}
        target={[0, 0.3, 0]}
        minDistance={3.4}
        maxDistance={9.5}
        rotateSpeed={0.8}
      />
    </>
  );
}

export default function HeartViewer(props: HeartViewerProps) {
  const [gl] = useState(webglAvailable);
  const [resetKey, setResetKey] = useState(0);
  const fallback = (
    <div role="status" className="h-full grid place-items-center text-center text-[12.5px] text-ink-muted p-6">
      3D view unavailable in this browser (WebGL disabled). The vessel cards show the same model outputs.
    </div>
  );
  if (!gl) return fallback;
  return (
    <div className="relative h-full w-full">
      <style>{`
        .ct-vessel-tag{display:flex;gap:6px;align-items:baseline;padding:2px 8px;border-radius:999px;font:600 11px/1.4 var(--font-ui,system-ui);
          background:rgb(15 23 42/.82);color:#fff;border:1px solid rgb(255 255 255/.25);white-space:nowrap;cursor:pointer}
        .ct-vessel-tag span{font-variant-numeric:tabular-nums;font-weight:500;opacity:.92}
        .ct-vessel-tag--sel{border-color:#22d3ee;box-shadow:0 0 0 2px rgb(34 211 238/.5)}
      `}</style>
      <SceneBoundary fallback={fallback}>
        <Canvas
          key={resetKey}
          frameloop="demand"
          dpr={[1, 1.5]}
          camera={{ position: [0.3, 0.45, 6.6], fov: 36 }}
          gl={{ antialias: true, powerPreference: "low-power" }}
          aria-label="Interactive 3D schematic of the heart with the LAD, LCX and RCA coronary arteries"
        >
          <Scene {...props} />
        </Canvas>
      </SceneBoundary>
      <button
        type="button"
        onClick={() => setResetKey((k) => k + 1)}
        className="absolute top-2 right-2 text-[11px] px-2 py-1 rounded-md border border-surface-border bg-surface-raised/90 text-ink-body hover:border-accent-brand/60 focus:outline-none focus:ring-2 focus:ring-accent-brand"
      >
        Reset view
      </button>
    </div>
  );
}
