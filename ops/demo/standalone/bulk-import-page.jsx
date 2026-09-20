/* global window, React */
const { useState: useStateB, useEffect: useEffectB } = React;

function BulkImportPage({ navigate }) {
  const { ROWS } = window.CLINCASE_BULK;
  const [dropped, setDropped] = useStateB(false);
  const [tick, setTick] = useStateB(0);

  // Slow tick to nudge progress bars
  useEffectB(() => {
    if (!dropped) return;
    const t = setInterval(() => setTick((x) => x + 1), 600);
    return () => clearInterval(t);
  }, [dropped]);

  const counts = ROWS.reduce(
    (acc, r) => {
      acc[r.status] = (acc[r.status] || 0) + 1;
      if (r.verdict) acc[r.verdict] = (acc[r.verdict] || 0) + 1;
      return acc;
    },
    {}
  );

  return (
    <div data-screen-label="cases-bulk-import" className="space-y-5">
      <header>
        <Eyebrow>Workspace · Bulk Import</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          FHIR Bulk Data $export
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[68ch]">
          Drop an NDJSON bundle (one Bundle per line) or paste a FHIR Bulk URL. ClinCase spins up parallel
          DAG workers, fans out the queue, and streams verdicts back as they finish — CMS-0057-F § IV.d compliant.
        </p>
      </header>

      {!dropped ? (
        <DropZone onDrop={() => setDropped(true)} />
      ) : (
        <>
          {/* Aggregate strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <AggTile label="cases imported" value={ROWS.length} />
            <AggTile label="elapsed"        value="8m 14s" />
            <AggTile label="approved"       value={counts.APPROVE || 0} accent="green" />
            <AggTile label="cost so far"    value="$1.08" />
          </div>

          {/* Queue */}
          <section className="rounded-2xl bg-surface-raised border border-surface-border overflow-hidden">
            <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
              <div>
                <div className="text-[11px] font-mono uppercase tracking-widest text-ink-muted">parallel queue</div>
                <div className="text-[14px] font-semibold text-ink-primary">
                  {(counts.running || 0)} running · {(counts.queued || 0)} queued · {(counts.done || 0)} done
                </div>
              </div>
              <div className="flex items-center gap-2 text-[11px] font-mono text-ink-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
                4 workers · streaming
              </div>
            </div>
            <ul className="divide-y divide-surface-border">
              {ROWS.map((r, i) => (
                <BulkRow key={r.id} row={r} tick={tick} idx={i} />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function DropZone({ onDrop }) {
  const [hover, setHover] = useStateB(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => { e.preventDefault(); setHover(false); onDrop(); }}
      onClick={onDrop}
      className={`rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
        hover
          ? "border-accent-brand bg-brand-50"
          : "border-surface-border-hi bg-surface-raised hover:bg-surface-raised-hi"
      } px-8 py-16 flex flex-col items-center text-center`}
    >
      <div className="w-14 h-14 rounded-2xl bg-accent-brand/10 border border-accent-brand/20 text-accent-brand flex items-center justify-center mb-4">
        <I.CloudUpload className="w-7 h-7" />
      </div>
      <div className="text-[18px] font-semibold text-ink-primary">Drop .ndjson or paste FHIR Bulk URL</div>
      <p className="mt-2 text-[13px] text-ink-body max-w-md">
        Each line should be a FHIR R4 Bundle. ClinCase fans out 4 workers in parallel and you'll see every
        case progress through the agent DAG live.
      </p>
      <div className="mt-5 flex items-center gap-2">
        <button className="px-3 py-1.5 text-[12px] font-medium bg-accent-brand text-white rounded-md inline-flex items-center gap-1.5">
          <I.Upload className="w-3.5 h-3.5" /> Browse files
        </button>
        <span className="text-[11px] font-mono text-ink-muted">or click anywhere to simulate drop</span>
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2 w-full max-w-md text-[11px] font-mono">
        <Hint k="format" v=".ndjson" />
        <Hint k="schema" v="FHIR R4" />
        <Hint k="auth"   v="OAuth2 PAT" />
      </div>
    </div>
  );
}

function Hint({ k, v }) {
  return (
    <div className="px-2.5 py-1.5 bg-surface-bg rounded border border-surface-border">
      <div className="text-ink-muted text-[10px] uppercase tracking-wider">{k}</div>
      <div className="text-ink-primary">{v}</div>
    </div>
  );
}

function AggTile({ label, value, accent }) {
  const color = accent === "green" ? "text-accent-green" : "text-ink-primary";
  return (
    <div className="rounded-xl bg-surface-raised border border-surface-border px-4 py-3">
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-muted">{label}</div>
      <div className={`text-[22px] font-semibold tabular-nums mt-0.5 ${color}`}>{value}</div>
    </div>
  );
}

function BulkRow({ row, tick, idx }) {
  // Simulated progress: running rows tick up slowly, capped just under 1.
  const live = row.status === "running"
    ? Math.min(0.97, row.progress + tick * 0.01 * (1 + (idx % 3) * 0.4))
    : row.progress;
  const pct = Math.round(live * 100);
  const tone =
    row.status === "done"
      ? row.verdict === "APPROVE" ? "green" : row.verdict === "DENY" ? "red" : "amber"
      : row.status === "running" ? "cyan"
      : "slate";
  return (
    <li className="px-5 py-3 flex items-center gap-4 hover:bg-surface-raised-hi transition-colors">
      <div className="font-mono text-[11px] text-ink-muted w-[120px] shrink-0 truncate">{row.id}</div>
      <div className="w-9 h-9 rounded-full bg-surface-raised-hi border border-surface-border flex items-center justify-center text-[11px] font-mono text-ink-body shrink-0">
        {row.initials}
      </div>
      <div className="hidden md:flex items-center gap-2 w-[180px] shrink-0">
        <PayerChip id={row.payer} small />
        <span className="text-[12px] text-ink-body truncate">{row.drug}</span>
      </div>
      <div className="flex-1 min-w-0">
        {row.status === "queued" ? (
          <div className="text-[11px] font-mono text-ink-faint">waiting…</div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-mono text-ink-muted truncate">
                {row.status === "done" ? "complete" : row.agent ? row.agent.replace(/_/g, " ") : "queued"}
              </span>
              <span className="text-[11px] font-mono text-ink-body tabular-nums">{pct}%</span>
            </div>
            <div className="h-1.5 bg-surface-raised-hi rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-[width] duration-500 ${
                  row.status === "done" ? "bg-accent-green" : "bg-accent-cyan"
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </>
        )}
      </div>
      <div className="w-[100px] shrink-0 flex justify-end">
        <Pill tone={tone}>
          {row.status === "done" ? row.verdict : row.status}
        </Pill>
      </div>
    </li>
  );
}

window.BulkImportPage = BulkImportPage;
