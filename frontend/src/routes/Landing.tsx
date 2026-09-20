/**
 * / — public marketing landing page.
 *
 * Ported from the Next.js "aperture" landing (frontend/LANDING/landing) onto
 * this app's stack: react-router links instead of next/link, and an
 * IntersectionObserver Reveal instead of framer-motion. The react-three-fiber
 * scene is the real one from the original design — see landing/Aperture3D.tsx.
 * Runs its own dark palette, scoped under .aperture-root so it never touches
 * the app's theme tokens.
 *
 * Reachable signed-out; signed-in visitors get "Go to dashboard" CTAs instead
 * of sign-up prompts.
 */
import { Component, Suspense, lazy, useEffect } from "react";
import type { ReactNode } from "react";

import { ApertureProvider, useAperture } from "../landing/ApertureContext";
import ApertureBackdrop from "../landing/ApertureBackdrop";
import FinalCTA from "../landing/FinalCTA";
import Footer from "../landing/Footer";
import Hero from "../landing/Hero";
import HowItWorks from "../landing/HowItWorks";
import Integrations from "../landing/Integrations";
import LiveStatus from "../landing/LiveStatus";
import Metrics from "../landing/Metrics";
import Nav from "../landing/Nav";
import ProblemSection from "../landing/ProblemSection";
import TrustSection from "../landing/TrustSection";
import { useDeviceTier } from "../landing/useDeviceTier";
import "../landing/landing.css";

// three + fiber + drei are a large slice of the bundle and are useless to
// anyone who gets the static backdrop, so they load as their own chunk.
const Aperture3D = lazy(() => import("../landing/Aperture3D"));

/**
 * If the 3D chunk fails to load or the scene throws, fall back to the static
 * backdrop instead of taking the page down with it.
 *
 * Without this, a lazy-import failure (a stale chunk hash after a deploy, a
 * flaky network, a blocked request) propagates to the root and renders a blank
 * document — the background is decoration, and decoration must never be able
 * to break the page.
 */
class ApertureBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.warn("[aperture] 3D scene unavailable, using static backdrop:", error);
  }

  render() {
    if (this.state.failed) return <ApertureBackdrop />;
    return this.props.children;
  }
}

/**
 * Picks the background: the WebGL scene on capable hardware, the static SVG
 * backdrop otherwise (no WebGL, few cores, small viewport, or reduced motion).
 * ApertureBackdrop doubles as the Suspense fallback, so the page is never
 * blank while the 3D chunk downloads.
 */
function ApertureStage() {
  const tier = useDeviceTier();
  const { scrollYProgress, pulse } = useAperture();

  if (tier !== "high") return <ApertureBackdrop />;

  return (
    <ApertureBoundary>
      <Suspense fallback={<ApertureBackdrop />}>
        <Aperture3D scrollYProgress={scrollYProgress} pulse={pulse} />
      </Suspense>
    </ApertureBoundary>
  );
}

export default function Landing() {
  // The app shell is light by default; this page is always dark. Paint the
  // document background to match so overscroll doesn't flash white, and undo
  // it on the way out so app routes are unaffected.
  useEffect(() => {
    const previous = document.body.style.backgroundColor;
    document.body.style.backgroundColor = "#050505";
    return () => {
      document.body.style.backgroundColor = previous;
    };
  }, []);

  return (
    <ApertureProvider>
      <div className="aperture-root">
        <ApertureStage />
        {/* Legibility scrim. The scene is allowed to be busy at the edges;
            this keeps the middle, where the copy lives, dark enough to read
            against. Sits between the canvas and the sections. */}
        <div className="aperture-scrim" aria-hidden="true" />
        <Nav />
        <Hero />
        <ProblemSection />
        <HowItWorks />
        <LiveStatus />
        <Metrics />
        <Integrations />
        <TrustSection />
        <FinalCTA />
        <Footer />
      </div>
    </ApertureProvider>
  );
}
