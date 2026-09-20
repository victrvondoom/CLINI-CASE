// Shared atoms + shell components for ClinCase (dark aurora theme)
const { useState, useEffect, useRef, useCallback, useMemo } = React;

// ---------- Icons (lucide-style, stroke 2) ----------
const Icon = ({ d, size = 18, className = "", children }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    {children || (d && <path d={d} />)}
  </svg>
);

const I = {
  Activity: (p) => <Icon {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></Icon>,
  Sparkles: (p) => <Icon {...p}><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z"/><path d="M19 14v4M21 16h-4"/></Icon>,
  ArrowRight: (p) => <Icon {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></Icon>,
  ArrowLeft: (p) => <Icon {...p}><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></Icon>,
  Check: (p) => <Icon {...p}><polyline points="20 6 9 17 4 12"/></Icon>,
  CheckCircle: (p) => <Icon {...p}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></Icon>,
  XCircle: (p) => <Icon {...p}><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></Icon>,
  AlertCircle: (p) => <Icon {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Icon>,
  Stethoscope: (p) => <Icon {...p}><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/><circle cx="20" cy="10" r="2"/></Icon>,
  Download: (p) => <Icon {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></Icon>,
  FileText: (p) => <Icon {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></Icon>,
  Play: (p) => <Icon {...p}><polygon points="6 3 20 12 6 21 6 3"/></Icon>,
  Loader: (p) => <Icon {...p}><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></Icon>,
  Clock: (p) => <Icon {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></Icon>,
  Cpu: (p) => <Icon {...p}><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="2" x2="9" y2="4"/><line x1="15" y1="2" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="22"/><line x1="15" y1="20" x2="15" y2="22"/><line x1="20" y1="9" x2="22" y2="9"/><line x1="20" y1="14" x2="22" y2="14"/><line x1="2" y1="9" x2="4" y2="9"/><line x1="2" y1="14" x2="4" y2="14"/></Icon>,
  Mail: (p) => <Icon {...p}><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></Icon>,
  Menu: (p) => <Icon {...p}><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></Icon>,
  Shield: (p) => <Icon {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></Icon>,
  ChevronDown: (p) => <Icon {...p}><polyline points="6 9 12 15 18 9"/></Icon>,
  ChevronRight: (p) => <Icon {...p}><polyline points="9 18 15 12 9 6"/></Icon>,
  X: (p) => <Icon {...p}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Icon>,
  Command: (p) => <Icon {...p}><path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/></Icon>,
  DollarSign: (p) => <Icon {...p}><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></Icon>,
  Sun: (p) => <Icon {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></Icon>,
  Moon: (p) => <Icon {...p}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></Icon>,
  AlertTriangle: (p) => <Icon {...p}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></Icon>,
  Database: (p) => <Icon {...p}><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></Icon>,
  Pill: (p) => <Icon {...p}><path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/></Icon>,
  Book: (p) => <Icon {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></Icon>,
  BookOpen: (p) => <Icon {...p}><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></Icon>,
  LayoutDashboard: (p) => <Icon {...p}><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></Icon>,
  FolderOpen: (p) => <Icon {...p}><path d="M6 14l1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/></Icon>,
  Upload: (p) => <Icon {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></Icon>,
  CloudUpload: (p) => <Icon {...p}><path d="M16 16l-4-4-4 4"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/><polyline points="16 16 12 12 8 16"/></Icon>,
  BarChart3: (p) => <Icon {...p}><path d="M3 3v18h18"/><path d="M7 16V8"/><path d="M12 16v-5"/><path d="M17 16v-3"/></Icon>,
  UserCheck: (p) => <Icon {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></Icon>,
  ShieldCheck: (p) => <Icon {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></Icon>,
  Settings: (p) => <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></Icon>,
  Scale: (p) => <Icon {...p}><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></Icon>,
  Search: (p) => <Icon {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></Icon>,
  TrendingUp: (p) => <Icon {...p}><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></Icon>,
  TrendingDown: (p) => <Icon {...p}><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></Icon>,
  Plus: (p) => <Icon {...p}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></Icon>,
  Copy: (p) => <Icon {...p}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></Icon>,
  Filter: (p) => <Icon {...p}><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></Icon>,
  Eye: (p) => <Icon {...p}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></Icon>,
  GitBranch: (p) => <Icon {...p}><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></Icon>,
  RefreshCw: (p) => <Icon {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></Icon>,
  Bell: (p) => <Icon {...p}><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></Icon>,
  HelpCircle: (p) => <Icon {...p}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></Icon>,
  Zap: (p) => <Icon {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></Icon>,
  Heart: (p) => <Icon {...p}><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></Icon>,
  Cross: (p) => <Icon {...p}><path d="M11 2a2 2 0 0 0-2 2v5H4a2 2 0 0 0-2 2v2c0 1.1.9 2 2 2h5v5c0 1.1.9 2 2 2h2a2 2 0 0 0 2-2v-5h5a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2h-5V4a2 2 0 0 0-2-2h-2z"/></Icon>,
};

// ---------- Brand hue (CSS var) ----------
function applyBrandHue(hue) {
  document.documentElement.style.setProperty("--brand-hue", String(hue));
}

// ---------- Aurora background blobs (Home only) ----------
function AuroraBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-0 overflow-hidden motion-reduce:hidden">
      <div
        className="absolute -top-40 -left-32 w-[640px] h-[640px] rounded-full motion-safe:animate-aurora-a"
        style={{ background: "radial-gradient(circle, var(--aurora-a) 0%, transparent 65%)", filter: "blur(var(--aurora-blur))", willChange: "transform" }}
      />
      <div
        className="absolute top-20 right-[-180px] w-[560px] h-[560px] rounded-full motion-safe:animate-aurora-b"
        style={{ background: "radial-gradient(circle, var(--aurora-b) 0%, transparent 65%)", filter: "blur(var(--aurora-blur))", willChange: "transform" }}
      />
      <div
        className="absolute top-[280px] left-[40%] w-[480px] h-[480px] rounded-full motion-safe:animate-aurora-c"
        style={{ background: "radial-gradient(circle, var(--aurora-c) 0%, transparent 65%)", filter: "blur(var(--aurora-blur))", willChange: "transform" }}
      />
    </div>
  );
}

// ---------- App shell (sidenav + topbar + content) ----------
function AppShell({ children, density, showAurora, route, navigate, onSearch, onOpenShortcuts, onNewCase }) {
  const [navOpen, setNavOpen] = useState(false);
  // Close drawer on route change
  useEffect(() => { setNavOpen(false); }, [route]);
  // Close drawer on resize to lg+
  useEffect(() => {
    const onResize = () => { if (window.innerWidth >= 1024) setNavOpen(false); };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return (
    <div className={`relative min-h-screen bg-surface-bg text-ink-primary antialiased ${density === "compact" ? "text-[14px]" : "text-[15px]"}`}>
      {/* Subtle enterprise grid background everywhere */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 grid-bg opacity-90" />
      {showAurora && <AuroraBackdrop />}
      <ActivityTicker />
      <TopBar onSearch={onSearch} onOpenShortcuts={onOpenShortcuts} onMenuToggle={() => setNavOpen((o) => !o)} navOpen={navOpen} />
      <Sidenav route={route} navigate={navigate} navOpen={navOpen} onClose={() => setNavOpen(false)} />
      <main className={`relative lg:pl-[240px] pt-14 sm:pt-[88px]`}>
        <div className={`mx-auto max-w-[1400px] px-4 sm:px-6 ${density === "compact" ? "py-5 sm:py-6" : "py-6 sm:py-8"}`}>
          {children}
        </div>
        <BottomBar />
      </main>
      <FAB onClick={onNewCase} />
    </div>
  );
}

// ---------- Live activity ticker (top of page, above topbar) ----------
function ActivityTicker() {
  const items = [
    { tone: "emerald", icon: "CheckCircle", text: "3 cases just decided in the last 5 min" },
    { tone: "brand",   icon: "Activity",    text: "Anthem MCG-2026.04 policy synced · 12 references re-indexed" },
    { tone: "amber",   icon: "AlertCircle", text: "AUTH-2914 escalated to nurse reviewer · LVEF missing" },
    { tone: "emerald", icon: "Heart",       text: "Patient M.C. — Trastuzumab approved in 4m 12s" },
    { tone: "cyan",    icon: "Zap",         text: "Average decision time today — 6.4 min (−71% vs payer median)" },
    { tone: "brand",   icon: "Sparkles",    text: "ClinCase signed BAA #4 · Sutter Health onboarded" },
    { tone: "emerald", icon: "ShieldCheck", text: "All systems operational · 99.98% uptime (30d)" },
  ];
  const all = [...items, ...items];
  return (
    <div className="fixed top-0 inset-x-0 z-40 h-7 overflow-hidden border-b border-surface-border bg-surface-raised/95 backdrop-blur-md hidden sm:block">
      {/* LIVE badge with solid backdrop — sits above marquee */}
      <div className="absolute left-0 top-0 bottom-0 z-20 flex items-center gap-1.5 pl-3 pr-4 bg-surface-raised">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-70 animate-ping" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent-green" />
        </span>
        <span className="text-[9px] font-mono uppercase tracking-widest text-ink-muted">Live</span>
        {/* Soft fade from solid badge backdrop into the scrolling track */}
        <span className="absolute inset-y-0 -right-6 w-6 bg-gradient-to-r from-surface-raised to-transparent pointer-events-none" />
      </div>
      <div className="absolute inset-y-0 right-0 z-10 w-24 pointer-events-none bg-gradient-to-l from-surface-raised via-surface-raised/70 to-transparent" />
      <div className="marquee-track flex items-center gap-10 h-full whitespace-nowrap pl-28">
        {all.map((it, i) => {
          const Ico = I[it.icon] || I.Activity;
          const tone = it.tone === "emerald" ? "text-accent-green"
            : it.tone === "amber" ? "text-accent-amber"
            : it.tone === "cyan" ? "text-accent-cyan"
            : "text-accent-brand-glow";
          return (
            <span key={i} className="inline-flex items-center gap-2 text-[11px] font-mono text-ink-body">
              <Ico size={11} className={tone} />
              <span>{it.text}</span>
              <span className="text-ink-faint">—</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Floating Action Button (New Case) ----------
function FAB({ onClick }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className="fixed bottom-6 right-6 z-30 group inline-flex items-center gap-2 h-14 pl-4 pr-5 rounded-full text-white font-medium text-sm fab-pulse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg transition-transform active:scale-[0.97]"
      style={{
        background: "linear-gradient(180deg, #2563d9 0%, #0033a1 100%)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.20), 0 0 0 1px rgba(0,51,161,0.55), 0 18px 40px -12px rgba(0,51,161,0.55)",
      }}
      title="New case (N)"
    >
      <span className="w-7 h-7 rounded-full grid place-items-center bg-white/15">
        <I.Plus size={16} className="text-white" />
      </span>
      <span className="max-w-0 overflow-hidden whitespace-nowrap transition-all duration-300 group-hover:max-w-[180px]">
        <span className="pl-1">New case</span>
      </span>
      <kbd className="hidden md:inline-block px-1.5 py-0.5 text-[10px] font-mono bg-white/20 rounded text-white/95">N</kbd>
    </button>
  );
}

// ---------- Sidenav ----------
const SIDENAV_SECTIONS = [
  {
    label: "Workspace",
    items: [
      { key: "dashboard",   label: "Dashboard",     icon: "LayoutDashboard", to: "#/dashboard", kbd: "G D" },
      { key: "cases",       label: "Cases",         icon: "FolderOpen",      to: "#/cases",     kbd: "G C", badgeKey: "active" },
      { key: "intake",      label: "Drop a scan",   icon: "Upload",          to: "#/intake",    kbd: "G I", chip: "INTAKE" },
      { key: "compare",     label: "Compare",       icon: "Scale",           to: "#/compare",   kbd: "G K" },
      { key: "bulk",        label: "Bulk Import",   icon: "Upload",          to: "#/cases/bulk-import", kbd: "G B", chip: "CMS-0057-F" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { key: "policies",    label: "Policies",      icon: "BookOpen",        to: "#/policies",  kbd: "G P" },
      { key: "agents",      label: "Agents",        icon: "Cpu",             to: "#/agents",    kbd: "G A" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { key: "cohorts",     label: "Cohorts",       icon: "BarChart3",       to: "#/cohorts",   kbd: "G O" },
      { key: "reviewer",    label: "Reviewer Queue",icon: "UserCheck",       to: "#/reviewer",  kbd: "G R", badgeKey: "refer" },
      { key: "compliance",  label: "Compliance",    icon: "ShieldCheck",     to: "#/compliance",kbd: "G M" },
      { key: "about",       label: "About ClinCase", icon: "Sparkles",        to: "#/about",     kbd: "G ?", chip: "PITCH" },
    ],
  },
];

const BOOK_OPEN_ICON = "BookOpen";
// add BookOpen if not present
if (typeof window !== "undefined" && !window.__clincase_bookopen) {
  window.__clincase_bookopen = true;
}

function Sidenav({ route, navigate, navOpen, onClose }) {
  const extra = window.CLINCASE_EXTRA || {};
  const badges = {
    active: extra.ACTIVE_COUNT || 0,
    refer: extra.REFER_COUNT || 0,
  };
  // route-prefix matching for active state
  const isActive = (to) => {
    if (!to) return false;
    const r = route || "#/dashboard";
    if (to === "#/dashboard" && (r === "#/" || r === "#/dashboard")) return true;
    if (to === "#/cases" && r.startsWith("#/cases") && !r.includes("bulk-import")) return true;
    if (to === "#/cases/bulk-import" && r === "#/cases/bulk-import") return true;
    if (to === r) return true;
    if (to !== "#/" && r.startsWith(to)) return true;
    return false;
  };

  return (
    <>
      {/* Backdrop for mobile drawer */}
      {navOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40 backdrop-blur-sm motion-safe:animate-fade-in"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed left-0 z-50 w-[260px] lg:w-[240px] border-r border-surface-border bg-surface-bg/98 lg:bg-surface-bg/95 backdrop-blur-sm
          top-14 sm:top-[84px] h-[calc(100vh-3.5rem)] sm:h-[calc(100vh-84px)]
          transform transition-transform duration-200 ease-out
          ${navOpen ? "translate-x-0" : "-translate-x-full"}
          lg:translate-x-0 lg:block`}
        aria-hidden={!navOpen ? "true" : undefined}
      >
      <nav className="h-full overflow-y-auto py-4 px-3 flex flex-col">
        <div className="flex-1 space-y-5">
          {SIDENAV_SECTIONS.map((sec) => (
            <div key={sec.label}>
              <div className="px-2.5 mb-1.5 text-[10px] font-mono uppercase tracking-widest text-ink-faint">{sec.label}</div>
              <ul className="space-y-0.5">
                {sec.items.map((it) => {
                  const Ico = I[it.icon] || I.Book;
                  const active = isActive(it.to);
                  const disabled = it.disabled;
                  const cls = `group relative w-full flex items-center gap-2.5 pl-3 pr-2 py-2 rounded-md text-[13px] transition-colors ${
                    disabled
                      ? "text-ink-faint cursor-not-allowed"
                      : active
                        ? "bg-accent-brand/10 text-ink-primary font-medium"
                        : "text-ink-body hover:bg-surface-raised-hi hover:text-ink-primary"
                  }`;
                  const btn = (
                    <button
                      key={it.key}
                      onClick={() => !disabled && it.to && navigate(it.to)}
                      disabled={disabled}
                      className={cls}
                      aria-current={active ? "page" : undefined}
                    >
                      {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-accent-brand" />}
                      <Ico size={15} className={`shrink-0 ${active ? "text-accent-brand-glow" : disabled ? "text-ink-faint" : "text-ink-muted group-hover:text-ink-body"}`} />
                      <span className="flex-1 text-left truncate">{it.label}</span>
                      {it.chip && (
                        <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface-raised border border-surface-border text-ink-muted">{it.chip}</span>
                      )}
                      {it.badgeKey && badges[it.badgeKey] > 0 && (
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${active ? "bg-accent-brand text-white" : "bg-surface-raised-hi text-ink-body"}`}>{badges[it.badgeKey]}</span>
                      )}
                    </button>
                  );
                  return <li key={it.key}>{btn}</li>;
                })}
              </ul>
            </div>
          ))}
        </div>
        {/* bottom: org card */}
        <div className="mt-4 pt-3 border-t border-surface-border space-y-2">
          <div className="px-2.5 py-2 rounded-md bg-surface-raised border border-surface-border">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md grid place-items-center text-[11px] font-mono font-semibold text-white"
                   style={{ background: "linear-gradient(135deg, #0033a1 0%, #00a3e0 100%)" }}>AF</div>
              <div className="flex-1 min-w-0 leading-tight">
                <div className="text-[12px] font-medium text-ink-primary truncate">aerofyta-team</div>
                <div className="text-[10px] font-mono text-ink-muted truncate">the hackathon</div>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-surface-border flex items-center justify-between">
              <span className="text-[9px] font-mono uppercase tracking-wider text-ink-muted">SOC2 · HIPAA</span>
              <span className="inline-flex items-center gap-1 text-[9px] font-mono text-accent-green">
                <span className="w-1 h-1 rounded-full bg-accent-green status-dot-live" /> SECURE
              </span>
            </div>
          </div>
        </div>
      </nav>
    </aside>
    </>
  );
}

// ---------- Institutional logo mark (caduceus-inspired shield) ----------
function ClinCaseMark({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <defs>
        <linearGradient id="axShieldGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1f4dbf" />
          <stop offset="60%" stopColor="#0033a1" />
          <stop offset="100%" stopColor="#1a2b5c" />
        </linearGradient>
        <linearGradient id="axShieldGloss" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="axTeal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#00b5b8" />
          <stop offset="100%" stopColor="#00a3e0" />
        </linearGradient>
      </defs>
      {/* shield body */}
      <path d="M16 1.5 L28 5 V14.5 C28 22 22.6 27.6 16 30.5 C9.4 27.6 4 22 4 14.5 V5 Z" fill="url(#axShieldGrad)" stroke="#0a1f44" strokeWidth="0.6" />
      <path d="M16 1.5 L28 5 V14.5 C28 22 22.6 27.6 16 30.5 C9.4 27.6 4 22 4 14.5 V5 Z" fill="url(#axShieldGloss)" />
      {/* medical cross + waveform combined */}
      <rect x="14.5" y="7" width="3" height="16" rx="0.7" fill="#ffffff" opacity="0.92" />
      <rect x="8.5" y="13" width="15" height="3" rx="0.7" fill="#ffffff" opacity="0.92" />
      {/* teal accent waveform */}
      <path d="M7 19.5 L10 19.5 L11.2 17 L13 22 L14.5 18.5 L16 21 L17.5 18.5 L19 22 L20.8 17 L22 19.5 L25 19.5" fill="none" stroke="url(#axTeal)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TopBar({ onSearch, onOpenShortcuts, onMenuToggle, navOpen }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header
      className={`fixed top-0 sm:top-7 inset-x-0 z-30 transition-colors duration-200 border-b ${
        scrolled
          ? "backdrop-blur-xl bg-surface-bg/90 border-surface-border"
          : "bg-surface-bg/70 backdrop-blur-md border-surface-border/60"
      }`}
    >
      <div className="h-14 flex items-center justify-between px-3 sm:px-4 lg:px-5 gap-2 sm:gap-3">
        {/* Mobile hamburger — only on <lg */}
        <button
          type="button"
          onClick={onMenuToggle}
          className="lg:hidden inline-grid place-items-center w-9 h-9 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          aria-label={navOpen ? "Close menu" : "Open menu"}
          aria-expanded={navOpen}
        >
          {navOpen ? <I.X size={16} /> : <I.Menu size={16} />}
        </button>
        <a href="#/dashboard" className="flex items-center gap-2 sm:gap-3 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand rounded-md min-w-0 lg:w-[228px] lg:shrink-0">
          <ClinCaseMark size={32} />
          <div className="leading-tight min-w-0">
            <div className="font-semibold tracking-[0.01em] text-ink-primary text-[15px] truncate">ClinCase<span className="text-accent-cyan">.</span></div>
            <div className="hidden sm:block text-[9px] text-ink-muted font-mono uppercase tracking-[0.18em]">Clinical AI Platform</div>
          </div>
        </a>
        <div className="flex-1 max-w-xl hidden md:block">
          <button
            type="button"
            onClick={() => onSearch && onSearch()}
            className="w-full h-9 px-3 flex items-center gap-2.5 rounded-md border border-surface-border bg-surface-raised hover:border-surface-border-hi text-left text-[13px] text-ink-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <I.Search size={14} className="text-ink-faint" />
            <span className="flex-1">Search cases, policies, agents…</span>
            <span className="text-[10px] font-mono text-ink-faint">⌘K</span>
          </button>
        </div>
        {/* Mobile-only search icon */}
        <button
          type="button"
          onClick={() => onSearch && onSearch()}
          className="md:hidden inline-grid place-items-center w-9 h-9 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary transition-colors shrink-0"
          aria-label="Search"
        >
          <I.Search size={14} />
        </button>
        <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
          <StatusPill />
          <NotificationsBell />
          <button
            type="button"
            onClick={onOpenShortcuts}
            className="hidden sm:inline-grid place-items-center w-8 h-8 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts (?)"
          >
            <I.HelpCircle size={14} />
          </button>
          <ThemeToggle />
          <UserChip />
        </div>
      </div>
    </header>
  );
}

// ---------- Status pill ("All systems operational") ----------
function StatusPill() {
  return (
    <a href="#/compliance" className="hidden lg:inline-flex items-center gap-2 h-8 px-2.5 rounded-md border border-emerald-500/30 bg-emerald-500/[0.06] text-[11px] font-mono text-accent-green hover:bg-emerald-500/10 transition-colors" title="99.98% uptime, 30d">
      <span className="relative flex h-1.5 w-1.5">
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent-green status-dot-live" />
      </span>
      <span className="tracking-tight">All systems operational</span>
    </a>
  );
}

// ---------- Notifications bell ----------
function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(3);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  const items = [
    { tone: "emerald", icon: "CheckCircle", title: "AUTH-2918 approved", body: "Trastuzumab · Anthem MCG-2026.04 · 4m 12s", time: "just now" },
    { tone: "amber",   icon: "AlertCircle", title: "AUTH-2914 needs review", body: "LVEF missing — escalated to nurse reviewer", time: "6m" },
    { tone: "brand",   icon: "BookOpen",    title: "Policy update synced", body: "UnitedHealth UHCO-2026-04 · 12 references re-indexed", time: "24m" },
    { tone: "cyan",    icon: "Activity",    title: "Daily digest ready", body: "34 cases decided · 92.4% within SLA", time: "2h" },
  ];
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => { setOpen((o) => !o); if (unread) setUnread(0); }}
        className="relative inline-grid place-items-center w-8 h-8 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
        aria-label="Notifications"
      >
        <I.Bell size={14} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent-red text-white text-[9px] font-mono font-semibold grid place-items-center border-2 border-surface-bg">{unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-[360px] rounded-xl border border-surface-border bg-surface-raised overflow-hidden card-pop" style={{ boxShadow: "var(--shadow-pop)" }}>
          <div className="px-3.5 py-2.5 border-b border-surface-border flex items-center justify-between">
            <span className="text-[12px] font-semibold text-ink-primary">Notifications</span>
            <span className="text-[10px] font-mono text-ink-muted">live · 4 new</span>
          </div>
          <ul className="max-h-[360px] overflow-auto divide-y divide-surface-border">
            {items.map((it, i) => {
              const Ico = I[it.icon] || I.Activity;
              const toneCls = it.tone === "emerald" ? "text-accent-green bg-emerald-500/10 border-emerald-500/30"
                : it.tone === "amber" ? "text-accent-amber bg-amber-500/10 border-amber-500/30"
                : it.tone === "cyan" ? "text-accent-cyan bg-cyan-500/10 border-cyan-500/30"
                : "text-accent-brand-glow bg-accent-brand/10 border-accent-brand/30";
              return (
                <li key={i} className="px-3.5 py-2.5 hover:bg-surface-raised-hi flex items-start gap-2.5">
                  <span className={`shrink-0 w-7 h-7 rounded-md grid place-items-center border ${toneCls}`}><Ico size={13} /></span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12.5px] font-medium text-ink-primary truncate">{it.title}</div>
                    <div className="text-[11px] text-ink-muted truncate">{it.body}</div>
                  </div>
                  <span className="text-[10px] font-mono text-ink-faint shrink-0 mt-0.5">{it.time}</span>
                </li>
              );
            })}
          </ul>
          <div className="px-3.5 py-2 border-t border-surface-border bg-surface-raised-hi/40 flex items-center justify-between">
            <button className="text-[11px] font-mono text-ink-muted hover:text-ink-body">Mark all read</button>
            <a href="#/dashboard" className="text-[11px] font-mono text-accent-brand-glow hover:underline">View all →</a>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- User chip with role ----------
function UserChip() {
  return (
    <div className="hidden md:flex items-center gap-2 h-8 pl-1 pr-2.5 rounded-md border border-surface-border bg-surface-raised hover:border-surface-border-hi transition-colors">
      <div className="w-6 h-6 rounded-full grid place-items-center text-[10px] font-mono font-semibold text-white" style={{ background: "linear-gradient(135deg, #0033a1 0%, #00a3e0 100%)" }}>AF</div>
      <div className="leading-tight hidden lg:block">
        <div className="text-[11px] font-medium text-ink-primary">aerofyta</div>
        <div className="text-[9px] font-mono text-ink-muted uppercase tracking-wider">Admin</div>
      </div>
      <span className="hidden xl:inline-flex items-center text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-accent-green border border-emerald-500/30 uppercase tracking-wider">Verified</span>
    </div>
  );
}

// ---------- Keyboard shortcuts overlay ----------
function ShortcutsOverlay({ open, onClose }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  const groups = [
    { label: "Navigation", items: [
      { keys: ["G", "D"], desc: "Go to Dashboard" },
      { keys: ["G", "C"], desc: "Go to Cases" },
      { keys: ["G", "K"], desc: "Go to Compare" },
      { keys: ["G", "P"], desc: "Go to Policies" },
      { keys: ["G", "A"], desc: "Go to Agents" },
      { keys: ["G", "O"], desc: "Go to Cohorts" },
      { keys: ["G", "R"], desc: "Reviewer Queue" },
      { keys: ["G", "M"], desc: "Compliance" },
    ]},
    { label: "Actions", items: [
      { keys: ["⌘", "K"], desc: "Open command palette" },
      { keys: ["N"],      desc: "New case" },
      { keys: ["R"],      desc: "Run ClinCase on current case" },
      { keys: ["/"],      desc: "Focus search" },
      { keys: ["?"],      desc: "Open this help" },
      { keys: ["Esc"],    desc: "Close dialogs" },
    ]},
  ];
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 backdrop-blur-md motion-safe:animate-fade-in p-6" onClick={onClose}>
      <div className="w-full max-w-2xl bg-surface-raised rounded-2xl border border-surface-border-hi overflow-hidden card-pop" onClick={(e) => e.stopPropagation()} style={{ boxShadow: "var(--shadow-pop)" }}>
        <div className="px-5 py-3.5 border-b border-surface-border flex items-center justify-between bg-surface-raised-hi/40">
          <div className="flex items-center gap-2">
            <I.HelpCircle size={16} className="text-accent-brand-glow" />
            <h2 className="font-semibold tracking-tight text-ink-primary">Keyboard Shortcuts</h2>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-md grid place-items-center hover:bg-surface-raised-hi text-ink-muted">
            <I.X size={14} />
          </button>
        </div>
        <div className="p-5 grid sm:grid-cols-2 gap-6">
          {groups.map((g) => (
            <div key={g.label}>
              <div className="text-[10px] font-mono uppercase tracking-widest text-ink-muted mb-2.5">{g.label}</div>
              <ul className="space-y-1.5">
                {g.items.map((it, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 py-1">
                    <span className="text-[13px] text-ink-body">{it.desc}</span>
                    <span className="flex items-center gap-1">
                      {it.keys.map((k, j) => (
                        <kbd key={j} className="px-1.5 py-0.5 text-[10px] font-mono bg-surface-raised-hi border border-surface-border rounded text-ink-primary min-w-[22px] text-center">{k}</kbd>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-surface-border bg-surface-raised-hi/40 flex items-center justify-between">
          <span className="text-[11px] font-mono text-ink-muted">Press <kbd className="px-1 rounded bg-surface-raised border border-surface-border">?</kbd> anywhere to open this</span>
          <span className="text-[11px] font-mono text-ink-faint">ClinCase · v0.9.4</span>
        </div>
      </div>
    </div>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    if (typeof document === "undefined") return false;
    return document.documentElement.classList.contains("dark");
  });
  useEffect(() => {
    const root = document.documentElement;
    if (dark) root.classList.add("dark");
    else root.classList.remove("dark");
    try { localStorage.setItem("clincase-theme", dark ? "dark" : "light"); } catch (e) {}
  }, [dark]);
  return (
    <button
      type="button"
      onClick={() => setDark((d) => !d)}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="hidden sm:inline-grid place-items-center w-8 h-8 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
    >
      {dark ? <I.Sun size={14} /> : <I.Moon size={14} />}
    </button>
  );
}

function KbdHint() {
  return (
    <div className="hidden md:flex items-center gap-1.5 ml-1 px-2 py-1 text-[11px] font-mono text-ink-body border border-surface-border-hi rounded-md bg-surface-raised motion-safe:animate-kbd-glow">
      <kbd className="px-1 rounded bg-surface-raised-hi text-ink-primary">⌘</kbd>
      <kbd className="px-1 rounded bg-surface-raised-hi text-ink-primary">K</kbd>
      <span className="text-ink-faint">·</span>
      <kbd className="px-1 rounded bg-surface-raised-hi text-ink-primary">R</kbd>
      <span>run</span>
    </div>
  );
}

function BottomBar() {
  return (
    <footer className="px-6 pb-8 pt-6 flex items-center justify-between text-xs text-ink-muted font-mono gap-4 flex-wrap">
      <span>5-agent LangGraph DAG · Powered by Claude Sonnet 4.6 · AWS-ready</span>
      <span>CMS-0057-F · 2026 / 2027 mandate</span>
    </footer>
  );
}

// ---------- Eyebrow / pill primitives ----------
function Eyebrow({ children, className = "" }) {
  return <div className={`text-[11px] font-mono uppercase tracking-widest text-ink-muted ${className}`}>{children}</div>;
}

function Pill({ children, tone = "slate", className = "" }) {
  // Dark-mode tones: subtle tinted background + matching text
  const tones = {
    slate:   "bg-surface-raised-hi text-ink-body border-surface-border",
    emerald: "bg-emerald-500/10 text-accent-green border-emerald-500/30",
    rose:    "bg-rose-500/10 text-accent-red border-rose-500/30",
    amber:   "bg-amber-500/10 text-accent-amber border-amber-500/30",
    blue:    "bg-blue-500/10 text-accent-blue border-blue-500/30",
    violet:  "bg-violet-500/10 text-accent-violet border-violet-500/30",
    brand:   "bg-accent-brand/10 text-accent-brand-glow border-accent-brand/35",
    cyan:    "bg-cyan-500/10 text-accent-cyan border-cyan-500/30",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider rounded border ${tones[tone] || tones.slate} ${className}`}>
      {children}
    </span>
  );
}

const VERDICT_META = {
  APPROVE: { tone: "emerald", icon: I.CheckCircle, label: "Approve",
             color: "#34d399", glow: "rgba(52,211,153,0.30)",
             text: "text-emerald-100", dim: "text-emerald-200/85",
             border: "border-emerald-500/40", bg: "bg-emerald-500/[0.06]" },
  DENY:    { tone: "rose",    icon: I.XCircle,    label: "Deny",
             color: "#fb7185", glow: "rgba(251,113,133,0.30)",
             text: "text-rose-100", dim: "text-rose-200/85",
             border: "border-rose-500/40", bg: "bg-rose-500/[0.06]" },
  REFER:   { tone: "amber",   icon: I.AlertCircle,label: "Refer",
             color: "#fbbf24", glow: "rgba(251,191,36,0.30)",
             text: "text-amber-100", dim: "text-amber-200/85",
             border: "border-amber-500/40", bg: "bg-amber-500/[0.06]" },
};

// ---------- Hash router ----------
function useHashRoute() {
  const [hash, setHash] = useState(() => window.location.hash || "#/");
  useEffect(() => {
    const onHash = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = useCallback((to) => { window.location.hash = to; }, []);
  return [hash, navigate];
}

Object.assign(window, {
  I, Icon, AppShell, AuroraBackdrop, Eyebrow, Pill, VERDICT_META, applyBrandHue, useHashRoute,
  ClinCaseMark, ShortcutsOverlay, ActivityTicker, FAB,
});
