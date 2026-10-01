/**
 * The landing page's WebGL scene ("aperture").
 *
 * Ported from frontend/LANDING/landing/Aperture3D.tsx, which was written for
 * Next.js and never wired into this Vite app. The port is deliberately
 * conservative -- same shaders, same particle fields, same crystal, same
 * five-stage camera choreography. What changed:
 *
 *   - the "@/lib/aperture/tokens" Next path alias -> "./tokens"
 *   - framer-motion MotionValue -> the local Signal (identical .get() surface)
 *   - the "use client" directive dropped (Vite has no server components)
 *   - palette resolved to neutral grayscale, so the page reads black + white
 *   - per-frame `new THREE.Vector3` hoisted out of the render loops
 *   - a DNA double-helix layer added: the scientific spine the composition
 *     was always describing, in the same scene rather than a second canvas
 *
 * The canvas is position:fixed, so one continuous environment sits behind
 * every section -- there are no per-section backgrounds to seam together.
 */
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Edges, MeshTransmissionMaterial } from "@react-three/drei";
import * as THREE from "three";

import { apertureColors } from "./tokens";
import type { Signal } from "./useScrollProgress";

const PARTICLE_FRAGMENT = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float alpha = smoothstep(0.5, 0.0, d) * vAlpha;
    gl_FragColor = vec4(uColor, alpha);
  }
`;

const CHAOS_VERTEX = `
  attribute float aSeed;
  uniform float uTime;
  varying float vAlpha;
  void main() {
    vec3 pos = position;
    float t = uTime * (1.2 + aSeed);
    pos.x += mod(t * 1.1 + aSeed * 6.0, 4.2) - 2.1;
    pos.y += sin(t * 4.0 + aSeed * 20.0) * 0.3 * (0.3 + aSeed);
    pos.z += cos(t * 3.0 + aSeed * 12.0) * 0.25;
    vAlpha = 0.35 + 0.5 * abs(sin(t * 5.0 + aSeed * 30.0));
    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_PointSize = clamp((2.2 + aSeed * 3.2) * (260.0 / -mvPosition.z), 1.0, 7.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const ORDER_VERTEX = `
  attribute float aSeed;
  uniform float uTime;
  varying float vAlpha;
  void main() {
    vec3 pos = position;
    float t = uTime * 0.55;
    pos.x += mod(t + aSeed * 5.0, 5.2);
    vAlpha = 0.55 + 0.35 * aSeed;
    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_PointSize = clamp(2.6 * (260.0 / -mvPosition.z), 1.0, 6.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

function useParticleGeometry(count: number, build: (i: number, arr: Float32Array) => void) {
  return useMemo(() => {
    const positions = new Float32Array(count * 3);
    const seeds = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      build(i, positions);
      seeds[i] = Math.random();
    }
    return { positions, seeds };
  }, [count, build]);
}

/** ShaderMaterials are constructed by hand, so they are disposed by hand. */
function useDisposedMaterial<T extends THREE.Material>(factory: () => T): T {
  const material = useMemo(factory, []);
  useEffect(() => () => material.dispose(), [material]);
  return material;
}

function ChaosField({ count = 220 }: { count?: number }) {
  const build = useMemo(
    () => (i: number, arr: Float32Array) => {
      arr[i * 3] = -Math.random() * 4.2 - 1.8;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 2.6;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 2.2;
    },
    [],
  );
  const { positions, seeds } = useParticleGeometry(count, build);
  const material = useDisposedMaterial(
    () =>
      new THREE.ShaderMaterial({
        uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(apertureColors.ember) } },
        vertexShader: CHAOS_VERTEX,
        fragmentShader: PARTICLE_FRAGMENT,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
  );
  useFrame((_, delta) => {
    material.uniforms.uTime.value += delta;
  });
  return (
    <points material={material}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aSeed" args={[seeds, 1]} />
      </bufferGeometry>
    </points>
  );
}

function OrderField({ count = 160 }: { count?: number }) {
  const lanes = 4;
  const build = useMemo(
    () => (i: number, arr: Float32Array) => {
      const lane = i % lanes;
      arr[i * 3] = Math.random() * 5.2 + 1.8;
      arr[i * 3 + 1] = (lane - (lanes - 1) / 2) * 0.5;
      arr[i * 3 + 2] = (lane - (lanes - 1) / 2) * 0.35;
    },
    [],
  );
  const { positions, seeds } = useParticleGeometry(count, build);
  const material = useDisposedMaterial(
    () =>
      new THREE.ShaderMaterial({
        uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(apertureColors.cyan) } },
        vertexShader: ORDER_VERTEX,
        fragmentShader: PARTICLE_FRAGMENT,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
  );
  useFrame((_, delta) => {
    material.uniforms.uTime.value += delta;
  });
  return (
    <points material={material}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aSeed" args={[seeds, 1]} />
      </bufferGeometry>
    </points>
  );
}

/* ---------------------------------------------------------------------------
   DNA double helix.

   Two instanced meshes per strand pair -- backbone nodes and base-pair rungs.
   Every instance matrix is written once on mount, never in the render loop;
   the animation is a single rotation on the parent group, so the whole helix
   costs two draw calls and one matrix update per frame.
   --------------------------------------------------------------------------- */

interface HelixProps {
  segments: number;
  radius: number;
  length: number;
  turns: number;
  nodeSize: number;
  rungRadius: number;
  color: string;
  opacity: number;
  /** Radians per second about the helix axis. */
  spin: number;
  /** How hard scroll progress winds the helix, in radians over the full page. */
  scrollTwist: number;
  position: [number, number, number];
  rotation: [number, number, number];
  scrollYProgress: Signal;
}

function Helix({
  segments,
  radius,
  length,
  turns,
  nodeSize,
  rungRadius,
  color,
  opacity,
  spin,
  scrollTwist,
  position,
  rotation,
  scrollYProgress,
}: HelixProps) {
  const groupRef = useRef<THREE.Group>(null);
  const nodesRef = useRef<THREE.InstancedMesh>(null);
  const rungsRef = useRef<THREE.InstancedMesh>(null);
  const elapsed = useRef(0);

  // Reused across the whole build; nothing is allocated per instance.
  const scratch = useMemo(
    () => ({
      dummy: new THREE.Object3D(),
      a: new THREE.Vector3(),
      b: new THREE.Vector3(),
      mid: new THREE.Vector3(),
      dir: new THREE.Vector3(),
      up: new THREE.Vector3(0, 1, 0),
      quat: new THREE.Quaternion(),
    }),
    [],
  );

  useLayoutEffect(() => {
    const nodes = nodesRef.current;
    const rungs = rungsRef.current;
    if (!nodes || !rungs) return;

    const { dummy, a, b, mid, dir, up, quat } = scratch;
    const span = 2 * radius;

    for (let i = 0; i < segments; i++) {
      const t = segments === 1 ? 0 : i / (segments - 1);
      const x = (t - 0.5) * length;
      const angle = t * turns * Math.PI * 2;

      a.set(x, Math.cos(angle) * radius, Math.sin(angle) * radius);
      b.set(x, Math.cos(angle + Math.PI) * radius, Math.sin(angle + Math.PI) * radius);

      // Backbone: one instance per strand, so 2i and 2i+1.
      dummy.quaternion.identity();
      dummy.scale.setScalar(1);
      dummy.position.copy(a);
      dummy.updateMatrix();
      nodes.setMatrixAt(i * 2, dummy.matrix);

      dummy.position.copy(b);
      dummy.updateMatrix();
      nodes.setMatrixAt(i * 2 + 1, dummy.matrix);

      // Base pair: a unit-height cylinder rotated from +Y onto the A->B axis
      // and stretched to span the strands.
      mid.addVectors(a, b).multiplyScalar(0.5);
      dir.subVectors(b, a).normalize();
      quat.setFromUnitVectors(up, dir);

      dummy.position.copy(mid);
      dummy.quaternion.copy(quat);
      dummy.scale.set(1, span, 1);
      dummy.updateMatrix();
      rungs.setMatrixAt(i, dummy.matrix);
    }

    nodes.instanceMatrix.needsUpdate = true;
    rungs.instanceMatrix.needsUpdate = true;
    nodes.computeBoundingSphere();
    rungs.computeBoundingSphere();
  }, [segments, radius, length, turns, scratch]);

  useFrame((_, delta) => {
    const group = groupRef.current;
    if (!group) return;
    elapsed.current += delta;
    // Spin about the helix's own axis (local X) + a slow wind from scroll.
    group.rotation.x = rotation[0] + elapsed.current * spin + scrollYProgress.get() * scrollTwist;
  });

  return (
    <group ref={groupRef} position={position} rotation={rotation}>
      <instancedMesh
        ref={nodesRef}
        args={[undefined, undefined, segments * 2]}
        frustumCulled={false}
      >
        <sphereGeometry args={[nodeSize, 8, 8]} />
        <meshStandardMaterial
          color={color}
          roughness={0.35}
          metalness={0.1}
          transparent
          opacity={opacity}
          depthWrite={false}
        />
      </instancedMesh>

      <instancedMesh ref={rungsRef} args={[undefined, undefined, segments]} frustumCulled={false}>
        <cylinderGeometry args={[rungRadius, rungRadius, 1, 5, 1, true]} />
        <meshStandardMaterial
          color={color}
          roughness={0.5}
          metalness={0.05}
          transparent
          opacity={opacity * 0.5}
          depthWrite={false}
        />
      </instancedMesh>
    </group>
  );
}

/**
 * The helix system: a near strand reading as fine structure, and a larger,
 * dimmer strand set further back and counter-rotating. The two at different
 * depths are what give the background parallax and density instead of one
 * flat decorative object.
 */
function HelixSystem({ scrollYProgress }: { scrollYProgress: Signal }) {
  return (
    <>
      <Helix
        scrollYProgress={scrollYProgress}
        segments={96}
        radius={0.95}
        length={20}
        turns={7}
        nodeSize={0.045}
        rungRadius={0.008}
        color={apertureColors.violet}
        opacity={0.5}
        spin={0.07}
        scrollTwist={2.2}
        position={[0, -0.4, -2.6]}
        rotation={[0, 0, -0.12]}
      />
      <Helix
        scrollYProgress={scrollYProgress}
        segments={72}
        radius={2.3}
        length={34}
        turns={5}
        nodeSize={0.075}
        rungRadius={0.012}
        color={apertureColors.violet}
        opacity={0.2}
        spin={-0.035}
        scrollTwist={-1.4}
        position={[0, 0.8, -8]}
        rotation={[0.6, 0, 0.16]}
      />
    </>
  );
}

const DESTINATIONS = [
  { label: "claude", pos: [6.4, 0.5, 0] as [number, number, number] },
  { label: "gpt-4.1", pos: [6.6, -0.4, 0.3] as [number, number, number] },
  { label: "internal-tool", pos: [6.2, 0.1, -0.5] as [number, number, number] },
  { label: "audit-log", pos: [6.8, -0.1, 0.6] as [number, number, number] },
];

function DestinationNodes() {
  return (
    <>
      {DESTINATIONS.map((d) => (
        <group key={d.label} position={d.pos}>
          <mesh>
            <sphereGeometry args={[0.05, 12, 12]} />
            <meshBasicMaterial color={apertureColors.cyan} />
          </mesh>
          <pointLight color={apertureColors.cyan} intensity={0.7} distance={1.1} />
        </group>
      ))}
    </>
  );
}

function ApertureCrystal({ pulse }: { pulse: Signal }) {
  const meshRef = useRef<THREE.Mesh>(null);
  // Hoisted out of the frame loop -- this used to allocate a Vector3 per frame.
  const targetScale = useMemo(() => new THREE.Vector3(), []);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    meshRef.current.rotation.y += delta * 0.09;
    const s = 1 + pulse.get() * 0.06;
    targetScale.set(s, s, s);
    meshRef.current.scale.lerp(targetScale, 0.15);
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1.15, 1]} />
      <MeshTransmissionMaterial
        samples={4}
        resolution={128}
        thickness={0.35}
        roughness={0.08}
        transmission={0.92}
        ior={1.5}
        chromaticAberration={0.05}
        anisotropy={0.25}
        distortion={0.15}
        distortionScale={0.3}
        temporalDistortion={0.08}
        color={apertureColors.bone}
        flatShading
      />
      <Edges color={apertureColors.violet} threshold={1} />
    </mesh>
  );
}

interface CameraStage {
  at: number;
  pos: [number, number, number];
  look: [number, number, number];
}

const STAGES: CameraStage[] = [
  { at: 0, pos: [1.9, 0.6, 9.2], look: [0.3, 0, 0] },
  { at: 0.22, pos: [4.0, 0.4, 10.4], look: [-1.8, 0, 0] },
  { at: 0.48, pos: [0, 0.8, 9.8], look: [0, 0, 0] },
  { at: 0.74, pos: [-3.4, 0.3, 10.2], look: [1.8, 0, 0] },
  { at: 1, pos: [0.3, 0.9, 12.0], look: [0, 0, 0] },
];

function CameraRig({ scrollYProgress }: { scrollYProgress: Signal }) {
  const target = useRef(new THREE.Vector3());
  // Both of these used to be allocated fresh on every single frame.
  const nextPos = useMemo(() => new THREE.Vector3(), []);
  const nextLook = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    const p = Math.min(Math.max(scrollYProgress.get(), 0), 1);
    let seg = STAGES[0];
    let next = STAGES[STAGES.length - 1];
    for (let i = 0; i < STAGES.length - 1; i++) {
      if (p >= STAGES[i].at && p <= STAGES[i + 1].at) {
        seg = STAGES[i];
        next = STAGES[i + 1];
        break;
      }
    }
    const span = next.at - seg.at || 1;
    const t = Math.min(Math.max((p - seg.at) / span, 0), 1);

    // extra slow orbit through the "how it works" middle stretch
    const orbit = p > 0.3 && p < 0.65 ? Math.sin(((p - 0.3) / 0.35) * Math.PI) * 1.4 : 0;

    nextPos.set(
      seg.pos[0] + (next.pos[0] - seg.pos[0]) * t + orbit,
      seg.pos[1] + (next.pos[1] - seg.pos[1]) * t,
      seg.pos[2] + (next.pos[2] - seg.pos[2]) * t,
    );
    nextLook.set(
      seg.look[0] + (next.look[0] - seg.look[0]) * t,
      seg.look[1] + (next.look[1] - seg.look[1]) * t,
      seg.look[2] + (next.look[2] - seg.look[2]) * t,
    );

    state.camera.position.lerp(nextPos, 0.08);
    target.current.lerp(nextLook, 0.08);
    state.camera.lookAt(target.current);
  });

  return null;
}

function Scene({ scrollYProgress, pulse }: { scrollYProgress: Signal; pulse: Signal }) {
  return (
    <>
      <ambientLight intensity={0.32} />
      <pointLight position={[-4, 1, 3]} color={apertureColors.ember} intensity={3.2} />
      <pointLight position={[4, 1, 3]} color={apertureColors.cyan} intensity={2.6} />
      <pointLight position={[0, 3, 4]} color={apertureColors.violet} intensity={1.8} />
      <HelixSystem scrollYProgress={scrollYProgress} />
      <ApertureCrystal pulse={pulse} />
      <ChaosField />
      <OrderField />
      <DestinationNodes />
      <CameraRig scrollYProgress={scrollYProgress} />
    </>
  );
}

export default function Aperture3D({
  scrollYProgress,
  pulse,
}: {
  scrollYProgress: Signal;
  pulse: Signal;
}) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [1.9, 0.6, 9.2], fov: 42 }}
      style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none" }}
    >
      <color attach="background" args={[apertureColors.void]} />
      <fog attach="fog" args={[apertureColors.void, 11, 30]} />
      <Scene scrollYProgress={scrollYProgress} pulse={pulse} />
    </Canvas>
  );
}
