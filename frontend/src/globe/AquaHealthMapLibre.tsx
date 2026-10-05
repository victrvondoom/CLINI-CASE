import { useEffect, useRef } from "react";
import { LngLatBounds, Map as MapLibreMap, Marker, NavigationControl, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";

import type { MapPoint } from "../aquahealth/types";

setWorkerUrl(workerUrl);

const STATUS_COLOR: Record<MapPoint["status"], string> = {
  critical_signal: "#ef4444",
  potential_stress: "#f59e0b",
  watch: "#3b82f6",
  healthy_signal: "#22c55e",
  insufficient_data: "#94a3b8",
};

interface Props {
  points: MapPoint[];
  selectedId: string | null;
  onSelect: (point: MapPoint) => void;
  viewBounds?: [[number, number], [number, number]];
  onCoordinateClick?: (longitude: number, latitude: number) => void;
}

export default function AquaHealthMapLibre({ points, selectedId, onSelect, viewBounds, onCoordinateClick }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);

  useEffect(() => {
    if (!container.current) return;
    const first = points[0];
    const instance = new MapLibreMap({
      container: container.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: first ? [first.longitude, first.latitude] : [-8.4265, 40.2033],
      zoom: first ? 11 : 5,
      attributionControl: {},
    });
    instance.addControl(new NavigationControl(), "top-right");
    if (onCoordinateClick) {
      instance.on("click", (event) => onCoordinateClick(event.lngLat.lng, event.lngLat.lat));
    }
    map.current = instance;
    return () => {
      markers.current.forEach((marker) => marker.remove());
      markers.current = [];
      instance.remove();
      map.current = null;
    };
    // Initialize once; markers and camera are updated in the following effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onCoordinateClick]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    markers.current.forEach((marker) => marker.remove());
    markers.current = points.map((point) => {
      const node = document.createElement("button");
      const isSelected = point.observation_id === selectedId;
      node.type = "button";
      node.className = "aqua-map-marker";
      node.setAttribute("aria-label", `${point.reference} at ${point.waterbody_name}; ${point.status.replaceAll("_", " ")}`);
      node.style.backgroundColor = STATUS_COLOR[point.status];
      node.style.width = isSelected ? "22px" : "16px";
      node.style.height = isSelected ? "22px" : "16px";
      node.style.border = "2px solid white";
      node.style.borderRadius = "9999px";
      node.style.boxShadow = "0 1px 5px #0008";
      node.style.cursor = "pointer";
      node.addEventListener("click", () => onSelect(point));
      return new Marker({ element: node, anchor: "center" })
        .setLngLat([point.longitude, point.latitude])
        .addTo(instance);
    });
  }, [points, selectedId, onSelect]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    if (viewBounds) {
      instance.fitBounds(viewBounds, { padding: 48, maxZoom: 5, duration: 650 });
    } else if (points.length > 1) {
      const bounds = points.reduce(
        (result, point) => result.extend([point.longitude, point.latitude] as [number, number]),
        new LngLatBounds([points[0].longitude, points[0].latitude], [points[0].longitude, points[0].latitude]),
      );
      instance.fitBounds(bounds, { padding: 48, maxZoom: 12, duration: 0 });
    } else if (points[0]) {
      instance.flyTo({ center: [points[0].longitude, points[0].latitude], zoom: 12, duration: 0 });
    }
  }, [points, viewBounds]);

  return (
    <div className="overflow-hidden rounded-xl border border-surface-border">
      <div ref={container} className="h-[360px] w-full" role="region" aria-label="MapLibre OpenStreetMap observations" />
      <p className="border-t border-surface-border bg-surface-raised px-3 py-2 text-[10px] text-ink-faint">Map tiles: OpenFreeMap · map data © OpenStreetMap contributors · selecting a marker opens the corresponding observation.</p>
    </div>
  );
}
