import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { authHeader } from "../lib/auth";

interface PushConfig { enabled: boolean; public_key: string | null }
const endpoint = "/api/v1/notifications/push";
const card = "rounded-xl border border-surface-border bg-surface-raised p-5";

function applicationKey(value: string): Uint8Array {
  const padded = value + "=".repeat((4 - value.length % 4) % 4);
  const binary = atob(padded.replaceAll("-", "+").replaceAll("_", "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function api<T>(path: string, method = "GET", payload?: unknown): Promise<T> {
  const response = await fetch(`${endpoint}${path}`, {
    method,
    headers: { ...authHeader(), ...(payload === undefined ? {} : { "Content-Type": "application/json" }) },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `Request failed (${response.status})`);
  return result as T;
}

export default function NotificationPreferences() {
  const [config, setConfig] = useState<PushConfig | null>(null);
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    api<PushConfig>("/config").then((value) => {
      if (current) setConfig(value);
      if (value.enabled && "serviceWorker" in navigator && "PushManager" in window) {
        navigator.serviceWorker.register("/sw.js").then((registration) => registration.pushManager.getSubscription()).then((value) => { if (current) setSubscription(value); }).catch(() => undefined);
      }
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load notification settings."));
    return () => { current = false; };
  }, []);

  async function subscribe() {
    setBusy(true); setError(""); setMessage("");
    try {
      if (!config?.public_key || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) throw new Error("This browser does not support Web Push or the server is not configured.");
      const permission = await Notification.requestPermission();
      if (permission !== "granted") throw new Error("Notification permission was not granted.");
      const registration = await navigator.serviceWorker.register("/sw.js");
      const current = await registration.pushManager.getSubscription();
      const next = current ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: applicationKey(config.public_key) as BufferSource });
      await api("/subscribe", "POST", { subscription: next.toJSON() });
      setSubscription(next);
      setMessage("This browser is subscribed. Notifications remain opt-in and use non-sensitive reminder text.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not enable notifications."); }
    finally { setBusy(false); }
  }

  async function unsubscribe() {
    setBusy(true); setError(""); setMessage("");
    try {
      if (subscription) {
        await api("/subscribe", "DELETE", { endpoint: subscription.endpoint });
        await subscription.unsubscribe();
      }
      setSubscription(null);
      setMessage("This browser has been unsubscribed.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not disable notifications."); }
    finally { setBusy(false); }
  }

  async function sendTest() {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api<{ sent: number; expired_removed: number }>("/test", "POST", {});
      setMessage(`Test notification accepted for ${result.sent} device${result.sent === 1 ? "" : "s"}.${result.expired_removed ? ` Removed ${result.expired_removed} expired subscription(s).` : ""}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not send the test notification."); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-5 p-6 lg:p-10">
      <header><p className="text-xs uppercase tracking-[0.18em] text-accent-cyan">Follow-up · optional</p><h1 className="mt-2">Notification preferences</h1><p className="mt-2 text-sm text-ink-muted">Enable browser notifications for this account, then send an explicit test. No case, patient, or observation details are included in the notification.</p></header>
      <section className={card}>
        <h2 className="text-sm font-semibold text-ink-primary">Browser subscription</h2>
        <p className="mt-2 text-xs text-ink-muted">Server status: {config === null ? "checking" : config.enabled ? "VAPID configured" : "not configured"} · Browser: {subscription ? "subscribed" : "not subscribed"} · Permission: {typeof Notification === "undefined" ? "unsupported" : Notification.permission}</p>
        {!subscription ? <button type="button" disabled={busy || !config?.enabled} onClick={() => void subscribe()} className="mt-4 rounded-md bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-bg disabled:opacity-50">Enable notifications</button> : <div className="mt-4 flex flex-wrap gap-3"><button type="button" disabled={busy} onClick={() => void sendTest()} className="rounded-md bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-bg disabled:opacity-50">Send me a test notification</button><button type="button" disabled={busy} onClick={() => void unsubscribe()} className="rounded-md border border-surface-border px-4 py-2 text-sm disabled:opacity-50">Unsubscribe this browser</button></div>}
      </section>
      {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      {message && <p role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">{message}</p>}
      <aside className={`${card} text-xs text-ink-muted`}><h2 className="text-sm font-semibold text-ink-primary">Privacy and setup</h2><ul className="mt-2 list-disc space-y-1 pl-5"><li>Permission is requested only after you click Enable. You can revoke it here or in browser settings.</li><li>Push subscription endpoint and encryption keys are AES-GCM encrypted in the database and scoped to your account and organization.</li><li>VAPID private key and encryption key stay on the backend. Keep them stable; rotating the encryption key requires users to subscribe again.</li><li>HTTPS is required outside localhost. The push is a generic reminder only, not an urgent alert or a clinical instruction.</li></ul><Link to="/follow-up" className="mt-3 inline-block text-accent-cyan underline">Back to Follow-up</Link></aside>
    </main>
  );
}
