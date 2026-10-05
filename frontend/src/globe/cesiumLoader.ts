/**
 * Loads CesiumJS once, from a pinned jsDelivr build with Subresource Integrity, so the app gets a
 * realistic globe without adding a ~100 MB package or changing the Vite build. Cesium's workers
 * and assets load from the same pinned base (CESIUM_BASE_URL). If the CDN is unreachable the
 * promise rejects and callers fall back to the offline three.js globe.
 */

export const CESIUM_VERSION = "1.146.0";
export const CESIUM_BASE = `https://cdn.jsdelivr.net/npm/cesium@${CESIUM_VERSION}/Build/Cesium/`;

const SCRIPT_SRI = "sha384-1lWK5deN/B+lLaUw4lk6xKp/L19ii/98SZLk6K8YthDskgvc+GbdixLzbCnSS2Wn";
const STYLE_SRI = "sha384-ghEeMdcWWzRv/BPeUcX835vcKDGrxvROXisl/Btpv3GeekBUXTSPVcFJpI1Tcrgp";

// CesiumJS ships its own (very large) typings only with the npm package; the CDN build is
// untyped, so the namespace is `any` and CesiumGlobe keeps its usage narrow.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CesiumNamespace = any;

declare global {
  interface Window {
    Cesium?: CesiumNamespace;
    CESIUM_BASE_URL?: string;
  }
}

let pending: Promise<CesiumNamespace> | null = null;

export function loadCesium(timeoutMs = 25_000): Promise<CesiumNamespace> {
  if (typeof window === "undefined") return Promise.reject(new Error("No browser window"));
  if (window.Cesium) return Promise.resolve(window.Cesium);
  if (pending) return pending;

  pending = new Promise((resolve, reject) => {
    window.CESIUM_BASE_URL = CESIUM_BASE;

    if (!document.querySelector("link[data-cesium-widgets]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = `${CESIUM_BASE}Widgets/widgets.css`;
      link.integrity = STYLE_SRI;
      link.crossOrigin = "anonymous";
      link.dataset.cesiumWidgets = "true";
      document.head.appendChild(link);
    }

    const script = document.createElement("script");
    script.src = `${CESIUM_BASE}Cesium.js`;
    script.async = true;
    script.integrity = SCRIPT_SRI;
    script.crossOrigin = "anonymous";

    const fail = (message: string) => {
      window.clearTimeout(timer);
      script.remove();
      pending = null;
      reject(new Error(message));
    };
    const timer = window.setTimeout(() => fail("CesiumJS did not load in time"), timeoutMs);

    script.onload = () => {
      window.clearTimeout(timer);
      if (window.Cesium) resolve(window.Cesium);
      else fail("CesiumJS loaded but did not initialise");
    };
    script.onerror = () => fail("CesiumJS could not be downloaded");
    document.head.appendChild(script);
  });
  return pending;
}
