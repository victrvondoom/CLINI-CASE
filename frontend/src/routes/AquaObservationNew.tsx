/**
 * /aquahealth/observations/new — guided citizen observation form.
 *
 * Citizen-science UX track. Three principles drive the design:
 *
 *  1. Nothing is mandatory except the waterbody name. Every qualitative field
 *     defaults to "Not available", so a volunteer who noticed one thing can
 *     file a valid observation in seconds.
 *  2. "Not observed" is offered as a first-class answer, distinct from
 *     "Unknown". Looking and seeing nothing is real evidence; not looking is
 *     not. The backend treats them differently and the form says so.
 *  3. Plain language throughout — no indices, no jargon.
 *
 * The field catalogue is fetched from /form-schema, which is generated from the
 * same constants the assessment agents read, so the form cannot drift from
 * what the AI actually interprets.
 */
import { Camera, Check, Crosshair, Loader2, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { aqua } from "../aquahealth/api";
import {
  ErrorNote,
  LoadingNote,
  PageHeader,
  PrototypeNotice,
} from "../aquahealth/panels";
import type {
  Clarity,
  FormSchema,
  Measurements,
  ObservationCreate,
  Presence,
  WaterbodyKind,
} from "../aquahealth/types";

type PresenceMap = Record<string, Presence>;

const PRESENCE_CHOICES: Array<{ value: Presence; label: string; hint: string }> = [
  { value: "observed", label: "Yes", hint: "I saw this" },
  { value: "not_observed", label: "No", hint: "I looked and did not see it" },
  { value: "unknown", label: "Not sure", hint: "I could not tell" },
  { value: "not_available", label: "Skip", hint: "I did not check" },
];

const inputClass =
  "w-full rounded-md border border-surface-border bg-surface-bg px-3 py-2 text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-cyan focus:outline-none transition-colors";

export default function AquaObservationNew() {
  const navigate = useNavigate();

  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Waterbody
  const [waterbodyName, setWaterbodyName] = useState("");
  const [waterbodyKind, setWaterbodyKind] = useState<WaterbodyKind>("stream");
  const [locality, setLocality] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [geoBusy, setGeoBusy] = useState(false);

  // When
  const [observedDate, setObservedDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [observedTime, setObservedTime] = useState(() =>
    new Date().toISOString().slice(11, 16),
  );

  // Answers
  const [appearance, setAppearance] = useState<PresenceMap>({});
  const [biodiversity, setBiodiversity] = useState<PresenceMap>({});
  const [context, setContext] = useState<PresenceMap>({});
  const [clarity, setClarity] = useState<Clarity>("unknown");
  const [colourNote, setColourNote] = useState("");
  const [note, setNote] = useState("");

  // Optional measurements, kept as strings so an empty box stays empty.
  const [measurements, setMeasurements] = useState<Record<string, string>>({});

  // Photos — metadata plus a data URI, so the demo needs no object store.
  const [photos, setPhotos] = useState<
    Array<{
      filename: string;
      content_type: string;
      size_bytes: number;
      uri: string;
      caption: string;
    }>
  >([]);

  useEffect(() => {
    aqua
      .formSchema()
      .then(setSchema)
      .catch((e) =>
        setLoadError(e instanceof Error ? e.message : "Failed to load the form"),
      );
  }, []);

  const sectionFor = useCallback(
    (key: "appearance" | "biodiversity" | "context") =>
      schema?.sections.find((s) => s.key === key),
    [schema],
  );

  const answeredCount = useMemo(() => {
    const all = { ...appearance, ...biodiversity, ...context };
    return Object.values(all).filter(
      (v) => v === "observed" || v === "not_observed",
    ).length;
  }, [appearance, biodiversity, context]);

  function useMyLocation() {
    if (!navigator.geolocation) {
      setSubmitError("This browser does not expose a location API.");
      return;
    }
    setGeoBusy(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude.toFixed(5));
        setLongitude(pos.coords.longitude.toFixed(5));
        setGeoBusy(false);
      },
      () => {
        setSubmitError(
          "Could not read your location. You can type the coordinates instead, or leave them blank.",
        );
        setGeoBusy(false);
      },
      { timeout: 10_000 },
    );
  }

  async function onPickPhotos(files: FileList | null) {
    if (!files?.length) return;
    const picked = Array.from(files).slice(0, 3);
    const read = await Promise.all(
      picked.map(
        (f) =>
          new Promise<{
            filename: string;
            content_type: string;
            size_bytes: number;
            uri: string;
            caption: string;
          }>((resolve) => {
            const reader = new FileReader();
            reader.onload = () =>
              resolve({
                filename: f.name,
                content_type: f.type || "image/jpeg",
                size_bytes: f.size,
                uri: String(reader.result ?? ""),
                caption: "",
              });
            reader.onerror = () =>
              resolve({
                filename: f.name,
                content_type: f.type || "image/jpeg",
                size_bytes: f.size,
                uri: "",
                caption: "",
              });
            reader.readAsDataURL(f);
          }),
      ),
    );
    setPhotos((prev) => [...prev, ...read].slice(0, 3));
  }

  function numeric(code: string): number | null {
    const raw = measurements[code];
    if (raw === undefined || raw.trim() === "") return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  async function submit() {
    if (!waterbodyName.trim()) {
      setSubmitError(
        "Please give the waterbody a name so the observation can be grouped.",
      );
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    const observedAt = (() => {
      const time = observedTime || "00:00";
      const parsed = new Date(`${observedDate}T${time}`);
      return Number.isNaN(parsed.getTime())
        ? new Date().toISOString()
        : parsed.toISOString();
    })();

    const measurementPayload: Partial<Measurements> = {};
    for (const m of schema?.measurements ?? []) {
      const v = numeric(m.code);
      if (v !== null) measurementPayload[m.code] = v;
    }

    const payload: ObservationCreate = {
      waterbody_name: waterbodyName.trim(),
      waterbody_kind: waterbodyKind,
      locality: locality.trim() || null,
      latitude: latitude.trim() === "" ? null : Number(latitude),
      longitude: longitude.trim() === "" ? null : Number(longitude),
      observed_at: observedAt,
      observer_note: note.trim() || null,
      appearance: {
        ...appearance,
        clarity,
        colour_note: colourNote.trim() || null,
      } as ObservationCreate["appearance"],
      biodiversity: biodiversity as ObservationCreate["biodiversity"],
      context: context as ObservationCreate["context"],
      measurements: measurementPayload,
      photos: photos.map((p) => ({
        filename: p.filename,
        content_type: p.content_type,
        size_bytes: p.size_bytes,
        uri: p.uri || null,
        caption: p.caption || null,
      })),
    };

    try {
      const created = await aqua.createObservation(payload);
      navigate(`/aquahealth/observations/${created.id}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Could not save the observation");
      setSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <div className="p-6 lg:p-8 max-w-3xl">
        <ErrorNote message={loadError} />
      </div>
    );
  }

  if (!schema) {
    return (
      <div className="p-6 lg:p-8 max-w-3xl">
        <LoadingNote label="Loading observation form…" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-3xl">
      <PageHeader
        eyebrow="AQUAHEALTH · CITIZEN SCIENCE"
        title="Record a freshwater observation"
        description="Tell us what you saw. Every question is optional — answer only what you actually observed."
      />

      <div className="space-y-5">
        <PrototypeNotice>{schema.guidance}</PrototypeNotice>

        {/* Where */}
        <Card title="Where" subtitle="Which water did you look at?">
          <div className="space-y-4">
            <Field label="Waterbody name" required>
              <input
                value={waterbodyName}
                onChange={(e) => setWaterbodyName(e.target.value)}
                placeholder="e.g. Riverside Brook"
                className={inputClass}
              />
              <Hint>
                Use the same name on repeat visits so observations group into a
                history for that site.
              </Hint>
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Type of water">
                <select
                  value={waterbodyKind}
                  onChange={(e) => setWaterbodyKind(e.target.value as WaterbodyKind)}
                  className={inputClass}
                >
                  {schema.waterbody_kinds.map((k) => (
                    <option key={k} value={k}>
                      {k.charAt(0).toUpperCase() + k.slice(1)}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Area or district">
                <input
                  value={locality}
                  onChange={(e) => setLocality(e.target.value)}
                  placeholder="Optional"
                  className={inputClass}
                />
              </Field>
            </div>

            <Field label="Location">
              <div className="flex gap-2 items-start flex-wrap">
                <input
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  placeholder="Latitude"
                  inputMode="decimal"
                  className={`${inputClass} flex-1 min-w-[120px]`}
                />
                <input
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  placeholder="Longitude"
                  inputMode="decimal"
                  className={`${inputClass} flex-1 min-w-[120px]`}
                />
                <button
                  type="button"
                  onClick={useMyLocation}
                  disabled={geoBusy}
                  className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 disabled:opacity-50 transition-colors"
                >
                  {geoBusy ? (
                    <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <Crosshair size={13} aria-hidden="true" />
                  )}
                  Use my location
                </button>
              </div>
              <Hint>Optional, but coordinates put the observation on the map.</Hint>
            </Field>
          </div>
        </Card>

        {/* When */}
        <Card title="When" subtitle="When did you see it?">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date">
              <input
                type="date"
                value={observedDate}
                onChange={(e) => setObservedDate(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Time">
              <input
                type="time"
                value={observedTime}
                onChange={(e) => setObservedTime(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        </Card>

        {/* Appearance */}
        <Card
          title="What the water looked like"
          subtitle="Choose Yes, No, Not sure, or Skip for each"
        >
          <div className="space-y-4">
            <PresenceGrid
              fields={sectionFor("appearance")?.fields ?? []}
              value={appearance}
              onChange={setAppearance}
            />

            <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-surface-border">
              <Field label="Water clarity">
                <select
                  value={clarity}
                  onChange={(e) => setClarity(e.target.value as Clarity)}
                  className={inputClass}
                >
                  {schema.clarity_options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Colour, in your words">
                <input
                  value={colourNote}
                  onChange={(e) => setColourNote(e.target.value)}
                  placeholder="e.g. brownish, milky, normal"
                  className={inputClass}
                />
              </Field>
            </div>
          </div>
        </Card>

        {/* Biodiversity */}
        <Card
          title="Life in and around the water"
          subtitle="Seeing nothing is useful too — answer No rather than Skip if you looked"
        >
          <PresenceGrid
            fields={sectionFor("biodiversity")?.fields ?? []}
            value={biodiversity}
            onChange={setBiodiversity}
          />
        </Card>

        {/* Context */}
        <Card
          title="What was happening nearby"
          subtitle="Weather and activity help explain what you saw"
        >
          <PresenceGrid
            fields={sectionFor("context")?.fields ?? []}
            value={context}
            onChange={setContext}
          />
        </Card>

        {/* Measurements */}
        <Card title="Measurements" subtitle={schema.measurement_note}>
          <div className="grid gap-4 sm:grid-cols-2">
            {schema.measurements.map((m) => (
              <Field key={m.code} label={`${m.label}${m.unit ? ` (${m.unit})` : ""}`}>
                <input
                  value={measurements[m.code] ?? ""}
                  onChange={(e) =>
                    setMeasurements((prev) => ({ ...prev, [m.code]: e.target.value }))
                  }
                  placeholder="Leave blank if not measured"
                  inputMode="decimal"
                  className={inputClass}
                />
              </Field>
            ))}
          </div>
        </Card>

        {/* Photos */}
        <Card title="Photos" subtitle="Optional. Up to three images.">
          <div className="space-y-3">
            <label className="inline-flex items-center gap-1.5 rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs text-ink-body hover:border-accent-cyan/40 cursor-pointer transition-colors w-fit">
              <Camera size={13} aria-hidden="true" />
              Add photos
              <input
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => void onPickPhotos(e.target.files)}
              />
            </label>

            {photos.length > 0 && (
              <ul className="space-y-2">
                {photos.map((p, i) => (
                  <li
                    key={`${p.filename}-${i}`}
                    className="flex items-center gap-3 rounded-lg border border-surface-border bg-surface-panel p-2"
                  >
                    {p.uri ? (
                      <img
                        src={p.uri}
                        alt=""
                        className="h-12 w-12 rounded object-cover shrink-0"
                      />
                    ) : (
                      <div className="h-12 w-12 rounded bg-surface-raised shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] text-ink-body truncate">
                        {p.filename}
                      </div>
                      <input
                        value={p.caption}
                        onChange={(e) =>
                          setPhotos((prev) =>
                            prev.map((q, j) =>
                              j === i ? { ...q, caption: e.target.value } : q,
                            ),
                          )
                        }
                        placeholder="Caption (optional)"
                        className="mt-1 w-full bg-transparent text-[11px] text-ink-muted border-b border-surface-border focus:border-accent-cyan focus:outline-none"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                      className="p-1.5 text-ink-faint hover:text-accent-red transition-colors"
                      aria-label={`Remove ${p.filename}`}
                    >
                      <Trash2 size={13} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <p className="text-[11px] text-ink-faint">
              Any automated reading of a photo is labelled{" "}
              <span className="text-ink-muted">
                &ldquo;AI-assisted observation — human verification required&rdquo;
              </span>{" "}
              and is never treated as fact until a reviewer confirms it.
            </p>
          </div>
        </Card>

        {/* Notes */}
        <Card title="Anything else" subtitle="In your own words">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="Optional — anything that seemed unusual or worth knowing"
            className={`${inputClass} resize-y`}
          />
        </Card>

        {submitError && <ErrorNote message={submitError} />}

        {/* Submit */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <p className="text-[11px] text-ink-muted">
            {answeredCount} field{answeredCount === 1 ? "" : "s"} answered.{" "}
            {answeredCount < 4
              ? "Four or more lets the AI suggest an ecosystem status."
              : "Enough for an ecosystem status to be suggested."}
          </p>
          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-md bg-accent-cyan/15 border border-accent-cyan/40 px-4 py-2.5 text-sm text-accent-cyan hover:bg-accent-cyan/25 disabled:opacity-50 transition-colors"
          >
            {submitting ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <Check size={14} aria-hidden="true" />
            )}
            {submitting ? "Saving…" : "Submit observation"}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Local components
// =============================================================================

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-surface-border bg-surface-raised p-5">
      <div className="mb-4">
        <h2 className="text-sm text-ink-primary">{title}</h2>
        {subtitle && <p className="text-[11px] text-ink-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-compact text-[10px] text-ink-muted">
        {label}
        {required && <span className="text-accent-red ml-1">*</span>}
      </span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="text-[10px] text-ink-faint mt-1">{children}</p>;
}

function PresenceGrid({
  fields,
  value,
  onChange,
}: {
  fields: Array<{ code: string; label: string }>;
  value: PresenceMap;
  onChange: (next: PresenceMap) => void;
}) {
  return (
    <ul className="space-y-2.5">
      {fields.map((f) => {
        const current = value[f.code] ?? "not_available";
        return (
          <li
            key={f.code}
            className="flex items-center justify-between gap-3 flex-wrap py-1.5 border-b border-surface-border last:border-0"
          >
            <span className="text-sm text-ink-body min-w-[180px] flex-1">{f.label}</span>
            <div className="flex gap-1" role="group" aria-label={f.label}>
              {PRESENCE_CHOICES.map((c) => {
                const active = current === c.value;
                return (
                  <button
                    key={c.value}
                    type="button"
                    title={c.hint}
                    aria-pressed={active}
                    onClick={() => onChange({ ...value, [f.code]: c.value })}
                    className={
                      active
                        ? "rounded-md border border-accent-cyan/50 bg-accent-cyan/15 px-2.5 py-1 text-[11px] text-accent-cyan transition-colors"
                        : "rounded-md border border-surface-border bg-surface-bg px-2.5 py-1 text-[11px] text-ink-muted hover:text-ink-body hover:border-surface-border-hi transition-colors"
                    }
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
