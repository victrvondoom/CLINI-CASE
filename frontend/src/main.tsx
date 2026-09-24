import React from "react";
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

import { AuthProvider } from "./components/AuthContext";
import { RequireAuth } from "./components/RequireAuth";
import Agents from "./routes/Agents";
import App from "./App";
import BulkImport from "./routes/BulkImport";
import CaseDetail from "./routes/CaseDetail";
import Cases from "./routes/Cases";
import Cohorts from "./routes/Cohorts";
import Compare from "./routes/Compare";
import Compliance from "./routes/Compliance";
import Dashboard from "./routes/Dashboard";
import Eval from "./routes/Eval";
import Intake from "./routes/Intake";
import Landing from "./routes/Landing";
import Login from "./routes/Login";
import OncologyStack from "./routes/OncologyStack";
import Policies from "./routes/Policies";
import PolicyDiff from "./routes/PolicyDiff";
import Architecture from "./routes/Architecture";
import Industrialize from "./routes/Industrialize";
import Reviewer from "./routes/Reviewer";
import ROI from "./routes/ROI";
import Settings from "./routes/Settings";
import Signup from "./routes/Signup";
import TwinCommand from "./routes/TwinCommand";
import TwinDashboard from "./routes/TwinDashboard";
import TwinHub from "./routes/TwinHub";
import TwinLab from "./routes/TwinLab";
import TwinOps from "./routes/TwinOps";
import TwinPatient from "./routes/TwinPatient";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
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

            {/* OncoTwin — dynamic digital-twin layer (additive) */}
            <Route path="/twin" element={<TwinCommand />} />
            <Route path="/twin/overview" element={<TwinHub />} />
            <Route path="/twin/lab" element={<TwinLab />} />
            <Route path="/twin/ops" element={<TwinOps />} />
            <Route path="/twin/demo" element={<TwinPatient demo />} />
            <Route path="/twin/demo/classic" element={<TwinDashboard demo />} />
            <Route path="/twin/:patientId/classic" element={<TwinDashboard />} />
            <Route path="/twin/:patientId/:tab?" element={<TwinPatient />} />

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

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
