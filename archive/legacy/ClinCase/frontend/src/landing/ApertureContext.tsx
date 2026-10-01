/**
 * Shared state between the DOM sections and the fixed WebGL canvas.
 *
 * Ported from frontend/LANDING/landing/ApertureContext.tsx: same contract,
 * with framer-motion MotionValues swapped for the local Signal primitive
 * (see useScrollProgress.ts).
 *
 * `scrollYProgress` drives the camera choreography (Aperture3D CameraRig) and
 * `pulse` is how a hovered HowItWorks step tells the crystal to visibly
 * ripple -- the one place the 3D object and the DOM content connect.
 */
import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";

import { createSignal, useSmoothScrollProgress, type Signal } from "./useScrollProgress";

interface ApertureContextValue {
  scrollYProgress: Signal;
  pulse: Signal;
  triggerPulse: () => void;
}

const ApertureCtx = createContext<ApertureContextValue | null>(null);

export function ApertureProvider({ children }: { children: ReactNode }) {
  const scrollYProgress = useSmoothScrollProgress();
  const pulse = useMemo(() => createSignal(0), []);
  const pulseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (pulseTimeout.current) clearTimeout(pulseTimeout.current);
  }, []);

  const value = useMemo<ApertureContextValue>(
    () => ({
      scrollYProgress,
      pulse,
      triggerPulse: () => {
        pulse.set(1);
        if (pulseTimeout.current) clearTimeout(pulseTimeout.current);
        pulseTimeout.current = setTimeout(() => pulse.set(0), 900);
      },
    }),
    [scrollYProgress, pulse],
  );

  return <ApertureCtx.Provider value={value}>{children}</ApertureCtx.Provider>;
}

/** Safe outside the provider: returns null so sections stay reusable. */
export function useApertureOptional(): ApertureContextValue | null {
  return useContext(ApertureCtx);
}

export function useAperture(): ApertureContextValue {
  const ctx = useContext(ApertureCtx);
  if (!ctx) throw new Error("useAperture must be used within an ApertureProvider");
  return ctx;
}
