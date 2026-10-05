/**
 * Interactive 3D globe for observation locations (React Three Fiber, already a dependency).
 * Drag to rotate, wheel/pinch or +/- to zoom. No tile server: land is drawn from a bundled Natural Earth
 * TopoJSON (/world-land-110m.json), so it works offline. Day/night shading uses the approximate sub-solar point.
 *
 * GPS is opt-in (browser permission). The device position is coarsened before it is shown, is held only in
 * component state, and is never sent anywhere.
 */
import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Crosshair, LocateFixed, Minus, Plus } from "lucide-react";
import { type MutableRefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { webglAvailable } from "../cardiotwin/HeartViewer";
import {
  type LandTopology,
  WORLD_CLOCK_ZONES,
  browserTimeZone,
  coarsen,
  decodeLandRings,
  formatInZone,
  formatSolar,
  latLonToXYZ,
  subsolarPoint,
  validCoordinates,
} from "./geo";
import { type GlobeWeather, type GlobeZone, PulseRing, WeatherGlyph, ZoneOutline } from "./weatherLayers";

export type { GlobeWeather, GlobeZone } from "./weatherLayers";

export interface GlobeMarker {
  id: string;
  latitude: number;
  longitude: number;
  label: string;
  color: string;
}

interface Props {
  markers: GlobeMarker[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Fly the camera over a point; `distance` (from the globe centre, 1 = surface) zooms in too. */
  focus?: { latitude: number; longitude: number; key: string; distance?: number };
  onSurfaceSelect?: (latitude: number, longitude: number) => void;
  /** Weather to draw at a point (rain, cloud, wind, temperature halo). */
  weather?: GlobeWeather | null;
  /** Exposure-zone outlines drawn on the surface. */
  zones?: GlobeZone[];
  /** Marker id to pulse while a live pipeline run is executing. */
  pulseId?: string | null;
  /** Instant used for the day/night terminator (forecast playback); defaults to now. */
  sunDate?: Date | null;
  /** Called with the coarsened point when the user shares GPS or types a location. */
  onDeviceLocation?: (latitude: number, longitude: number, source: "gps" | "manual") => void;
}

interface Device {
  latitude: number;
  longitude: number;
  accuracy: number;
  at: number;
}

interface CameraApi {
  zoom: (factor: number) => void;
  focus: (lat: number, lon: number, distance?: number) => void;
}

// 1.004 ≈ 25 km above the surface: close enough to see a 1 km exposure zone.
const MIN_D = 1.004;
const MAX_D = 6;

function landTexture(rings: Array<Array<[number, number]>>): THREE.CanvasTexture {
  const w = 2048;
  const h = 1024;
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d");
  if (g) {
    g.fillStyle = "#0b2236";
    g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(120,170,210,0.18)";
    g.lineWidth = 1;
    for (let lon = -180; lon <= 180; lon += 30) {
      const x = ((lon + 180) / 360) * w;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, h);
      g.stroke();
    }
    for (let lat = -90; lat <= 90; lat += 30) {
      const y = ((90 - lat) / 180) * h;
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(w, y);
      g.stroke();
    }
    g.fillStyle = "#2f6b57";
    g.strokeStyle = "#7fc4a4";
    g.lineWidth = 1.2;
    for (const ring of rings) {
      g.beginPath();
      ring.forEach(([lon, lat], i) => {
        const x = ((lon + 180) / 360) * w;
        const y = ((90 - lat) / 180) * h;
        if (i === 0) g.moveTo(x, y);
        else g.lineTo(x, y);
      });
      g.closePath();
      g.fill();
      g.stroke();
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.anisotropy = 4;
  return t;
}

function Pin({
  lat,
  lon,
  color,
  size,
  onClick,
}: {
  lat: number;
  lon: number;
  color: string;
  size: number;
  onClick?: () => void;
}) {
  const pos = useMemo(() => latLonToXYZ(lat, lon, 1.012), [lat, lon]);
  return (
    <mesh
      position={pos}
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick();
            }
          : undefined
      }
    >
      <sphereGeometry args={[size, 16, 16]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

function CameraBridge({ apiRef }: { apiRef: MutableRefObject<CameraApi | null> }) {
  const { camera, invalidate } = useThree();
  useEffect(() => {
    apiRef.current = {
      zoom: (f) => {
        camera.position.setLength(Math.min(MAX_D, Math.max(MIN_D, camera.position.length() * f)));
        invalidate();
      },
      focus: (lat, lon, distance) => {
        const [x, y, z] = latLonToXYZ(lat, lon, 1);
        const length = distance ?? Math.min(camera.position.length() || 3, 2.2);
        camera.position.set(x, y, z).setLength(Math.min(MAX_D, Math.max(MIN_D, length)));
        camera.lookAt(0, 0, 0);
        invalidate();
      },
    };
  }, [apiRef, camera, invalidate]);
  return null;
}

function Scene({
  markers,
  selectedId,
  onSelect,
  device,
  texture,
  sun,
  onSurfaceSelect,
  weather,
  zones,
  pulseId,
}: Props & { device: Device | null; texture: THREE.Texture | null; sun: [number, number, number] }) {
  const controlsRef = useRef<{ rotateSpeed: number; zoomSpeed: number } | null>(null);
  // Rotation is an angle about the globe centre, so slow it down near the surface.
  useFrame(({ camera }) => {
    const controls = controlsRef.current;
    if (!controls) return;
    const altitude = camera.position.length() - 1;
    controls.rotateSpeed = THREE.MathUtils.clamp(altitude * 0.25, 0.004, 0.5);
    controls.zoomSpeed = altitude < 0.15 ? 0.55 : 0.8;
  });
  const pulsing = pulseId ? markers.find((m) => m.id === pulseId) : undefined;
  return (
    <>
      <ambientLight intensity={0.35} />
      <directionalLight position={[sun[0] * 5, sun[1] * 5, sun[2] * 5]} intensity={2.2} />
      <mesh
        onClick={(event) => {
          if (!onSurfaceSelect) return;
          const point = event.point.clone().normalize();
          const latitude = (Math.asin(THREE.MathUtils.clamp(point.y, -1, 1)) * 180) / Math.PI;
          const phi = Math.atan2(point.z, -point.x);
          const longitude = ((((phi * 180) / Math.PI - 180) % 360) + 540) % 360 - 180;
          onSurfaceSelect(latitude, longitude);
        }}
      >
        <sphereGeometry args={[1, 96, 64]} />
        <meshStandardMaterial map={texture ?? undefined} color={texture ? "#ffffff" : "#16405e"} roughness={0.9} />
      </mesh>
      {markers.map((m) => (
        <Pin
          key={m.id}
          lat={m.latitude}
          lon={m.longitude}
          color={m.color}
          size={m.id === selectedId ? 0.026 : 0.017}
          onClick={() => onSelect(m.id)}
        />
      ))}
      {device && <Pin lat={device.latitude} lon={device.longitude} color="#38bdf8" size={0.022} />}
      {zones?.map((zone) => <ZoneOutline key={zone.id} zone={zone} />)}
      {weather && <WeatherGlyph weather={weather} />}
      {pulsing && <PulseRing latitude={pulsing.latitude} longitude={pulsing.longitude} color={pulsing.color} />}
      <OrbitControls
        ref={controlsRef as never}
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minDistance={MIN_D}
        maxDistance={MAX_D}
        zoomSpeed={0.8}
        rotateSpeed={0.5}
      />
    </>
  );
}

export default function ObservationGlobe({
  markers,
  selectedId,
  onSelect,
  focus,
  onSurfaceSelect,
  weather,
  zones,
  pulseId,
  sunDate,
  onDeviceLocation,
}: Props) {
  const [texture, setTexture] = useState<THREE.Texture | null>(null);
  const [now, setNow] = useState(() => new Date());
  const [device, setDevice] = useState<Device | null>(null);
  const [gpsMsg, setGpsMsg] = useState<string | null>(null);
  const [manual, setManual] = useState({ lat: "", lon: "" });
  const apiRef = useRef<CameraApi | null>(null);
  const gl = useMemo(() => webglAvailable(), []);
  const tz = useMemo(() => browserTimeZone(), []);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!gl) return;
    let alive = true;
    fetch("/world-land-110m.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("land data unavailable"))))
      .then((topo: LandTopology) => {
        if (alive) setTexture(landTexture(decodeLandRings(topo)));
      })
      .catch(() => undefined); // degraded mode: plain ocean sphere + markers
    return () => {
      alive = false;
    };
  }, [gl]);

  useEffect(() => {
    if (focus) apiRef.current?.focus(focus.latitude, focus.longitude, focus.distance);
  }, [focus]);

  const sun = useMemo(() => {
    const s = subsolarPoint(sunDate ?? now);
    return latLonToXYZ(s.latitude, s.longitude, 1);
  }, [now, sunDate]);

  const place = useCallback(
    (lat: number, lon: number, accuracy: number, msg: string, source: "gps" | "manual") => {
      const d = { latitude: coarsen(lat), longitude: coarsen(lon), accuracy, at: Date.now() };
      setDevice(d);
      setGpsMsg(msg);
      apiRef.current?.focus(d.latitude, d.longitude);
      onDeviceLocation?.(d.latitude, d.longitude, source);
    },
    [onDeviceLocation],
  );

  const locate = () => {
    if (!("geolocation" in navigator)) {
      setGpsMsg("Geolocation is not available in this browser. Enter coordinates instead.");
      return;
    }
    setGpsMsg("Requesting location…");
    navigator.geolocation.getCurrentPosition(
      (p) =>
        place(
          p.coords.latitude,
          p.coords.longitude,
          p.coords.accuracy,
          onDeviceLocation
            ? "Device location, coarsened to ~1 km. Only that coarsened point leaves the browser (for weather)."
            : "Device location (coarsened to ~1 km; not stored or sent).",
          "gps",
        ),
      (err) =>
        setGpsMsg(
          err.code === err.PERMISSION_DENIED
            ? "Location permission denied. Enter coordinates manually."
            : "Could not determine location. Enter coordinates manually.",
        ),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  };

  const applyManual = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = Number(manual.lat);
    const lon = Number(manual.lon);
    if (manual.lat.trim() === "" || manual.lon.trim() === "" || !validCoordinates(lat, lon)) {
      setGpsMsg("Enter a latitude between -90 and 90 and a longitude between -180 and 180.");
      return;
    }
    place(lat, lon, 0, "Manual location (coarsened to ~1 km).", "manual");
  };

  const selected = markers.find((m) => m.id === selectedId) ?? null;
  const focusPoint = selected ?? device;

  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-4 mb-4">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div>
          <h2 className="text-sm text-ink-primary">Global view</h2>
          <p className="text-[11px] text-ink-muted">
            Drag to rotate · scroll or pinch to zoom · click a pin to select it. The lit side is the approximate
            daylight hemisphere.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={locate}
            className="flex items-center gap-1.5 rounded-md border border-accent-cyan/40 bg-accent-cyan/15 px-2.5 py-1.5 text-[11px] text-accent-cyan hover:bg-accent-cyan/25"
          >
            <LocateFixed size={13} aria-hidden="true" /> Use my location
          </button>
          <button
            type="button"
            aria-label="Zoom in"
            onClick={() => apiRef.current?.zoom(0.75)}
            className="rounded-md border border-surface-border p-1.5 text-ink-body hover:border-accent-cyan"
          >
            <Plus size={13} />
          </button>
          <button
            type="button"
            aria-label="Zoom out"
            onClick={() => apiRef.current?.zoom(1.33)}
            className="rounded-md border border-surface-border p-1.5 text-ink-body hover:border-accent-cyan"
          >
            <Minus size={13} />
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div
          className="relative h-[420px] rounded-xl border border-surface-border bg-[#050d16] overflow-hidden"
          data-testid="globe-canvas"
        >
          {gl ? (
            <Canvas
              frameloop="demand"
              dpr={[1, 1.75]}
              camera={{ position: [0, 0.4, 3.2], fov: 45, near: 0.0005, far: 100 }}
            >
              <CameraBridge apiRef={apiRef} />
              <Scene
                markers={markers}
                selectedId={selectedId}
                onSelect={onSelect}
                device={device}
                texture={texture}
                sun={sun}
                onSurfaceSelect={onSurfaceSelect}
                weather={weather}
                zones={zones}
                pulseId={pulseId}
              />
            </Canvas>
          ) : (
            <p className="p-6 text-[12px] text-ink-muted">
              WebGL is not available in this browser, so the globe cannot render. The observation plot below still
              works.
            </p>
          )}
        </div>

        <div className="space-y-3 text-[11px]">
          <form onSubmit={applyManual} className="rounded-xl border border-surface-border bg-surface-bg p-3">
            <div className="flex items-center gap-1.5 text-ink-primary mb-2">
              <Crosshair size={12} aria-hidden="true" /> Manual location
            </div>
            <div className="flex gap-2">
              <input
                aria-label="Latitude"
                placeholder="Lat"
                inputMode="decimal"
                value={manual.lat}
                onChange={(e) => setManual({ ...manual, lat: e.target.value })}
                className="w-full rounded border border-surface-border bg-surface-raised px-2 py-1 text-ink-body"
              />
              <input
                aria-label="Longitude"
                placeholder="Lon"
                inputMode="decimal"
                value={manual.lon}
                onChange={(e) => setManual({ ...manual, lon: e.target.value })}
                className="w-full rounded border border-surface-border bg-surface-raised px-2 py-1 text-ink-body"
              />
              <button
                type="submit"
                className="rounded border border-surface-border px-2 text-ink-body hover:border-accent-cyan"
              >
                Go
              </button>
            </div>
            {gpsMsg && (
              <p role="status" className="mt-2 text-ink-muted">
                {gpsMsg}
              </p>
            )}
            {device && (
              <p className="mt-2 text-ink-body">
                {device.latitude.toFixed(2)}, {device.longitude.toFixed(2)}
                {device.accuracy > 0 && ` · ±${Math.round(device.accuracy)} m`}
              </p>
            )}
          </form>

          <div className="rounded-xl border border-surface-border bg-surface-bg p-3">
            <div className="text-ink-primary mb-2">Local time</div>
            <dl className="space-y-1">
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">You ({tz})</dt>
                <dd className="text-ink-body">{formatInZone(now, tz)}</dd>
              </div>
              {focusPoint && (
                <div className="flex justify-between gap-2">
                  <dt className="text-ink-muted">{selected ? "Selected pin" : "Chosen point"}</dt>
                  <dd className="text-ink-body">{formatSolar(now, focusPoint.longitude)}</dd>
                </div>
              )}
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">UTC</dt>
                <dd className="text-ink-body">{formatInZone(now, "UTC")}</dd>
              </div>
            </dl>
            <ul className="mt-2 pt-2 border-t border-surface-border space-y-1">
              {WORLD_CLOCK_ZONES.map((z) => (
                <li key={z} className="flex justify-between gap-2">
                  <span className="text-ink-muted">{z.split("/")[1].replace(/_/g, " ")}</span>
                  <span className="text-ink-body">{formatInZone(now, z)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[10px] text-ink-faint">
              Pin times are mean-solar approximations from longitude. Named zones use the browser's IANA database.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
