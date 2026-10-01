import React, { lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

// Production API rewrite: when deployed to a static host (e.g. S3 website),
// fetches to "/api/*" can't be proxied. Rewrite them to the deployed
// backend URL. In dev, VITE_API_BASE is empty and the Vite proxy handles it.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "");
if (API_BASE) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.startsWith("/api/")) {
      return originalFetch(API_BASE + input, init);
    }
    if (input instanceof URL && input.pathname.startsWith("/api/")) {
      return originalFetch(API_BASE + input.pathname + input.search, init);
    }
    return originalFetch(input, init);
  };
}

import { RouteBoundary } from "./components/RouteBoundary";
import { AuthProvider } from "./components/AuthContext";
import { RequireAuth } from "./components/RequireAuth";
const AquaCommunity = lazy(() => import("./routes/AquaCommunity"));
const AquaDashboard = lazy(() => import("./routes/AquaDashboard"));
const AquaEvaluation = lazy(() => import("./routes/AquaEvaluation"));
const Interop = lazy(() => import("./routes/Interop"));
const OneHealth = lazy(() => import("./routes/OneHealth"));
const AquaMap = lazy(() => import("./routes/AquaMap"));
const AquaObservationDetail = lazy(() => import("./routes/AquaObservationDetail"));
const AquaObservationNew = lazy(() => import("./routes/AquaObservationNew"));
const AquaObservations = lazy(() => import("./routes/AquaObservations"));
const AquaOneHealth = lazy(() => import("./routes/AquaOneHealth"));
const AquaReview = lazy(() => import("./routes/AquaReview"));
const AquaTrends = lazy(() => import("./routes/AquaTrends"));
const Agents = lazy(() => import("./routes/Agents"));
import App from "./App";
const BulkImport = lazy(() => import("./routes/BulkImport"));
const CardioEvaluation = lazy(() => import("./routes/CardioEvaluation"));
const CardioTwin = lazy(() => import("./routes/CardioTwin"));
const CaseDetail = lazy(() => import("./routes/CaseDetail"));
const Cases = lazy(() => import("./routes/Cases"));
const Cohorts = lazy(() => import("./routes/Cohorts"));
const Compare = lazy(() => import("./routes/Compare"));
const Compliance = lazy(() => import("./routes/Compliance"));
const Dashboard = lazy(() => import("./routes/Dashboard"));
const Eval = lazy(() => import("./routes/Eval"));
const Intake = lazy(() => import("./routes/Intake"));
const Landing = lazy(() => import("./routes/Landing"));
const Login = lazy(() => import("./routes/Login"));
const OncologyStack = lazy(() => import("./routes/OncologyStack"));
const Policies = lazy(() => import("./routes/Policies"));
const PolicyDiff = lazy(() => import("./routes/PolicyDiff"));
const Architecture = lazy(() => import("./routes/Architecture"));
const Industrialize = lazy(() => import("./routes/Industrialize"));
const Reviewer = lazy(() => import("./routes/Reviewer"));
const ROI = lazy(() => import("./routes/ROI"));
const Sandbox = lazy(() => import("./routes/Sandbox"));
const Settings = lazy(() => import("./routes/Settings"));
const Signup = lazy(() => import("./routes/Signup"));
const TwinCommand = lazy(() => import("./routes/TwinCommand"));
const TwinDashboard = lazy(() => import("./routes/TwinDashboard"));
const TwinHub = lazy(() => import("./routes/TwinHub"));
const TwinLab = lazy(() => import("./routes/TwinLab"));
const TwinOps = lazy(() => import("./routes/TwinOps"));
const TwinPatient = lazy(() => import("./routes/TwinPatient"));
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <RouteBoundary>
        <Routes>
          {/* Public marketing landing — the app's front door */}
          <Route path="/" element={<Landing />} />

          {/* Public auth pages */}
          <Route path="/login"  element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Protected app shell */}
          <Route
            element={
              <RequireAuth>
                <App />
              </RequireAuth>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/cases/bulk-import" element={<BulkImport />} />
            <Route path="/cases/:caseId" element={<CaseDetail />} />
            <Route path="/cases/:caseId/compare" element={<Compare />} />
            <Route path="/intake" element={<Intake />} />
            <Route path="/sandbox" element={<Sandbox />} />

            {/* OncoTwin — dynamic digital-twin layer (additive) */}
            <Route path="/twin" element={<TwinCommand />} />
            <Route path="/twin/overview" element={<TwinHub />} />
            <Route path="/twin/lab" element={<TwinLab />} />
            <Route path="/twin/ops" element={<TwinOps />} />
            <Route path="/twin/demo" element={<TwinPatient demo />} />
            <Route path="/twin/demo/classic" element={<TwinDashboard demo />} />
            {/* /twin/demo/:tab (e.g. /twin/demo/whatif) — same guided demo, deep-linkable to a tab.
                Without this, those URLs fell through to /twin/:patientId/:tab? with patientId
                literally "demo", which the backend correctly 404s (no such twin patient). */}
            <Route path="/twin/demo/:tab" element={<TwinPatient demo />} />
            <Route path="/twin/:patientId/classic" element={<TwinDashboard />} />
            <Route path="/twin/:patientId/:tab?" element={<TwinPatient />} />

            {/* CardioTwin — cardiovascular risk visualisation & vessel-level prediction (additive) */}
            <Route path="/cardiotwin" element={<CardioTwin />} />
            <Route path="/cardiotwin/evaluation" element={<CardioEvaluation />} />

            <Route path="/policies" element={<Policies />} />
            <Route path="/onco" element={<OncologyStack />} />
            <Route path="/policies/:policyId/diff" element={<PolicyDiff />} />
            <Route path="/agents" element={<Agents />} />

            <Route path="/cohorts" element={<Cohorts />} />
            <Route
              path="/reviewer"
              element={
                <RequireAuth roles={["reviewer", "admin"]}>
                  <Reviewer />
                </RequireAuth>
              }
            />
            <Route path="/compliance"     element={<Compliance />} />
            <Route path="/roi"            element={<ROI />} />
            <Route path="/industrialize"  element={<Industrialize />} />
            <Route path="/architecture"   element={<Architecture />} />
            <Route path="/eval"           element={<Eval />} />
            <Route
              path="/settings"
              element={
                <RequireAuth roles={["admin"]}>
                  <Settings />
                </RequireAuth>
              }
            />

            {/* AquaHealth — OneAquaHealth freshwater module (additive).
                Existing ClinCase routes above are unchanged. */}
            <Route path="/aquahealth" element={<AquaDashboard />} />
            <Route path="/onehealth" element={<OneHealth />} />
            <Route path="/interop" element={<Interop />} />
            <Route path="/aquahealth/observations" element={<AquaObservations />} />
            <Route path="/aquahealth/observations/new" element={<AquaObservationNew />} />
            <Route path="/aquahealth/observations/:observationId" element={<AquaObservationDetail />} />
            <Route path="/aquahealth/map" element={<AquaMap />} />
            <Route path="/aquahealth/trends" element={<AquaTrends />} />
            <Route path="/aquahealth/one-health" element={<AquaOneHealth />} />
            <Route path="/aquahealth/community" element={<AquaCommunity />} />
            <Route path="/aquahealth/evaluation" element={<AquaEvaluation />} />
            <Route
              path="/aquahealth/review"
              element={
                <RequireAuth roles={["reviewer", "admin"]}>
                  <AquaReview />
                </RequireAuth>
              }
            />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
        </RouteBoundary>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
