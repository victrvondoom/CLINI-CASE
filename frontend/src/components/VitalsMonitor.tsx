/**
 * VitalsMonitor — real-time, ECG-style scrolling waveform plus the two
 * primary bedside actions: Emergency and Appointment.
 *
 * The waveform is a client-side simulation (this app has no live device/EHR
 * vitals feed — every OncoTwin signal is synthetic, see oncotwin/*). It is
 * seeded from the twin's current resting heart rate when available so the
 * trace rate matches what the rest of the page is already showing, and
 * falls back to a plausible resting rate otherwise. It is a visual/demo
 * aid, not a diagnostic monitor.
 */
import { AlertTriangle, CalendarPlus, CheckCircle2, Loader2, PhoneCall, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";

// One PQRST-ish beat as a normalized [0,1] x → [-1,1] y lookup, sampled coarsely
// and interpolated. Values are stylized, not clinical waveform morphology.
const BEAT: [number, number][] = [
  [0.00, 0], [0.08, 0.05], [0.14, -0.08], [0.18, 0.9], [0.22, -0.35],
  [0.28, -0.05], [0.30, 0], [0.45, 0], [0.5, 0.05], [0.58, 0.28],
  [0.66, 0.05], [0.7, 0], [1.0, 0],
];

function beatY(t: number): number {
  // t in [0,1) — find surrounding samples and lerp.
  for (let i = 0; i < BEAT.length - 1; i++) {
    const [x0, y0] = BEAT[i];
    const [x1, y1] = BEAT[i + 1];
    if (t >= x0 && t <= x1) {
      const f = (t - x0) / (x1 - x0 || 1);
      return y0 + (y1 - y0) * f;
    }
  }
  return 0;
}

interface Props {
  /** Beats per minute driving the trace; defaults to a plausible resting rate. */
  bpm?: number;
  width?: number;
  height?: number;
  className?: string;
  label?: string;
}

export function EcgWaveform({ bpm = 72, width = 320, height = 72, className, label }: Props) {
  const [points, setPoints] = useState<number[]>(() => new Array(Math.floor(width)).fill(0));
  const rafRef = useRef<number | undefined>(undefined);
  const phaseRef = useRef(0);
  const lastTsRef = useRef<number | undefined>(undefined);
  const bpmRef = useRef(bpm);
  bpmRef.current = bpm;

  useEffect(() => {
    const pxPerSecond = width / 3.2; // ~3.2s of trace visible, like a bedside monitor sweep
    function tick(ts: number) {
      const last = lastTsRef.current ?? ts;
      const dt = Math.min(0.05, (ts - last) / 1000);
      lastTsRef.current = ts;

      const secondsPerBeat = 60 / Math.max(20, bpmRef.current);
      phaseRef.current = (phaseRef.current + dt / secondsPerBeat) % 1;
      const y = beatY(phaseRef.current);

      const advance = Math.max(1, Math.round(pxPerSecond * dt));
      setPoints((prev) => {
        const next = prev.slice(advance);
        while (next.length < prev.length) next.push(y);
        return next;
      });
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [width]);

  const path = useMemo(() => {
    const midY = height / 2;
    const amp = height * 0.42;
    return points
      .map((v, i) => `${i === 0 ? "M" : "L"} ${i} ${(midY - v * amp).toFixed(1)}`)
      .join(" ");
  }, [points, height]);

  return (
    <div className={className} aria-hidden>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="currentColor" strokeOpacity={0.08} strokeWidth={1} />
        <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="text-accent-green" />
      </svg>
      {label && <div className="text-[10px] text-compact text-ink-faint -mt-1">{label}</div>}
    </div>
  );
}

// =============================================================================
// Emergency + Appointment action bar
// =============================================================================

// Rough adult vital-sign alarm bands, for the bedside-monitor visual only —
// not a clinical threshold engine (the twin's own tier/alert system is that).
const HR_ALARM = { low: 50, high: 120 };
const TEMP_ALARM_F = { low: 96, high: 100.4 };
const SBP_ALARM = { low: 90, high: 160 };

type Vital = { value: number | null | undefined; low: number; high: number };
function vitalTone(v: Vital): "ok" | "alarm" {
  if (v.value == null) return "ok";
  return v.value < v.low || v.value > v.high ? "alarm" : "ok";
}

function VitalReadout({ label, value, unit, decimals = 0, tone }: {
  label: string; value: number | null | undefined; unit: string; decimals?: number; tone: "ok" | "alarm";
}) {
  return (
    <div className="min-w-[64px]">
      <div className="text-[9.5px] text-compact text-ink-faint">{label}</div>
      <div className={clsx("text-[15px] leading-tight text-mono-tech font-semibold", tone === "alarm" ? "text-accent-red animate-pulse-soft" : "text-ink-primary")}>
        {value == null ? "—" : value.toFixed(decimals)}
        <span className="text-[10px] text-ink-muted font-normal ml-0.5">{unit}</span>
      </div>
    </div>
  );
}

interface LogEntry {
  id: number;
  at: string;
  kind: "emergency" | "appointment";
  text: string;
}

interface VitalsMonitorProps {
  /** Patient/case display name for confirmation copy. */
  who?: string;
  /** Latest resting heart rate reading (bpm), if the caller has one (e.g. from a twin's signals). */
  restingHr?: number | null;
  /** Latest body temperature reading (°F), if available. */
  temperatureF?: number | null;
  /** Latest systolic blood pressure reading (mmHg), if available. */
  systolicBp?: number | null;
  /** Called when the clinician confirms the emergency escalation. */
  onEmergency?: () => Promise<void> | void;
  /** Called when an appointment is confirmed; receives the chosen ISO date + reason. */
  onScheduleAppointment?: (isoDate: string, reason: string) => Promise<void> | void;
  className?: string;
}

export function VitalsMonitor({ who, restingHr, temperatureF, systolicBp, onEmergency, onScheduleAppointment, className }: VitalsMonitorProps) {
  const [emergencyOpen, setEmergencyOpen] = useState(false);
  const [apptOpen, setApptOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);

  const bpm = restingHr && restingHr > 30 && restingHr < 220 ? restingHr : 72;
  const hrTone = vitalTone({ value: restingHr, ...HR_ALARM });
  const tempTone = vitalTone({ value: temperatureF, ...TEMP_ALARM_F });
  const sbpTone = vitalTone({ value: systolicBp, ...SBP_ALARM });
  const anyAlarm = hrTone === "alarm" || tempTone === "alarm" || sbpTone === "alarm";

  const addLog = (kind: LogEntry["kind"], text: string) =>
    setLog((prev) => [{ id: Date.now(), at: new Date().toLocaleTimeString(), kind, text }, ...prev].slice(0, 6));

  const confirmEmergency = async () => {
    setBusy(true);
    try {
      await onEmergency?.();
      const msg = "Emergency escalation logged. Care team notified.";
      setNotice(msg);
      addLog("emergency", msg);
    } finally {
      setBusy(false);
      setEmergencyOpen(false);
    }
  };

  return (
    <div className={className}>
      <div className={clsx("flex flex-wrap items-center gap-4 rounded-xl border p-3 transition-colors duration-300",
        anyAlarm ? "border-accent-red/60 bg-accent-red/5" : "border-surface-border bg-surface-raised")}>
        <EcgWaveform bpm={bpm} width={220} height={56} label={`${Math.round(bpm)} bpm · live trace (simulated)`} />

        <div className="flex items-center gap-4">
          <VitalReadout label="HR" value={restingHr} unit="bpm" tone={hrTone} />
          <VitalReadout label="TEMP" value={temperatureF} unit="°F" decimals={1} tone={tempTone} />
          <VitalReadout label="SBP" value={systolicBp} unit="mmHg" tone={sbpTone} />
        </div>

        {anyAlarm && (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent-red">
            <AlertTriangle size={13} aria-hidden /> Out of range
          </span>
        )}

        <div className="flex-1 min-w-[80px]" />

        <button
          type="button"
          onClick={() => setEmergencyOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-accent-red text-white text-[12.5px] font-semibold hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-accent-red focus:ring-offset-2 focus:ring-offset-surface-bg"
          title="Escalate to emergency review"
        >
          <AlertTriangle size={14} aria-hidden /> Emergency
        </button>

        <button
          type="button"
          onClick={() => setApptOpen(true)}
          className={BTN}
          title="Schedule a follow-up appointment"
        >
          <CalendarPlus size={14} aria-hidden /> Appointment
        </button>
      </div>

      {notice && (
        <div className="mt-2 text-[12px] px-3 py-2 rounded-md bg-accent-brand/10 border border-accent-brand/40" role="status">
          {notice}
        </div>
      )}

      {log.length > 0 && (
        <ul className="mt-2 space-y-1" aria-label="Recent bedside actions">
          {log.map((e, i) => (
            <li key={e.id} className="flex items-start gap-1.5 text-[11px] text-ink-muted animate-fade-in"
              style={{ animationDelay: `${Math.min(i, 6) * 25}ms`, animationFillMode: "both" }}>
              {e.kind === "emergency"
                ? <AlertTriangle size={11} className="text-accent-red mt-0.5 shrink-0" aria-hidden />
                : <CheckCircle2 size={11} className="text-accent-brand mt-0.5 shrink-0" aria-hidden />}
              <span className="text-mono-tech text-[10px] text-ink-faint shrink-0">{e.at}</span>
              <span>{e.text}</span>
            </li>
          ))}
        </ul>
      )}

      {emergencyOpen && (
        <EmergencyDialog
          who={who}
          busy={busy}
          onCancel={() => setEmergencyOpen(false)}
          onConfirm={confirmEmergency}
        />
      )}

      {apptOpen && (
        <AppointmentDialog
          who={who}
          onCancel={() => setApptOpen(false)}
          onConfirm={async (iso, reason) => {
            await onScheduleAppointment?.(iso, reason);
            const msg = `Appointment requested for ${iso}${reason ? `: ${reason}` : ""}.`;
            setNotice(msg);
            addLog("appointment", msg);
            setApptOpen(false);
          }}
        />
      )}
    </div>
  );
}

function Dialog({ title, icon, tone, children, onCancel }: {
  title: string; icon: React.ReactNode; tone: "red" | "brand"; children: React.ReactNode; onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 animate-fade-in" role="dialog" aria-modal="true" aria-label={title}>
      <div className="reveal-go w-full max-w-sm rounded-xl border border-surface-border bg-surface-raised p-4 shadow-xl">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className={`flex items-center gap-2 text-[14px] font-semibold ${tone === "red" ? "text-accent-red" : "text-ink-primary"}`}>
            {icon} {title}
          </div>
          <button type="button" onClick={onCancel} className="text-ink-muted hover:text-ink-primary" aria-label="Close">
            <X size={16} aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function EmergencyDialog({ who, busy, onCancel, onConfirm }: {
  who?: string; busy: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <Dialog title="Confirm emergency escalation" icon={<AlertTriangle size={16} aria-hidden />} tone="red" onCancel={onCancel}>
      <p className="text-[12.5px] text-ink-body mb-3">
        This will flag {who ?? "this patient"} for immediate clinician review. Use for a genuine urgent
        concern — this is a demo action and does not dial emergency services.
      </p>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className={BTN} disabled={busy}>Cancel</button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-red text-white text-[12px] font-semibold disabled:opacity-60"
        >
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <PhoneCall size={13} aria-hidden />} Escalate now
        </button>
      </div>
    </Dialog>
  );
}

function AppointmentDialog({ who, onCancel, onConfirm }: {
  who?: string; onCancel: () => void; onConfirm: (isoDate: string, reason: string) => Promise<void> | void;
}) {
  const tomorrow = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  }, []);
  const [date, setDate] = useState(tomorrow);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try { await onConfirm(date, reason.trim()); } finally { setBusy(false); }
  };

  return (
    <Dialog title="Schedule appointment" icon={<CalendarPlus size={16} aria-hidden />} tone="brand" onCancel={onCancel}>
      <p className="text-[12px] text-ink-muted mb-3">Request a follow-up visit for {who ?? "this patient"}.</p>
      <div className="space-y-2 mb-3">
        <label className="flex flex-col gap-1 text-[12px] text-ink-body">
          Date
          <input
            type="date"
            value={date}
            min={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
            className="rounded border border-surface-border bg-surface-bg px-2 py-1.5 text-[12.5px]"
          />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-body">
          Reason (optional)
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. post-cycle check-in"
            className="rounded border border-surface-border bg-surface-bg px-2 py-1.5 text-[12.5px]"
          />
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className={BTN} disabled={busy}>Cancel</button>
        <button
          type="button"
          onClick={submit}
          disabled={busy || !date}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert text-[12px] font-medium disabled:opacity-60"
        >
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <CalendarPlus size={13} aria-hidden />} Confirm
        </button>
      </div>
    </Dialog>
  );
}
