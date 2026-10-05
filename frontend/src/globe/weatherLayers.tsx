/**
 * Data-driven globe layers: weather at a point, exposure-zone outlines, and a pulse ring for live
 * pipeline runs. Every layer is drawn from real inputs (Open-Meteo values, scenario polygons, run
 * state); nothing here is decorative weather.
 *
 * The canvas renders on demand, so animated layers call `invalidate()` from useFrame while they
 * are mounted and stop costing frames as soon as they unmount.
 */
import { Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { latLonToXYZ } from "./geo";

export interface GlobeWeather {
  latitude: number;
  longitude: number;
  /** UTC instant the values apply to; null means current conditions. */
  atUtc: string | null;
  precipitationMm: number;
  windSpeedKmh: number;
  /** Meteorological: the direction the wind blows FROM, degrees clockwise from north. */
  windDirectionDeg: number;
  cloudCover: number;
  temperatureC: number | null;
}

export interface GlobeZone {
  id: string;
  /** Closed ring of [longitude, latitude] pairs. */
  ring: [number, number][];
  color: string;
}

/** Local tangent frame at a point: up (surface normal), east, north. */
export function tangentFrame(lat: number, lon: number) {
  const up = new THREE.Vector3(...latLonToXYZ(lat, lon, 1)).normalize();
  const east = new THREE.Vector3(0, 1, 0).cross(up);
  if (east.lengthSq() < 1e-9) east.set(1, 0, 0); // poles
  east.normalize();
  const north = new THREE.Vector3().crossVectors(up, east).normalize();
  return { up, east, north };
}

/** Orientation whose local axes are X = east, Y = up, Z = south. */
function frameQuaternion(lat: number, lon: number): THREE.Quaternion {
  const { up, east, north } = tangentFrame(lat, lon);
  const south = north.clone().negate();
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(east, up, south));
}

/** World size that keeps a glyph readable from orbit down to city zoom. */
export function glyphScale(cameraDistance: number): number {
  return THREE.MathUtils.clamp((cameraDistance - 1) * 0.22, 0.0012, 0.11);
}

/** Rotation about local Y that points local +X along a compass bearing. */
export function bearingToYaw(bearingDeg: number): number {
  return ((90 - bearingDeg) * Math.PI) / 180;
}

export function temperatureHex(c: number | null): string {
  if (c == null) return "#94a3b8";
  if (c < 5) return "#60a5fa";
  if (c < 15) return "#22d3ee";
  if (c < 22) return "#4ade80";
  if (c < 28) return "#fbbf24";
  return "#f87171";
}

/** Rain particles shown for a precipitation rate in mm/h (0 = none). */
export function rainParticleCount(precipitationMm: number): number {
  if (!(precipitationMm > 0)) return 0;
  return Math.round(THREE.MathUtils.clamp(40 + precipitationMm * 90, 40, RAIN_MAX));
}

const RAIN_MAX = 420;
const RAIN_TOP = 1.7;

const CLOUD_PUFFS: [number, number, number, number][] = [
  [-0.42, 1.75, 0.1, 0.36],
  [0, 1.95, -0.08, 0.46],
  [0.46, 1.75, 0.04, 0.38],
  [0.12, 1.62, 0.36, 0.32],
];

export function WeatherGlyph({ weather }: { weather: GlobeWeather }) {
  const group = useRef<THREE.Group>(null);
  const rainGeometry = useRef<THREE.BufferGeometry>(null);
  const { latitude, longitude } = weather;
  const position = useMemo(
    () => new THREE.Vector3(...latLonToXYZ(latitude, longitude, 1.0012)),
    [latitude, longitude],
  );
  const quaternion = useMemo(() => frameQuaternion(latitude, longitude), [latitude, longitude]);
  const drops = rainParticleCount(weather.precipitationMm);

  const rainPositions = useMemo(() => {
    const arr = new Float32Array(RAIN_MAX * 3);
    for (let i = 0; i < RAIN_MAX; i += 1) {
      const r = 0.55 * Math.sqrt(Math.random());
      const a = Math.random() * Math.PI * 2;
      arr[i * 3] = Math.cos(a) * r;
      arr[i * 3 + 1] = Math.random() * RAIN_TOP;
      arr[i * 3 + 2] = Math.sin(a) * r;
    }
    return arr;
  }, []);

  const arrowLength = 0.45 + (Math.min(weather.windSpeedKmh, 60) / 60) * 0.9;
  const showWind = weather.windSpeedKmh >= 1;
  const cloudOpacity = 0.12 + 0.58 * THREE.MathUtils.clamp(weather.cloudCover / 100, 0, 1);

  useFrame((state, delta) => {
    group.current?.scale.setScalar(glyphScale(state.camera.position.length()));
    const geometry = rainGeometry.current;
    if (drops > 0 && geometry) {
      const attr = geometry.getAttribute("position") as THREE.BufferAttribute;
      const fall = Math.min(delta, 0.05) * (1.6 + Math.min(weather.precipitationMm, 10) * 0.12);
      for (let i = 0; i < drops; i += 1) {
        let y = attr.getY(i) - fall;
        if (y < 0) y += RAIN_TOP;
        attr.setY(i, y);
      }
      attr.needsUpdate = true;
      state.invalidate();
    }
  });

  return (
    <group ref={group} position={position} quaternion={quaternion}>
      {/* Temperature halo */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.55, 0.64, 48]} />
        <meshBasicMaterial color={temperatureHex(weather.temperatureC)} transparent opacity={0.9} side={THREE.DoubleSide} />
      </mesh>

      {/* Cloud cover */}
      {weather.cloudCover > 5 &&
        CLOUD_PUFFS.map(([x, y, z, r]) => (
          <mesh key={`${x}-${y}`} position={[x, y, z]}>
            <sphereGeometry args={[r, 16, 12]} />
            <meshStandardMaterial color="#e2e8f0" transparent opacity={cloudOpacity} depthWrite={false} />
          </mesh>
        ))}

      {/* Precipitation */}
      {drops > 0 && (
        <points>
          <bufferGeometry ref={rainGeometry} drawRange={{ start: 0, count: drops }}>
            <bufferAttribute attach="attributes-position" args={[rainPositions, 3]} />
          </bufferGeometry>
          <pointsMaterial color="#7dd3fc" size={2.2} sizeAttenuation={false} transparent opacity={0.9} />
        </points>
      )}

      {/* Wind: arrow points where the wind blows TO (meteorological direction + 180°) */}
      {showWind && (
        <group rotation={[0, bearingToYaw(weather.windDirectionDeg + 180), 0]}>
          <mesh position={[arrowLength / 2, 0.18, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <cylinderGeometry args={[0.035, 0.035, arrowLength, 10]} />
            <meshBasicMaterial color="#f8fafc" />
          </mesh>
          <mesh position={[arrowLength + 0.11, 0.18, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <coneGeometry args={[0.1, 0.22, 14]} />
            <meshBasicMaterial color="#f8fafc" />
          </mesh>
        </group>
      )}
    </group>
  );
}

export function PulseRing({ latitude, longitude, color }: { latitude: number; longitude: number; color: string }) {
  const ring = useRef<THREE.Mesh>(null);
  const material = useRef<THREE.MeshBasicMaterial>(null);
  const position = useMemo(
    () => new THREE.Vector3(...latLonToXYZ(latitude, longitude, 1.0015)),
    [latitude, longitude],
  );
  const quaternion = useMemo(() => frameQuaternion(latitude, longitude), [latitude, longitude]);

  useFrame((state) => {
    const t = (state.clock.elapsedTime % 1.4) / 1.4;
    ring.current?.scale.setScalar(glyphScale(state.camera.position.length()) * (0.5 + t * 2.6));
    if (material.current) material.current.opacity = 0.9 * (1 - t);
    state.invalidate();
  });

  return (
    <group position={position} quaternion={quaternion}>
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.82, 1, 48]} />
        <meshBasicMaterial ref={material} color={color} transparent opacity={0.9} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

export function ZoneOutline({ zone }: { zone: GlobeZone }) {
  const points = useMemo(
    () => zone.ring.map(([lon, lat]) => new THREE.Vector3(...latLonToXYZ(lat, lon, 1.0004))),
    [zone.ring],
  );
  if (points.length < 2) return null;
  return <Line points={points} color={zone.color} lineWidth={2.5} />;
}
