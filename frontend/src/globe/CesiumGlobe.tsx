/**
 * Realistic 3D Earth (CesiumJS): Esri World Imagery satellite tiles with Esri place names and
 * borders on top, sun-lit atmosphere, and Cesium's bundled Natural Earth II layer underneath as
 * a fallback if the imagery service is unreachable. No Cesium ion services are used, so no
 * access token is needed.
 *
 * Each OneAquaHealth research city is pointed out with a glowing beacon, a labelled pin and an
 * info card holding its demonstration-matrix row (values computed live by the engine). Its
 * exposure zone and citizen reports are drawn on the satellite imagery, so flying in shows the
 * real river reach. If WebGL or the CesiumJS CDN is unavailable, `fallback` renders instead.
 */
import { Globe2, LocateFixed, Minus, Plus } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { webglAvailable } from "../cardiotwin/HeartViewer";
import { compass } from "../oahbridge/format";
import { type CesiumNamespace, loadCesium } from "./cesiumLoader";
import { coarsen } from "./geo";
import { type GlobeWeather, temperatureHex } from "./weatherLayers";

export interface CityPin {
  id: string;
  name: string;
  basin: string;
  country: string;
  latitude: number;
  longitude: number;
  color: string;
  hazard: string;
  status: string;
  score: number;
  sub: { cs: number; cc: number; ct: number };
  cohort: string;
  outcome: string;
  inputs: string[];
  /** Closed ring of [longitude, latitude] pairs. */
  zone?: [number, number][];
  reports?: { id: string; latitude: number; longitude: number; label: string }[];
  /** Which side of the pin the label sits on (keeps nearby cities readable). */
  labelSide?: "left" | "right";
}

interface Props {
  pins: CityPin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** "overview" frames all cities; "city" flies to the selected city's exposure zone. Bump focusKey to re-fly. */
  focusMode: "overview" | "city";
  focusKey: number;
  weather?: GlobeWeather | null;
  /** Lighting time for forecast playback; null = real time. */
  time?: Date | null;
  onSurfaceSelect?: (latitude: number, longitude: number) => void;
  onDeviceLocation?: (latitude: number, longitude: number, source: "gps") => void;
  /** Rendered when WebGL or the CesiumJS CDN is unavailable. */
  fallback: ReactNode;
  height?: number;
}

const ESRI_IMAGERY =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_LABELS =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";
const ESRI_CREDIT = "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community";

const OVERVIEW = { lon: -3.6, lat: 29.8, height: 1_250_000, pitchDeg: -40 };
const BEACON_HEIGHT_M = 120_000;
const WEATHER_ID = "__weather__";
const DEVICE_ID = "__device__";

// Info cards render in Cesium's iframe. Its document must share the page's dark colour scheme,
// otherwise Chrome paints an opaque white canvas behind the (light) text.
const FRAME_STYLE =
  "<style>:root{color-scheme:dark}html,body{background:transparent;color:#f8fafc;font-family:Inter,system-ui,sans-serif}</style>";

function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);
}

/** Info-card HTML for a city: its row of the multi-city demonstration matrix. */
export function cityCardHtml(pin: CityPin): string {
  const rows: [string, string][] = [
    ["City &amp; water basin", `${esc(pin.name)} (${esc(pin.basin)})${pin.country ? ` · ${esc(pin.country)}` : ""}`],
    ["Target hazard", esc(pin.hazard)],
    ["Key telemetry inputs", pin.inputs.map(esc).join("<br>") || "—"],
    [
      "Epistemic status &amp; score",
      `${esc(pin.status)} · S = ${pin.score.toFixed(2)}<br>(Cs = ${pin.sub.cs.toFixed(2)}, Cc = ${pin.sub.cc.toFixed(2)}, Ct = ${pin.sub.ct.toFixed(2)})`,
    ],
    ["Exposed cohort", esc(pin.cohort)],
    ["Clinical outcome context", esc(pin.outcome)],
  ];
  return [
    FRAME_STYLE,
    "<style>body{margin:8px}table{border-collapse:collapse;width:100%;font-size:12px}",
    "th{text-align:left;vertical-align:top;color:#94a3b8;font-weight:500;padding:5px 10px 5px 0;white-space:nowrap}",
    "td{padding:5px 0;color:#f8fafc}p{margin:10px 0 0;font-size:11px;color:#94a3b8}</style><table>",
    rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join(""),
    "</table><p>Synthetic demonstration scenario. Values are computed live by the OAH-Bridge engine. Informational context, not a diagnosis.</p>",
  ].join("");
}

export function weatherLabel(w: GlobeWeather): string {
  const when = w.atUtc
    ? `${new Date(w.atUtc).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC`
    : "now";
  const sky = w.precipitationMm > 0 ? `rain ${w.precipitationMm.toFixed(1)} mm/h` : w.cloudCover > 60 ? "cloudy, dry" : "dry";
  const temp = w.temperatureC == null ? "—" : w.temperatureC.toFixed(1);
  return `${temp} °C · ${sky}\nwind ${Math.round(w.windSpeedKmh)} km/h from ${compass(w.windDirectionDeg)} · ${when}`;
}

// The CDN build is untyped; keep Cesium objects as `any` locally.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

export default function CesiumGlobe({
  pins,
  selectedId,
  onSelect,
  focusMode,
  focusKey,
  weather,
  time,
  onSurfaceSelect,
  onDeviceLocation,
  fallback,
  height = 560,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const coordsRef = useRef<HTMLSpanElement>(null);
  const viewerRef = useRef<Any>(null);
  const cesiumRef = useRef<CesiumNamespace>(null);
  const pinIdsRef = useRef<Set<string>>(new Set());
  const onSelectRef = useRef(onSelect);
  const onSurfaceRef = useRef(onSurfaceSelect);
  onSelectRef.current = onSelect;
  onSurfaceRef.current = onSurfaceSelect;

  const [status, setStatus] = useState<"loading" | "ready" | "failed">(() => (webglAvailable() ? "loading" : "failed"));
  const [failure, setFailure] = useState<string | null>(null);
  const [gpsMsg, setGpsMsg] = useState<string | null>(null);

  // Create the viewer once.
  useEffect(() => {
    if (!webglAvailable()) return;
    let cancelled = false;
    let viewer: Any = null;
    let handler: Any = null;

    loadCesium()
      .then((C: Any) => {
        if (cancelled || !container.current) return;
        cesiumRef.current = C;
        C.Ion.defaultAccessToken = "";
        viewer = new C.Viewer(container.current, {
          baseLayer: false,
          baseLayerPicker: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          animation: false,
          timeline: false,
          fullscreenButton: false,
          infoBox: true,
          selectionIndicator: true,
          shouldAnimate: true,
        });
        viewerRef.current = viewer;

        const layers = viewer.imageryLayers;
        // Offline-safe backdrop shipped with Cesium, then real satellite imagery, then place names.
        layers.add(
          C.ImageryLayer.fromProviderAsync(
            C.TileMapServiceImageryProvider.fromUrl(C.buildModuleUrl("Assets/Textures/NaturalEarthII")),
          ),
        );
        layers.addImageryProvider(
          new C.UrlTemplateImageryProvider({ url: ESRI_IMAGERY, maximumLevel: 19, credit: new C.Credit(ESRI_CREDIT) }),
        );
        layers.addImageryProvider(
          new C.UrlTemplateImageryProvider({
            url: ESRI_LABELS,
            maximumLevel: 19,
            credit: new C.Credit("Places and boundaries © Esri"),
          }),
        );

        const scene = viewer.scene;
        scene.globe.enableLighting = true; // sun-lit from orbit; fully lit when zoomed in
        scene.globe.showGroundAtmosphere = true;
        scene.skyAtmosphere.show = true;
        scene.fog.enabled = true;
        scene.screenSpaceCameraController.minimumZoomDistance = 250;
        scene.screenSpaceCameraController.maximumZoomDistance = 30_000_000;

        viewer.camera.setView({
          destination: C.Cartesian3.fromDegrees(OVERVIEW.lon, OVERVIEW.lat, OVERVIEW.height),
          orientation: { heading: 0, pitch: C.Math.toRadians(OVERVIEW.pitchDeg), roll: 0 },
        });

        handler = new C.ScreenSpaceEventHandler(scene.canvas);
        handler.setInputAction((movement: Any) => {
          const picked = scene.pick(movement.position);
          const rawId = C.defined(picked) && picked.id && typeof picked.id.id === "string" ? picked.id.id : null;
          if (rawId) {
            const cityId = rawId.split("::")[0];
            if (pinIdsRef.current.has(cityId)) {
              onSelectRef.current(cityId);
              return;
            }
          }
          const cartesian = viewer.camera.pickEllipsoid(movement.position, scene.globe.ellipsoid);
          if (cartesian && onSurfaceRef.current) {
            const carto = C.Cartographic.fromCartesian(cartesian);
            onSurfaceRef.current(C.Math.toDegrees(carto.latitude), C.Math.toDegrees(carto.longitude));
          }
        }, C.ScreenSpaceEventType.LEFT_CLICK);
        handler.setInputAction((movement: Any) => {
          const cartesian = viewer.camera.pickEllipsoid(movement.endPosition, scene.globe.ellipsoid);
          if (!coordsRef.current) return;
          if (!cartesian) {
            coordsRef.current.textContent = "Move over the globe";
            return;
          }
          const carto = C.Cartographic.fromCartesian(cartesian);
          const lat = C.Math.toDegrees(carto.latitude);
          const lon = C.Math.toDegrees(carto.longitude);
          const altKm = viewer.camera.positionCartographic.height / 1000;
          coordsRef.current.textContent = `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"} · eye ${altKm >= 10 ? altKm.toFixed(0) : altKm.toFixed(1)} km`;
        }, C.ScreenSpaceEventType.MOUSE_MOVE);

        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setFailure(err instanceof Error ? err.message : "CesiumJS failed to start");
        setStatus("failed");
      });

    return () => {
      cancelled = true;
      handler?.destroy();
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // City pins, beacons, exposure zones and citizen reports.
  useEffect(() => {
    const C = cesiumRef.current;
    const viewer = viewerRef.current;
    if (status !== "ready" || !C || !viewer) return;
    const added: Any[] = [];
    const ids = new Set<string>();
    const zoneColor = C.Color.fromCssColorString("#22d3ee");

    for (const pin of pins) {
      ids.add(pin.id);
      const color = C.Color.fromCssColorString(pin.color);
      const left = pin.labelSide === "left";
      added.push(
        viewer.entities.add({
          id: pin.id,
          name: `${pin.name} · ${pin.hazard}`,
          position: C.Cartesian3.fromDegrees(pin.longitude, pin.latitude, 0),
          point: {
            pixelSize: 15,
            color,
            outlineColor: C.Color.WHITE,
            outlineWidth: 3,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: `${pin.name}\n${pin.status} · S ${pin.score.toFixed(2)}`,
            font: "600 14px Inter, system-ui, sans-serif",
            fillColor: C.Color.WHITE,
            showBackground: true,
            backgroundColor: C.Color.fromCssColorString("#0b1220").withAlpha(0.82),
            backgroundPadding: new C.Cartesian2(9, 6),
            horizontalOrigin: left ? C.HorizontalOrigin.RIGHT : C.HorizontalOrigin.LEFT,
            verticalOrigin: C.VerticalOrigin.CENTER,
            pixelOffset: new C.Cartesian2(left ? -16 : 16, 0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            scaleByDistance: new C.NearFarScalar(150_000, 1.0, 9_000_000, 0.75),
          },
          description: cityCardHtml(pin),
        }),
      );
      added.push(
        viewer.entities.add({
          id: `${pin.id}::beacon`,
          name: `${pin.name} · ${pin.hazard}`,
          polyline: {
            positions: C.Cartesian3.fromDegreesArrayHeights([
              pin.longitude, pin.latitude, 0,
              pin.longitude, pin.latitude, BEACON_HEIGHT_M,
            ]),
            width: 7,
            arcType: C.ArcType.NONE,
            material: new C.PolylineGlowMaterialProperty({ glowPower: 0.3, color }),
            distanceDisplayCondition: new C.DistanceDisplayCondition(40_000, 40_000_000),
          },
          description: cityCardHtml(pin),
        }),
      );
      if (pin.zone && pin.zone.length > 2) {
        added.push(
          viewer.entities.add({
            id: `${pin.id}::zone`,
            name: `${pin.name} · exposure zone`,
            polygon: {
              hierarchy: C.Cartesian3.fromDegreesArray(pin.zone.flatMap(([lon, lat]) => [lon, lat])),
              material: zoneColor.withAlpha(0.33),
              height: 0,
            },
            description: cityCardHtml(pin),
          }),
        );
        added.push(
          viewer.entities.add({
            id: `${pin.id}::outline`,
            polyline: {
              positions: C.Cartesian3.fromDegreesArrayHeights(pin.zone.flatMap(([lon, lat]) => [lon, lat, 4])),
              width: 3,
              material: zoneColor,
              arcType: C.ArcType.GEODESIC,
            },
          }),
        );
      }
      for (const report of pin.reports ?? []) {
        added.push(
          viewer.entities.add({
            id: `${pin.id}::report::${report.id}`,
            name: report.label,
            position: C.Cartesian3.fromDegrees(report.longitude, report.latitude, 3),
            point: {
              pixelSize: 9,
              color: C.Color.fromCssColorString("#f59e0b"),
              outlineColor: C.Color.WHITE,
              outlineWidth: 2,
              distanceDisplayCondition: new C.DistanceDisplayCondition(0, 80_000),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            description: `${FRAME_STYLE}<p>${esc(report.label)}</p><p style="font-size:11px;color:#94a3b8">Synthetic citizen report</p>`,
          }),
        );
      }
    }
    pinIdsRef.current = ids;
    return () => {
      for (const entity of added) viewer.entities.remove(entity);
    };
  }, [status, pins]);

  // Picking a city opens its matrix card; the overview stays uncluttered.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (status !== "ready" || !viewer) return;
    viewer.selectedEntity =
      focusMode === "city" && selectedId ? viewer.entities.getById(selectedId) : undefined;
  }, [status, selectedId, pins, focusMode, focusKey]);

  // Camera: overview of all cities, or a fly-in to the selected exposure zone.
  useEffect(() => {
    const C = cesiumRef.current;
    const viewer = viewerRef.current;
    if (status !== "ready" || !C || !viewer) return;
    if (focusMode === "overview" || !selectedId) {
      viewer.camera.flyTo({
        destination: C.Cartesian3.fromDegrees(OVERVIEW.lon, OVERVIEW.lat, OVERVIEW.height),
        orientation: { heading: 0, pitch: C.Math.toRadians(OVERVIEW.pitchDeg), roll: 0 },
        duration: 2.5,
      });
      return;
    }
    const target = viewer.entities.getById(`${selectedId}::zone`) ?? viewer.entities.getById(selectedId);
    if (target) {
      void viewer.flyTo(target, { duration: 3.2, offset: new C.HeadingPitchRange(0, C.Math.toRadians(-38), 4200) });
    }
  }, [status, focusMode, focusKey, selectedId]);

  // Weather at the chosen point.
  useEffect(() => {
    const C = cesiumRef.current;
    const viewer = viewerRef.current;
    if (status !== "ready" || !C || !viewer) return;
    const old = viewer.entities.getById(WEATHER_ID);
    if (old) viewer.entities.remove(old);
    if (!weather) return;
    viewer.entities.add({
      id: WEATHER_ID,
      name: "Weather context (Open-Meteo)",
      position: C.Cartesian3.fromDegrees(weather.longitude, weather.latitude, 30),
      point: {
        pixelSize: 11,
        color: C.Color.fromCssColorString(temperatureHex(weather.temperatureC)),
        outlineColor: C.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: weatherLabel(weather),
        font: "500 12px Inter, system-ui, sans-serif",
        fillColor: C.Color.WHITE,
        showBackground: true,
        backgroundColor: C.Color.fromCssColorString("#0b1220").withAlpha(0.85),
        backgroundPadding: new C.Cartesian2(8, 5),
        verticalOrigin: C.VerticalOrigin.TOP,
        // Below the city pin and its label, which sit beside the same point.
        pixelOffset: new C.Cartesian2(0, 40),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        // Keep the overview clean: the weather label appears once you zoom towards the point.
        distanceDisplayCondition: new C.DistanceDisplayCondition(0, 1_200_000),
      },
      description: `${FRAME_STYLE}<p>Live Open-Meteo weather for this point. Context only, not evidence of a hazard, an exposure or an illness.</p>`,
    });
  }, [status, weather]);

  // Lighting clock: real time, or the forecast hour being played.
  useEffect(() => {
    const C = cesiumRef.current;
    const viewer = viewerRef.current;
    if (status !== "ready" || !C || !viewer) return;
    if (time) {
      viewer.clock.currentTime = C.JulianDate.fromDate(time);
      viewer.clock.shouldAnimate = false;
    } else {
      viewer.clock.currentTime = C.JulianDate.now();
      viewer.clock.shouldAnimate = true;
    }
  }, [status, time]);

  const flyOverview = useCallback(() => {
    const C = cesiumRef.current;
    const viewer = viewerRef.current;
    if (!C || !viewer) return;
    viewer.camera.flyTo({
      destination: C.Cartesian3.fromDegrees(OVERVIEW.lon, OVERVIEW.lat, OVERVIEW.height),
      orientation: { heading: 0, pitch: C.Math.toRadians(OVERVIEW.pitchDeg), roll: 0 },
      duration: 2,
    });
  }, []);

  const zoom = useCallback((inward: boolean) => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const h = viewer.camera.positionCartographic.height;
    if (inward) viewer.camera.zoomIn(h * 0.45);
    else viewer.camera.zoomOut(h * 0.8);
  }, []);

  const locate = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setGpsMsg("Geolocation is not available in this browser.");
      return;
    }
    setGpsMsg("Requesting your location…");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const lat = coarsen(p.coords.latitude);
        const lon = coarsen(p.coords.longitude);
        setGpsMsg(`You are near ${lat.toFixed(2)}, ${lon.toFixed(2)} (coarsened to ~1 km; only this point is used, for weather).`);
        const C = cesiumRef.current;
        const viewer = viewerRef.current;
        if (C && viewer) {
          const old = viewer.entities.getById(DEVICE_ID);
          if (old) viewer.entities.remove(old);
          viewer.entities.add({
            id: DEVICE_ID,
            name: "Your location (~1 km)",
            position: C.Cartesian3.fromDegrees(lon, lat, 10),
            point: {
              pixelSize: 13,
              color: C.Color.fromCssColorString("#38bdf8"),
              outlineColor: C.Color.WHITE,
              outlineWidth: 3,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            label: {
              text: "You (~1 km)",
              font: "600 13px Inter, system-ui, sans-serif",
              fillColor: C.Color.WHITE,
              showBackground: true,
              backgroundColor: C.Color.fromCssColorString("#0369a1").withAlpha(0.85),
              pixelOffset: new C.Cartesian2(0, -24),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          });
          viewer.camera.flyTo({ destination: C.Cartesian3.fromDegrees(lon, lat, 80_000), duration: 2.5 });
        }
        onDeviceLocation?.(lat, lon, "gps");
      },
      (err) =>
        setGpsMsg(err.code === err.PERMISSION_DENIED ? "Location permission denied." : "Could not determine your location."),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  }, [onDeviceLocation]);

  if (status === "failed") {
    return (
      <div>
        <p className="mb-2 text-[11px] text-amber-300">
          Realistic satellite globe unavailable ({failure ?? "WebGL is not available in this browser"}). Showing the offline
          globe instead.
        </p>
        {fallback}
      </div>
    );
  }

  const button =
    "flex items-center gap-1.5 rounded-md border border-white/20 bg-black/60 px-2.5 py-1.5 text-[11px] text-slate-100 backdrop-blur hover:border-cyan-300";

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-surface-border bg-black"
      style={{ height }}
      data-testid="cesium-globe"
    >
      <div ref={container} className="absolute inset-0" />
      {status === "loading" && (
        <div className="absolute inset-0 grid place-items-center text-xs text-slate-300">Loading the satellite globe…</div>
      )}
      <div className="absolute left-3 top-3 z-10 flex flex-col items-start gap-1.5">
        <button type="button" onClick={flyOverview} className={button}>
          <Globe2 size={13} aria-hidden="true" /> All cities
        </button>
        <button type="button" onClick={locate} className={button}>
          <LocateFixed size={13} aria-hidden="true" /> Use my location
        </button>
        <div className="flex gap-1.5">
          <button type="button" aria-label="Zoom in" onClick={() => zoom(true)} className={button}>
            <Plus size={13} />
          </button>
          <button type="button" aria-label="Zoom out" onClick={() => zoom(false)} className={button}>
            <Minus size={13} />
          </button>
        </div>
      </div>
      {gpsMsg && (
        <div role="status" className="absolute bottom-11 right-3 z-10 max-w-xs rounded-md bg-black/70 px-2.5 py-1.5 text-[11px] text-slate-100">
          {gpsMsg}
        </div>
      )}
      <div className="pointer-events-none absolute bottom-3 right-3 z-10 rounded bg-black/60 px-2 py-1 font-mono text-[10px] text-slate-200">
        <span ref={coordsRef}>Move over the globe</span>
      </div>
    </div>
  );
}
