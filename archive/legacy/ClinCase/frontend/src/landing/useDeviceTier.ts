/**
 * Decides whether the visitor gets the real WebGL Aperture scene or the
 * static SVG backdrop -- a good fallback beats a stuttering 3D scene.
 *
 * Ported from frontend/LANDING/landing/useDeviceTier.ts. Starts at "checking"
 * so nothing WebGL-shaped is constructed during the first paint; the static
 * backdrop covers that frame.
 */
import { useEffect, useState } from "react";

export type DeviceTier = "high" | "low" | "checking";

export function useDeviceTier(): DeviceTier {
  const [tier, setTier] = useState<DeviceTier>("checking");

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTier("low");
      return;
    }

    let hasWebGL = false;
    try {
      const canvas = document.createElement("canvas");
      hasWebGL = !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
    } catch {
      hasWebGL = false;
    }

    const cores = navigator.hardwareConcurrency ?? 4;
    const isSmallViewport = window.innerWidth < 640;

    setTier(hasWebGL && cores >= 4 && !isSmallViewport ? "high" : "low");
  }, []);

  return tier;
}
