/**
 * Scroll plumbing for the landing page's WebGL scene.
 *
 * The original Next.js landing drove the R3F camera from framer-motion
 * MotionValues. framer-motion is not a dependency of this app and pulling it
 * in for two numbers would be a lot of bundle for nothing, so this provides
 * the same `.get()` / `.set()` surface the scene already reads -- Aperture3D's
 * CameraRig and ApertureCrystal are used verbatim against it.
 *
 * Values live on a mutable object rather than in React state on purpose: the
 * scene samples them inside useFrame, so a scroll must never cost a React
 * render. Nothing here re-renders the page while you scroll.
 */
import { useEffect, useMemo, useRef } from "react";

/** The slice of framer-motion's MotionValue API the Aperture scene uses. */
export interface Signal {
  get(): number;
  set(v: number): void;
}

export function createSignal(initial = 0): Signal {
  let value = initial;
  return {
    get: () => value,
    set: (v: number) => {
      value = v;
    },
  };
}

/**
 * Document scroll progress in [0,1], critically damped toward the raw value.
 *
 * This is the "scroll interpolation" layer: the page itself scrolls natively
 * (no scroll-jacking, no transform hijack, wheel/keyboard/trackpad untouched),
 * while the *signal the 3D scene reads* trails the real scroll position
 * slightly. That is what makes the camera glide instead of snapping on every
 * wheel tick, and it costs one rAF that parks itself when nothing is moving.
 */
export function useSmoothScrollProgress(): Signal {
  const signal = useMemo(() => createSignal(0), []);
  const raw = useRef(0);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    let frame = 0;
    let running = false;

    const measure = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      raw.current = max > 0 ? Math.min(Math.max(window.scrollY / max, 0), 1) : 0;
    };

    const tick = () => {
      const target = raw.current;
      const current = signal.get();
      const delta = target - current;

      // Close enough: settle exactly and stop burning frames until next scroll.
      if (Math.abs(delta) < 0.0001) {
        signal.set(target);
        running = false;
        return;
      }

      signal.set(current + delta * 0.12);
      frame = requestAnimationFrame(tick);
    };

    const start = () => {
      if (running) return;
      running = true;
      frame = requestAnimationFrame(tick);
    };

    const onScroll = () => {
      measure();
      // Reduced motion: no easing, the camera tracks scroll 1:1.
      if (reduced.matches) {
        signal.set(raw.current);
        return;
      }
      start();
    };

    measure();
    signal.set(raw.current);

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, [signal]);

  return signal;
}
