// Component contracts for the OAH-Bridge globe integration.
// AquaMap (the page) owns all state; these components are controlled, so the guided
// walkthrough can drive tabs, highlights and the CDS reveal from one place.
import type { ReactNode } from "react";

import type { CdsResponse, CitizenPoint, DemoRunResponse, LonLat, ScenarioSite } from "./types";

// ---------------------------------------------------------------------------
// BridgeConsole — src/oahbridge/console/BridgeConsole.tsx (default export)
// ---------------------------------------------------------------------------

export type ConsoleTab = "chain" | "clinical" | "graph" | "conformance" | "impact";

export type GraphNodeKey =
  | "Location"
  | "Observation-hazard"
  | "Observation-evidence"
  | "Group"
  | "RiskAssessment"
  | "Provenance"
  | "Flag"
  | "CommunicationRequest"
  | "Bundle";

/** Blocks the walkthrough can scroll to and pulse. */
export type HighlightTarget = "evidence" | "score" | "exposure" | "cohort" | "risk" | "bundle" | "cds";

export interface BridgeConsoleProps {
  /** Latest pipeline run; null while the first run loads or after an error. */
  run: DemoRunResponse | null;
  loading: boolean;
  error: string | null;
  tab: ConsoleTab;
  onTabChange: (tab: ConsoleTab) => void;
  graphNode: GraphNodeKey;
  onGraphNodeChange: (node: GraphNodeKey) => void;
  /** Scroll into view and pulse this block. `pulseKey` increments to re-trigger the same target. */
  highlight: { target: HighlightTarget; pulseKey: number } | null;
  cds: CdsResponse | null;
  cdsLoading: boolean;
  cdsError: string | null;
  /** Ask the page to make the CDS Hooks call. No coordinates = the scenario's synthetic demo patient. */
  onEvaluateCds: (coordinates?: [number, number]) => void;
  /** Whether the (simulated) EHR note has been shown; owned by the page so the walkthrough can reveal it. */
  documented: boolean;
  onDocument: () => void;
  onOpenDossier: () => void;
  /** The exposure-zone inset map, rendered by the page and placed in the chain tab's exposure block. */
  zoneSlot?: ReactNode;
}

// ---------------------------------------------------------------------------
// DossierModal — src/oahbridge/console/DossierModal.tsx (default export)
// ---------------------------------------------------------------------------

export interface DossierModalProps {
  run: DemoRunResponse;
  open: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Walkthrough — src/oahbridge/console/Walkthrough.tsx (default export)
// ---------------------------------------------------------------------------

export interface WalkthroughStep {
  title: string;
  text: string;
}

export interface WalkthroughProps {
  open: boolean;
  steps: WalkthroughStep[];
  /** 0-based index of the current step. */
  index: number;
  finished: boolean;
  autoPlay: boolean;
  autoPlaySeconds: number;
  onPrev: () => void;
  onNext: () => void;
  onToggleAutoPlay: () => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// ZoneInset — src/oahbridge/ZoneInset.tsx (default export)
// ---------------------------------------------------------------------------

export type Basemap = "street" | "satellite";

export interface ZoneInsetProps {
  site: ScenarioSite;
  citizenPoints: CitizenPoint[];
  /** Point evaluated by CDS Hooks; null hides the marker. */
  patient: LonLat | null;
  /** From the last CDS evaluation of `patient`: inside the zone, outside, or not evaluated yet. */
  patientInside: boolean | null;
  basemap: Basemap;
  onBasemapChange: (basemap: Basemap) => void;
  /** Called with the clicked map position, so the page can evaluate it with CDS Hooks. */
  onPick?: (point: LonLat) => void;
  /** Pulse the frame (walkthrough "exposure" step). */
  highlighted?: boolean;
  /** Pixel height of the map area. Default 300. */
  height?: number;
}
