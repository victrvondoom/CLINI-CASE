import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

const card = "rounded-xl border border-surface-border bg-surface-raised p-5";
const configuredBase = (import.meta.env.VITE_SMART_FHIR_BASE as string | undefined) ?? "";
const clientId = (import.meta.env.VITE_SMART_CLIENT_ID as string | undefined) ?? "";
const redirectUri = (import.meta.env.VITE_SMART_REDIRECT_URI as string | undefined) ?? `${window.location.origin}/smart-on-fhir`;

interface SmartMetadata {
  authorization_endpoint: string;
  token_endpoint: string;
  capabilities?: string[];
}

interface SmartToken {
  access_token: string;
  token_type: string;
  expires_in?: number;
  patient?: string;
  scope?: string;
}

interface LaunchTransaction {
  state: string;
  verifier: string;
  issuer: string;
  launch?: string;
  createdAt: number;
}

function randomToken(bytes = 32): string {
  const values = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...values)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function challenge(verifier: string): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return btoa(String.fromCharCode(...new Uint8Array(hash))).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function issuerUrl(value: string): string {
  const url = new URL(value.trim());
  if ((url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) || url.username || url.password || url.search || url.hash) {
    throw new Error("Use a trusted HTTPS FHIR base URL (HTTP is allowed only on localhost).");
  }
  return url.toString().replace(/\/+$/, "");
}

function secureEndpoint(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) {
    throw new Error("The SMART server advertised a non-HTTPS OAuth endpoint.");
  }
  return url.toString();
}

export default function SmartOnFhir() {
  const [params] = useSearchParams();
  const launchIssuer = params.get("iss") ?? "";
  const launchHandle = params.get("launch") ?? undefined;
  const [base, setBase] = useState(launchIssuer || configuredBase);
  const [token, setToken] = useState<SmartToken | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const callbackHandled = useRef(false);

  useEffect(() => {
    const code = params.get("code");
    const returnedState = params.get("state");
    const oauthError = params.get("error");
    if (!code && !oauthError) return;
    if (callbackHandled.current) return;
    callbackHandled.current = true;
    window.history.replaceState({}, "", window.location.pathname);
    if (oauthError) {
      setError("The EHR authorization server declined or could not complete the SMART launch.");
      return;
    }
    setBusy(true);
    try {
      const raw = sessionStorage.getItem("clincase-smart-launch");
      sessionStorage.removeItem("clincase-smart-launch");
      if (!raw || !returnedState) throw new Error("SMART launch state is missing or expired. Start the connection again.");
      const pending = JSON.parse(raw) as LaunchTransaction;
      if (pending.state !== returnedState || Date.now() - pending.createdAt > 10 * 60_000) throw new Error("SMART launch state did not match or has expired.");
      void (async () => {
        const discoveryResponse = await fetch(`${pending.issuer}/.well-known/smart-configuration`, { headers: { Accept: "application/json" }, credentials: "omit", redirect: "error" });
        if (!discoveryResponse.ok) throw new Error("Could not discover SMART endpoints at the configured FHIR server.");
        const metadata = await discoveryResponse.json() as SmartMetadata;
        const endpoint = secureEndpoint(metadata.token_endpoint);
        const body = new URLSearchParams({ grant_type: "authorization_code", code: code!, redirect_uri: redirectUri, client_id: clientId, code_verifier: pending.verifier });
        const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body, credentials: "omit", redirect: "error" });
        if (!response.ok) throw new Error("The SMART token exchange failed. Confirm the registered client and redirect URI.");
        const result = await response.json() as SmartToken;
        if (!result.access_token || result.token_type.toLowerCase() !== "bearer") throw new Error("The EHR returned an invalid SMART token response.");
        setToken(result);
        setBase(pending.issuer);
        setMessage("SMART connection established. The access token stays in page memory and is not written to application storage.");
      })().catch((e: unknown) => setError(e instanceof Error ? e.message : "SMART launch failed.")).finally(() => setBusy(false));
    } catch (e) {
      setError(e instanceof Error ? e.message : "SMART launch failed.");
      setBusy(false);
    }
  }, [params]);

  async function connect() {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      if (!clientId) throw new Error("Set the public VITE_SMART_CLIENT_ID and register this exact redirect URI with your EHR first.");
      const issuer = issuerUrl(base);
      if (launchIssuer && issuerUrl(launchIssuer) !== issuer) throw new Error("The EHR launch issuer does not match the configured FHIR base URL.");
      const response = await fetch(`${issuer}/.well-known/smart-configuration`, { headers: { Accept: "application/json" }, credentials: "omit", redirect: "error" });
      if (!response.ok) throw new Error("SMART discovery failed for this FHIR base URL.");
      const metadata = await response.json() as SmartMetadata;
      const authorize = new URL(secureEndpoint(metadata.authorization_endpoint));
      const verifier = randomToken(48);
      const state = randomToken(32);
      const params = new URLSearchParams({ response_type: "code", client_id: clientId, redirect_uri: redirectUri, scope: launchHandle ? "launch patient/Patient.r" : "launch/patient patient/Patient.r", aud: issuer, state, code_challenge: await challenge(verifier), code_challenge_method: "S256" });
      if (launchHandle) params.set("launch", launchHandle);
      const pending: LaunchTransaction = { state, verifier, issuer, launch: launchHandle, createdAt: Date.now() };
      sessionStorage.setItem("clincase-smart-launch", JSON.stringify(pending));
      window.location.assign(`${authorize.href}?${params.toString()}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start SMART launch.");
      setBusy(false);
    }
  }

  async function verifyFhirAccess() {
    if (!token || !base) return;
    setBusy(true);
    setError("");
    try {
      const issuer = issuerUrl(base);
      const response = await fetch(`${issuer}/metadata`, { headers: { Accept: "application/fhir+json", Authorization: `Bearer ${token.access_token}` }, credentials: "omit", redirect: "error" });
      if (!response.ok) throw new Error("FHIR CapabilityStatement request was rejected by the server.");
      const statement = await response.json() as { resourceType?: string; fhirVersion?: string };
      setMessage(`FHIR access verified: ${statement.resourceType ?? "CapabilityStatement"}, version ${statement.fhirVersion ?? "not declared"}. No patient resource was read.`);
    } catch (e) { setError(e instanceof Error ? e.message : "FHIR access check failed."); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto min-h-screen max-w-3xl space-y-5 p-6 text-ink-body lg:p-10">
      <header><p className="text-xs uppercase tracking-[0.18em] text-accent-cyan">Clinical interoperability · optional</p><h1 className="mt-2 text-2xl font-semibold text-ink-primary">SMART on FHIR launch</h1><p className="mt-2 text-sm text-ink-muted">Connect to a registered EHR using SMART App Launch authorization code with PKCE. This page does not send a client secret or automatically read patient resources.</p></header>
      <section className={card}>
        <label className="block text-sm font-medium" htmlFor="smart-base">FHIR server base URL</label>
        <input id="smart-base" type="url" value={base} onChange={(e) => setBase(e.target.value)} disabled={!!launchIssuer || !!token} placeholder="https://ehr.example/fhir/R4" className="mt-2 w-full rounded-md border border-surface-border bg-surface-bg px-3 py-2 text-sm" autoComplete="url" />
        <p className="mt-2 text-xs text-ink-faint">Public client ID: {clientId || "not configured"} · redirect URI: {redirectUri}</p>
        {launchHandle && <p className="mt-2 text-xs text-accent-cyan">EHR launch context detected; the opaque launch handle is kept in session storage for the authorization exchange.</p>}
        {!token ? <button type="button" onClick={() => void connect()} disabled={busy} className="mt-4 rounded-md bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-bg disabled:opacity-50">{busy ? "Connecting…" : "Connect to EHR"}</button> : <div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={() => void verifyFhirAccess()} disabled={busy} className="rounded-md bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-bg disabled:opacity-50">Verify FHIR access</button><button type="button" onClick={() => { setToken(null); setMessage("SMART access token cleared from page memory."); }} className="rounded-md border border-surface-border px-4 py-2 text-sm">Disconnect</button></div>}
        {token?.patient && <p className="mt-3 text-xs text-ink-muted">EHR patient context is available and held in memory; the identifier is not displayed or persisted.</p>}
      </section>
      {error && <p className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300" role="alert">{error}</p>}
      {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm" role="status">{message}</p>}
      <aside className={card}><h2 className="text-sm font-semibold text-ink-primary">Setup and limits</h2><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-muted"><li>Register this redirect URI and public client ID with an EHR authorization server; each EHR has its own registration and policies.</li><li>The client uses PKCE S256 and requests only patient launch context plus Patient read scope.</li><li>This is a browser public client, so there is no client secret. Access token lifetime/refresh is controlled by the EHR; this demo does not persist tokens or implement refresh.</li><li>Use synthetic data for demonstrations. No patient data is copied into the CLINI-CASE backend.</li></ul><Link to="/interop" className="mt-3 inline-block text-sm text-accent-cyan underline">Return to Track 7 workbench</Link></aside>
    </main>
  );
}
