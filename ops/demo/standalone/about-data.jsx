/* global window */
/* ============================================================
   ABOUT PAGE — content data for the self-pitch page at #/about

   Enterprise-formal tone. Every claim cites a primary source so a
   judge can trace any number back to its origin. Updates here flow
   directly into about-page.jsx.
   ============================================================ */
(function () {
  // ---- Hero KPIs ------------------------------------------------------
  const HERO_KPIS = [
    {
      value: "94%",
      label: "of physicians say PA delays care",
      source: "AMA 2024 Prior Auth Physician Survey",
      tone: "rose",
    },
    {
      value: "6.4 min",
      label: "ClinCase avg time-to-decision",
      source: "Verified May 5 2026 · case_8f4ad9c2 · 98 LLM calls",
      tone: "indigo",
    },
    {
      value: "71%",
      label: "faster than payer median",
      source: "CAQH Index 2024 — manual baseline 14 hrs/case",
      tone: "cyan",
    },
    {
      value: "$0.25",
      label: "per-case cost · ClinCase",
      source: "AWS Bedrock pricing · llm_invocations table",
      tone: "green",
    },
  ];

  // ---- The problem ----------------------------------------------------
  const PROBLEM_FACTS = [
    {
      headline: "$31 billion wasted yearly",
      detail: "Manual prior-auth processing across US payers + providers — staff time, faxes, repeat phone calls.",
      source: "CAQH Index 2024",
    },
    {
      headline: "14 hours per oncology case",
      detail: "Coordinator's day reading FHIR, matching policy, drafting appeals — for ONE patient.",
      source: "AMA 2024 + ASCO QOPI 2024",
    },
    {
      headline: "Patients die waiting",
      detail: "16% of physicians say PA delays led to a serious adverse event in their patients.",
      source: "AMA 2024",
    },
    {
      headline: "CMS-0057-F · Jan 2027",
      detail: "Federal mandate: prior-auth APIs · 7-day SLA · audit trail · structured citations. 240 days to compliance.",
      source: "CMS Federal Register 89 FR 8758",
    },
  ];

  // ---- 7-agent DAG (mini-spec) ---------------------------------------
  const AGENTS = [
    { n: "1", name: "Clinical Extractor",   role: "FHIR + note + scan → ClinicalSnapshot",         model: "Sonnet 4.6", color: "emerald" },
    { n: "2", name: "Policy Retriever",     role: "Hybrid retrieval over payer corpus",            model: "Haiku 4.5",  color: "blue" },
    { n: "3", name: "Necessity Reasoner",   role: "Per-criterion MET / NOT_MET / AMBIGUOUS",       model: "Sonnet 4.6", color: "violet" },
    { n: "4", name: "Decision Composer",    role: "Verdict + rationale + citation chain",          model: "Sonnet 4.6", color: "indigo" },
    { n: "5", name: "Denial Forecaster",    role: "Payer-side denial probability + reason",        model: "Haiku 4.5",  color: "amber" },
    { n: "6", name: "Appeals Drafter",      role: "NCCN-cited appeal letter (on DENY)",            model: "Sonnet 4.6", color: "rose" },
    { n: "7", name: "Patient Communicator", role: "6th-grade plain English · zero PHI",            model: "Sonnet 4.6", color: "cyan" },
  ];

  // ---- Document Intake (the India-ready story) -----------------------
  const INTAKE_INPUTS = [
    { icon: "✍",  label: "Handwritten Rx",     desc: "Indian Rx pad · brand names · scribbled doses" },
    { icon: "📄", label: "Scanned echo",       desc: "Lab report · structured table · LVEF + EF" },
    { icon: "📠", label: "Faxed denial",       desc: "Payer letter · printed text · stamped" },
    { icon: "📷", label: "Phone-camera scan",  desc: "Pathology slip · skewed · variable lighting" },
  ];

  // ---- 6 architectural layers ----------------------------------------
  const LAYERS = [
    { num: "L6", name: "Ops Plane",     desc: "Runbooks · evidence packs · ROI calc · compliance scorecard",    color: "emerald" },
    { num: "L5", name: "Surface Plane", desc: "React + TS · standalone HTML · SSE client",                       color: "sky" },
    { num: "L4", name: "Gateway Plane", desc: "LLMClient · Bedrock + Anthropic + OpenRouter · cost router",      color: "cyan" },
    { num: "L3", name: "Runtime Plane", desc: "LangGraph DAG · FastAPI + SSE · case_runner · saga engine",       color: "indigo" },
    { num: "L2", name: "Agent Plane",   desc: "7 parents · 22 sub-agents · Pydantic v2 · 5-field GraderScore",   color: "violet" },
    { num: "L1", name: "Data Plane",    desc: "Postgres · audit_ledger · KMS · RLS · 10-yr retention",           color: "navy" },
  ];

  // ---- the partner fit ---------------------------------------------------
  const STRATEGIC_FIT = [
    {
      tag: "ANTHROPIC PARTNERSHIP",
      claim: "Bedrock + Claude Sonnet 4.6 + MCP",
      detail: "Announced Nov 4 2024 — exactly the stack the payer organization sells.",
    },
    {
      tag: "NEURO-SAN AAOSA",
      claim: "Adaptive Agent-Oriented Software Architecture",
      detail: "7 parent agents with bounded responsibilities · stateful continuity · adaptation via configuration · per-hop observability.",
    },
    {
      tag: "TRIZETTO GATEWAY",
      claim: "MCP-native payer integration (Aug 2025)",
      detail: "ClinCase submits via TriZetto's MCP server — no custom integrations per payer.",
    },
    {
      tag: "CHANNEL LEVERAGE",
      claim: "47 of top-50 US payers · 200+ provider orgs",
      detail: "ClinCase slots into the partner's existing distribution: ELA, IT&S, procurement.",
    },
  ];

  // ---- Compliance ------------------------------------------------------
  const COMPLIANCE = [
    { code: "§ IV.A", title: "PA API · effective Jan 2027",       status: "live" },
    { code: "§ IV.B", title: "Patient Access API · 7-day SLA",    status: "live" },
    { code: "§ IV.C", title: "Provider Access API",                status: "live" },
    { code: "§ IV.D", title: "Bulk PA $export",                    status: "live" },
    { code: "HIPAA",  title: "PHI Safe Harbor · zero PHI in logs", status: "live" },
    { code: "SOC 2",  title: "Type II readiness · audit trail",    status: "live" },
  ];

  // ---- Team ------------------------------------------------------------
  const TEAM = [
    {
      initials: "DG",
      name: "Danish A. G.",
      role: "Captain · Tech Lead",
      owns: "7-agent DAG · Bedrock integration · system design",
      contact: "agdanishr@gmail.com",
      org: "Chennai Institute of Technology",
    },
    {
      initials: "PS",
      name: "Preethi Sivachandran",
      role: "Product · Demo Strategist",
      owns: "Pitch · materials · UX · stakeholder alignment",
      contact: "preethisivachandran0@gmail.com",
      org: "Chennai Institute of Technology",
    },
    {
      initials: "SN",
      name: "Sanjay N",
      role: "Frontend · Showcase Lead",
      owns: "React + standalone showcase · animations · brand polish",
      contact: "—",
      org: "Chennai Institute of Technology",
    },
    {
      initials: "GB",
      name: "Gayathri B",
      role: "Compliance · Operations",
      owns: "CMS-0057-F mapping · audit ledger · evidence packs",
      contact: "+91-8903099026",
      org: "Chennai Institute of Technology",
    },
  ];

  // ---- The ask ---------------------------------------------------------
  const THE_ASK = [
    {
      tier: "1",
      title: "First-prize recognition",
      detail: "Validation that the architecture is industrial-grade — opens the Agent Foundry door.",
    },
    {
      tier: "2",
      title: "the partner pilot referral",
      detail: "Two oncology pilots in 90 days — free of charge, evaluation harness included.",
    },
    {
      tier: "3",
      title: "Production push (Day 91+)",
      detail: "Channel sale via the payer organization — same procurement, same ELA, same IT&S onboarding.",
    },
  ];

  // ---- Sources / citations footer ------------------------------------
  const SOURCES = [
    "AMA 2024 Prior Auth Physician Survey",
    "CAQH Index 2024 (volume + waste)",
    "ASCO QOPI 2024 (oncology PA volume)",
    "KFF Medicare Advantage 2024 (overturn rate)",
    "CMS Federal Register CMS-0057-F · 89 FR 8758",
    "Anthropic-enterprise partnership (Nov 4 2024)",
    "the partner 10-K 2024 (channel reach)",
    "NCCN BINV-N v3.2026 (clinical guidelines)",
    "AWS Bedrock pricing (May 2026)",
    "ClinCase internal verified llm_invocations table · case_8f4ad9c2 (May 5 2026)",
  ];

  window.CLINCASE_ABOUT = {
    HERO_KPIS,
    PROBLEM_FACTS,
    AGENTS,
    INTAKE_INPUTS,
    LAYERS,
    STRATEGIC_FIT,
    COMPLIANCE,
    TEAM,
    THE_ASK,
    SOURCES,
  };
})();
