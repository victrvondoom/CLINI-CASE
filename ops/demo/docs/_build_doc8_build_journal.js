/* ============================================================
   DOC 8 — How We Built ClinCase From Scratch (build journal)
   ============================================================ */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber,
} = require('docx');

const OUT = path.join(__dirname, 'ClinCase_08_How_We_Built_It.docx');
const PAGE = { width: 11906, height: 16838 };
const MARGIN = { top: 1440, right: 1200, bottom: 1440, left: 1200 };
const CONTENT_W = 9506;
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 }, children: [new TextRun({ text: t, bold: true, size: 32, color: '0F172A' })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, bold: true, size: 26, color: '1E293B' })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 80 }, children: [new TextRun({ text: t, bold: true, size: 22, color: '4F46E5' })] });
const PARA = (t, opts = {}) => new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: t, size: 22, ...opts })] });
const BULLET = (t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: t, size: 22 })] });
const PB = () => new Paragraph({ children: [new PageBreak()] });
const SPACER = () => new Paragraph({ spacing: { after: 100 }, children: [new TextRun('')] });

const CALLOUT = (label, body, accent = '4F46E5', bg = 'EEF2FF') => new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: [CONTENT_W],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: { style: BorderStyle.SINGLE, size: 16, color: accent }, bottom: BORDER, left: BORDER, right: BORDER },
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill: bg, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 200, right: 200 },
      children: [
        new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: label, bold: true, color: accent, size: 20 })] }),
        new Paragraph({ children: [new TextRun({ text: body, size: 22 })] }),
      ],
    })],
  })],
});

const TOOL = (name, role, why, alts) => [
  new Paragraph({ spacing: { before: 200, after: 50 }, children: [new TextRun({ text: name, bold: true, color: '4F46E5', size: 24 })] }),
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: 'Used for: ', bold: true, color: '0F172A', size: 21 }), new TextRun({ text: role, size: 21 })] }),
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: 'Why we chose it: ', bold: true, color: '047857', size: 21 }), new TextRun({ text: why, size: 21 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'What we considered instead: ', bold: true, color: 'D97706', size: 21 }), new TextRun({ text: alts, size: 21 })] }),
];

const PHASE = (label, dates, summary) => [
  new Paragraph({ spacing: { before: 240, after: 40 }, children: [new TextRun({ text: label, bold: true, color: '4F46E5', size: 26 })] }),
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: dates, italics: true, color: '64748B', size: 21 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: summary, size: 22 })] }),
];

const c = [];

// =============================================================
// COVER
// =============================================================
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: 'CLINCASE', bold: true, size: 56, color: '4F46E5' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'How We Built It — From Idea to Demo Day', size: 26, color: '475569' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: 'A complete build journal: every tool, every choice, every bug, every fix.', italics: true, size: 22, color: '64748B' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Document 8 of 8 · the 2026 hackathon', size: 22, color: '64748B' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Team AeroFyta · April 4 — May 7, 2026', size: 22, color: '64748B' })] }));
c.push(PB());

// =============================================================
// INTRO
// =============================================================
c.push(H1('How to read this build journal'));
c.push(PARA('This document tells the whole story. It is honest — including the bugs, the wrong turns, the late-night fixes. We wrote it so anyone can understand exactly how a 4-person student team shipped an enterprise-grade healthcare AI system in about 4 weeks.'));
c.push(SPACER());

c.push(PARA('What you will find:'));
c.push(BULLET('Phase-by-phase timeline (April 4 → May 7)'));
c.push(BULLET('Every tool we used, why we chose it, and what alternatives we considered'));
c.push(BULLET('The 6 systemic bugs we hit and how we fixed them'));
c.push(BULLET('The 24-hour MVP sprint diary'));
c.push(BULLET('Lessons learned that we would tell our past selves'));
c.push(SPACER());

c.push(CALLOUT('What this is NOT',
  'This is not a tutorial. We are not teaching you how to build a healthcare AI system. We are documenting the actual decisions our team made, the tools we used, and what we would do differently. If you read this and ask "but why did you not also do X?" — the answer is usually "we did not have time" or "we did not know about X yet". Engineering is full of constraints.',
  'D97706', 'FEF3C7'));
c.push(PB());

// =============================================================
// PHASE 1 — IDEA + STRATEGY
// =============================================================
c.push(H1('Part 1 — The Timeline (Phase by Phase)'));

c.push(...PHASE('Phase 1 · The Idea Discovery',
  'April 4 — April 12, 2026 · ~9 days',
  'We started by reading every the 2026 hackathon industry theme. Eight verticals, 40+ themes total. We looked for the one with: (a) the largest dollar problem, (b) the most regulatory tailwind, and (c) the most underserved technical niche. Healthcare → Prior Authorisation Automation hit all three.'));

c.push(H3('What we did this phase'));
c.push(BULLET('Read all four official partner PDFs (brochure, themes, agent builder, orientation)'));
c.push(BULLET('Researched the prior auth market — CAQH 2024 reports, AMA surveys, KFF reports'));
c.push(BULLET('Found the CMS-0057-F mandate — Jan 2027 enforcement was the regulatory tailwind'));
c.push(BULLET('Identified the gap — most "AI for prior auth" startups are payer-side, not provider-side'));
c.push(BULLET('Submitted our idea on the Superset platform on April 12'));
c.push(SPACER());

c.push(H3('Tools used in this phase'));
c.push(BULLET('Google Search + research aggregators (CAQH, AMA, KFF reports)'));
c.push(BULLET('Markdown for the initial proposal draft'));
c.push(BULLET('Notion for team brainstorming'));
c.push(BULLET('the partner Superset platform for idea submission'));
c.push(SPACER());

c.push(CALLOUT('Decision rationale: Why oncology specifically',
  'Oncology has the highest-stakes prior auth (cancer drugs are $1,500+/month), the most complex policies (NCCN updates several times a year), the worst delays (14-day average), and the highest growth (38% YoY oncology PA volume). If we won oncology, the same architecture would extend to GLP-1, MS, transplant later. The choice was: dominate one niche, then expand.',
  '047857', 'F0FDF4'));
c.push(PB());

// =============================================================
c.push(...PHASE('Phase 2 · Tooling and Architecture Research',
  'April 13 — April 22, 2026 · ~10 days',
  'Once the idea was locked, we researched the technical stack. Not what we knew already — what would actually work for healthcare AI at enterprise scale. We had to learn FHIR R4, Bedrock, LangGraph, AWS Q Business. None of us had built any of these before.'));

c.push(H3('What we learned in this phase'));
c.push(BULLET('FHIR R4 — the standard format for hospital data; we read the entire R4 spec for Observation, Condition, Bundle resources'));
c.push(BULLET('AWS Bedrock — the AWS-hosted LLM service; how to call it via boto3'));
c.push(BULLET('LangGraph — the multi-agent DAG library; we built 3 toy projects to learn the API'));
c.push(BULLET('CMS-0057-F — read the full Federal Register text (107 pages)'));
c.push(BULLET('NCCN guidelines — sampled BINV (breast cancer) to understand citation format'));
c.push(BULLET('the payer organization vertical — what they sell, who they sell to'));
c.push(BULLET('Anthropic-enterprise November 4, 2024 partnership announcement'));
c.push(SPACER());

c.push(H3('Architectural decisions made in this phase'));
c.push(BULLET('7 parent agents (not 1, not 15) — one for each major step in the pipeline'));
c.push(BULLET('22 sub-agents — split each parent into 3-4 specialists'));
c.push(BULLET('6 layers (Data, Agent, Runtime, Gateway, Surface, Ops) — bounded responsibility'));
c.push(BULLET('Pydantic v2 for every input/output — type safety at every boundary'));
c.push(BULLET('System prompts in .txt files (not in code) — editable without redeploy'));
c.push(BULLET('Hash-chained audit ledger — required for CMS-0057-F § IV.A'));
c.push(SPACER());
c.push(PB());

// =============================================================
c.push(...PHASE('Phase 3 · The Agent Builder Challenge',
  'April 23, 2026 · 45 minutes',
  'the partner required all teams to complete a 45-minute Agent Builder Challenge on the Superset platform. We had to design a workflow with input/LLM/router/condition/branch/loop nodes from one shared workstation. This was a stress test of how clearly we could think about agent design under time pressure.'));

c.push(BULLET('We modeled a simplified prior-auth flow: input (FHIR) → classifier (route by drug-class) → LLM step (necessity check) → condition (verdict) → output formatter'));
c.push(BULLET('Used Custom Code nodes for deterministic verdict synthesis'));
c.push(BULLET('Wrote rationale answers for: API selection logic, confidence-based branching, trade-off handling'));
c.push(BULLET('Submitted with 8 minutes remaining'));
c.push(SPACER());

c.push(CALLOUT('What we learned',
  'The Agent Builder Challenge is testing system-design intuition — not just LLM knowledge. The judges look for: clear logic flow, smart use of conditions, defensible trade-offs. Our 7-agent DAG architecture (already designed in Phase 2) made this section easy.',
  '4F46E5', 'EEF2FF'));
c.push(PB());

// =============================================================
c.push(...PHASE('Phase 4 · Architecture Spec + Pre-Build Setup',
  'April 24 — May 4, 2026 · ~11 days',
  'We could not start coding the MVP until May 5 (the 24-hour build window at Pune). But we used the 11 pre-build days to write the full architectural specification — every Pydantic schema, every database table, every API endpoint. When the 24-hour clock started, we were ready to type, not think.'));

c.push(H3('What we wrote in this phase'));
c.push(BULLET('PROPOSAL.md — 1,392-line full engineering spec (single source of truth)'));
c.push(BULLET('CLINCASE_PROPOSAL.md — 597-line strategic proposal (for AI uploads)'));
c.push(BULLET('CLAUDE.md — coding conventions for AI-assisted dev (Python 3.11+, Pydantic v2, ruff, mypy strict)'));
c.push(BULLET('All 22 system prompts as .txt files'));
c.push(BULLET('Database schema — 12 tables, 36 indexes, 8 RLS policies, 4 triggers'));
c.push(BULLET('API contract — 30+ endpoints with OpenAPI specs'));
c.push(BULLET('Frontend route structure — 20 pages, 36 components'));
c.push(SPACER());

c.push(H3('Tools we used in this phase'));
c.push(BULLET('Markdown for all spec docs'));
c.push(BULLET('Mermaid for architecture diagrams'));
c.push(BULLET('GitHub for version control (started fresh repo on April 24)'));
c.push(BULLET('Claude Design — for visual prototyping (we hit credit limits twice; learned to use it sparingly)'));
c.push(BULLET('Excalidraw — quick whiteboard-style architecture sketches'));
c.push(SPACER());

c.push(CALLOUT('Why we wrote 1,392 lines BEFORE coding',
  'A 24-hour build is impossible if you spend 6 hours arguing about architecture. We pre-decided: 7 agents, 22 sub-agents, 12 tables, 30+ endpoints. When the clock started May 5, every team member knew exactly which files to write. No debate, no stand-ups, just typing.',
  '047857', 'F0FDF4'));
c.push(PB());

// =============================================================
c.push(...PHASE('Phase 5 · The 24-Hour MVP Sprint',
  'May 5 — May 6, 2026 · 24 hours straight',
  'This is what the hackathon was really judging. We built the full system in 24 continuous hours at the venue in Pune.'));

c.push(H3('Hour-by-hour breakdown (the actual diary)'));
c.push(SPACER());

c.push(H3('Hour 0-2 (May 5 morning) — Repo + scaffolding'));
c.push(BULLET('Cloned the pre-built skeleton from GitHub'));
c.push(BULLET('docker-compose up — Postgres + Redis running locally'));
c.push(BULLET('Ran initial migrations — all 12 tables created with RLS policies'));
c.push(BULLET('Smoke-tested FastAPI boots, /healthz returns 200'));
c.push(SPACER());

c.push(H3('Hour 2-8 — Agent framework + 7 parents'));
c.push(BULLET('Implemented framework/agent.py base class'));
c.push(BULLET('Built Clinical Extractor (orchestrator + 3 sub-agents)'));
c.push(BULLET('Built Policy Retriever (orchestrator + 4 sub-agents)'));
c.push(BULLET('Built Necessity Reasoner (orchestrator + 3 sub-agents) — hardest one'));
c.push(BULLET('Built Decision Composer (orchestrator + 3 sub-agents)'));
c.push(BULLET('Built Denial Forecaster (orchestrator + 3 sub-agents)'));
c.push(BULLET('Built Appeals Drafter (orchestrator + 3 sub-agents)'));
c.push(BULLET('Built Patient Communicator (orchestrator + 3 sub-agents)'));
c.push(SPACER());

c.push(H3('Hour 8-12 — LangGraph wiring + worker'));
c.push(BULLET('Wired all 7 agents into one DAG via app/graph/build.py'));
c.push(BULLET('Implemented case_runner worker — polls case_jobs queue, runs DAG'));
c.push(BULLET('First end-to-end run on demo case ' + 'failed' + ' — caught 3 schema bugs'));
c.push(BULLET('After fixes, first APPROVE verdict produced at Hour 11:30'));
c.push(SPACER());

c.push(H3('Hour 12-16 — Frontend MVP'));
c.push(BULLET('Vite + React + TypeScript scaffold'));
c.push(BULLET('AppShell + Sidenav + Top Bar'));
c.push(BULLET('Dashboard route with KPI tiles'));
c.push(BULLET('Cases list + Case Detail routes'));
c.push(BULLET('SSE client for live agent trace streaming'));
c.push(BULLET('CitationChip + DecisionBadge components'));
c.push(SPACER());

c.push(H3('Hour 16-20 — Compliance + ROI features'));
c.push(BULLET('Built /compliance route (CMS-0057-F scorecard)'));
c.push(BULLET('Built /roi route (member-count slider, savings calculation)'));
c.push(BULLET('Built /architecture route (live 6-layer descriptor)'));
c.push(BULLET('Built /agents route (5-agent DAG meta-view)'));
c.push(BULLET('Hash-chain triggers in Postgres for audit ledger'));
c.push(SPACER());

c.push(H3('Hour 20-24 — Polish + standalone showcase'));
c.push(BULLET('Built standalone HTML showcase (zero-backend version)'));
c.push(BULLET('Tweaks panel for live demo control'));
c.push(BULLET('Pre-staged 3 demo fixtures (APPROVE, REFER, DENY)'));
c.push(BULLET('Final smoke test — all 13 routes render, no console errors'));
c.push(BULLET('Committed final code at Hour 23:42'));
c.push(SPACER());

c.push(CALLOUT('What broke during the 24 hours',
  '6 systemic bugs hit us during Hour 8-12. JSON truncation in 5 agents (max_tokens too low), grader silent failures (max_tokens 400 way too low for 5-field score), schema mismatch in appeal_path_recommender (LLM produced flat JSON for nested schema), case-detail route regex too narrow (only matched AUTH-* IDs). We fixed all 6 in a single bulk pass and shipped. Detailed bug log is in Part 4 below.',
  'BE123C', 'FEF2F2'));
c.push(PB());

// =============================================================
c.push(...PHASE('Phase 6 · Polish, Materials, and Demo Prep',
  'May 6 — May 7, 2026 · ~36 hours',
  'After MVP completion, we shifted from build mode to "win the demo" mode. We built the printed kit, recorded the standalone showcase, hosted it on clincase-demo-26697.s3-website-us-east-1.amazonaws.com, and drilled Q&A.'));

c.push(H3('What we built in this phase'));
c.push(BULLET('Architecture Poster (A3 portrait, foam-board mounted) — 6-layer + 7-agent topology'));
c.push(BULLET('Sample Artifacts Booklet (A4 6 pages stapled) — real APPROVE / REFER / DENY artifacts'));
c.push(BULLET('Compliance & Trust One-Pager (A4 double-sided) — CMS-0057-F § IV mapping'));
c.push(BULLET('ROI + TAM A3 fold (bi-fold) — pricing tiers, market hierarchy, 3-year roadmap'));
c.push(BULLET('Brochure repurpose plan from existing AeroFyta template (with image generation prompts)'));
c.push(BULLET('ClinCase logo SVG + 5 PNG sizes (256, 512, 1024, 2048, 4096 px, transparent)'));
c.push(BULLET('Hosted standalone at clincase-demo-26697.s3-website-us-east-1.amazonaws.com (custom domain)'));
c.push(BULLET('QR code for the live demo (encoded into all printed materials)'));
c.push(BULLET('8 detailed Word documents (this set) — glossary, story, Q&A, code, pitch lines, AWS, competitive, build journal'));
c.push(SPACER());

c.push(H3('Tools used in this phase'));
c.push(BULLET('HTML + CSS for printable materials (no design software needed — just Chrome\'s "Print to PDF")'));
c.push(BULLET('Python segno library for QR code generation (SVG output)'));
c.push(BULLET('Python cairosvg for SVG → PNG conversion (multiple sizes, transparent)'));
c.push(BULLET('Node.js docx library for the 8 Word documents'));
c.push(BULLET('Cloudflare Pages for hosting the standalone (deployed via drag-drop)'));
c.push(BULLET('DNS CNAME at the domain registrar to point clincase-demo-26697.s3-website-us-east-1.amazonaws.com'));
c.push(BULLET('Local print shop in Pune for premium card stock + foam-board mounting'));
c.push(PB());

// =============================================================
// PART 2 — TOOL BY TOOL
// =============================================================
c.push(H1('Part 2 — Every Tool We Used, and Why'));

c.push(H2('AI / LLM tools'));
c.push(...TOOL('Claude Code (Anthropic CLI)',
  'AI-assisted coding throughout the build. Claude wrote ~70% of the boilerplate, we wrote the architecture and the prompts.',
  'Claude is the strongest coding model available. Sonnet 4.6 produced clean Python, valid Pydantic schemas, well-formatted React. We treated Claude as a pair-programmer, not a magic answer machine.',
  'GitHub Copilot — too auto-complete-y, not strategic. ChatGPT Codex — older, weaker code. Cursor — uses Claude under the hood anyway.'));

c.push(...TOOL('Claude Sonnet 4.6 (the LLM in ClinCase itself)',
  'Powers all 7 parent agents and most sub-agents. Used via AWS Bedrock in production.',
  'Best medical reasoning per dollar. the partner standardised on Anthropic in their November 2024 partnership.',
  'GPT-4 (no comparable enterprise alignment), Gemini Pro (not BAA-covered), Llama 3.1 (lower quality on policy reasoning).'));

c.push(...TOOL('Claude Haiku 4.5',
  'Powers the Grader (scores every agent output) and lightweight sub-agents.',
  '5x cheaper than Sonnet. Fast enough that we can grade every output without cost blowing up.',
  'Smaller open models would self-host but add ops surface we did not have time for.'));

c.push(...TOOL('Claude Design',
  'Visual prototyping for the standalone HTML showcase before we built the React app.',
  'Generates real working HTML/JSX with brand-tuned styling. Saved us 8+ hours of UI iteration.',
  'Figma — too slow for our timeline. v0 by Vercel — comparable but less brand-tuned. Plain hand-coded CSS — we eventually did this anyway.'));

c.push(SPACER());
c.push(H2('Backend tools'));
c.push(...TOOL('Python 3.11+',
  'Backend language for all 7 agents, framework, API.',
  'Standard for AI/ML. Massive ecosystem. AsyncIO is mature in 3.11. We require 3.11+ for native exception groups and improved type system.',
  'Java (Spring Boot) — alienates the Python AI ecosystem. TypeScript backend — would force us to maintain Pydantic-equivalent schemas in TS.'));

c.push(...TOOL('FastAPI',
  'Web framework for the API.',
  'Async by default — handles 60-second LLM calls without blocking. Auto-generated OpenAPI docs from Pydantic. Native SSE support.',
  'Flask (synchronous, would block), Django (too heavy for an API), Spring Boot (Java).'));

c.push(...TOOL('Pydantic v2',
  'Data validation for every agent input/output.',
  '5x faster than v1 (Rust-backed). Stricter validation. Catches malformed LLM output at the boundary, before it propagates.',
  'Marshmallow (older), attrs (no JSON serialization), raw dataclasses (no validation).'));

c.push(...TOOL('LangGraph',
  'Multi-agent DAG orchestration.',
  'De-facto standard for multi-agent flows in Python. Stateful, conditional branching, type-safe state via Pydantic.',
  'CrewAI (less mature, weak typing), AutoGen (better for chat than DAG), custom Python (would take 2 weeks of plumbing).'));

c.push(...TOOL('AsyncPG',
  'Async Postgres driver.',
  'Fastest Postgres driver for Python. Async-native. Connection pooling built in.',
  'psycopg2 (synchronous), psycopg3 (newer but smaller user base), SQLAlchemy ORM (overkill — we use raw SQL with type hints).'));

c.push(...TOOL('pytest + pytest-asyncio',
  'Testing framework. ~60 test files.',
  'Standard. Async support is first-class. Fixtures + parametrize give us per-agent contract tests cleanly.',
  'unittest (more verbose), nose (deprecated).'));

c.push(...TOOL('ruff',
  'Linting + formatting.',
  '100x faster than pylint. Single tool replaces black + isort + flake8 + bandit. Zero-config for most cases.',
  'flake8 + black + isort (slow, multiple tools).'));

c.push(...TOOL('mypy --strict',
  'Static type checking.',
  'Catches type errors before runtime. Mandatory on app/models/ (strictest module).',
  'pyright (faster, but mypy is the standard).'));

c.push(SPACER());
c.push(H2('Frontend tools'));
c.push(...TOOL('React 18',
  'UI framework.',
  'Largest hiring pool. Mature ecosystem. Concurrent rendering for SSE-heavy UI.',
  'Next.js (SSR not needed for our internal-tool style), Vue (smaller pool), Svelte (modern but smaller pool).'));

c.push(...TOOL('Vite 5',
  'Build tool / dev server.',
  'Hot reload in <100ms. Native ESM. Replaces webpack. Simpler config.',
  'webpack (slower), Parcel (less Vue/React-tuned), Bun (newer, riskier).'));

c.push(...TOOL('TypeScript (strict mode)',
  'Frontend language.',
  'Type safety = fewer "is this string a JSON object?" runtime errors. Strict mode catches everything.',
  'Plain JavaScript (we would catch errors at runtime, not commit time).'));

c.push(...TOOL('Tailwind CSS',
  'Styling system.',
  'Utility-first = fast iteration. Same brand tokens used across React app + standalone HTML showcase + printable materials.',
  'CSS-in-JS (runtime overhead), Material UI (heavyweight, hard to brand).'));

c.push(...TOOL('lucide-react',
  'Icon library.',
  '~1,500 icons, tree-shakable, modern style. We use ~50 of them.',
  'react-icons (multi-library, larger bundle), Heroicons (smaller set).'));

c.push(SPACER());
c.push(H2('Database tools'));
c.push(...TOOL('PostgreSQL 16',
  'Primary database.',
  'Row-level security for tenant isolation, JSONB for flexible agent outputs, ACID for audit chain integrity.',
  'MongoDB (no RLS at kernel level), DynamoDB (cross-item ACID hard).'));

c.push(...TOOL('AWS RDS for Postgres',
  'Managed Postgres in production.',
  'Backups, replication, security all handled by AWS. We focus on schema, not operations.',
  'Self-hosted Postgres on EC2 (more ops burden), Aurora MySQL (less RLS support).'));

c.push(SPACER());
c.push(H2('AWS services'));
c.push(BULLET('Bedrock — LLM hosting (Sonnet + Haiku) — see Doc 6 for full deep-dive'));
c.push(BULLET('Q Business — RAG over payer policies'));
c.push(BULLET('ECS Fargate — serverless container hosting'));
c.push(BULLET('RDS — managed Postgres'));
c.push(BULLET('S3 — FHIR archive + evidence packs'));
c.push(BULLET('KMS — encryption keys'));
c.push(BULLET('CloudWatch — logs + metrics + alarms'));
c.push(BULLET('ALB — public HTTPS endpoint'));
c.push(BULLET('VPC — private network with Bedrock VPC endpoints'));
c.push(BULLET('IAM — per-component roles, principle of least privilege'));
c.push(BULLET('Secrets Manager — DB passwords, API keys, JWT secrets'));
c.push(BULLET('SES (optional) — appeal letter email delivery'));

c.push(SPACER());
c.push(H2('Documentation + design tools'));
c.push(...TOOL('Markdown (everywhere)',
  'All proposal docs, README files, design decisions.',
  'Plain text, version-control-friendly, AI-uploadable.',
  'Word docs (binary, hard to diff), Notion (cloud-only).'));

c.push(...TOOL('HTML + CSS for printable materials',
  'Architecture Poster, Compliance one-pager, ROI fold, Sample Artifacts Booklet.',
  'Print-ready, brand-consistent, no design software required, opens in any browser, prints to PDF for the print shop.',
  'Adobe InDesign (not free, not familiar to us), Canva (limited fold/poster sizing).'));

c.push(...TOOL('Node.js docx library',
  'These 8 Word documents.',
  'Generates valid .docx files programmatically. Same content can be re-generated by editing JS, no manual Word editing needed.',
  'python-docx (works but Node has better ergonomics for this use case).'));

c.push(...TOOL('Python segno + cairosvg',
  'QR codes (segno → SVG) and ClinCase logo PNG export (cairosvg).',
  'Pure Python, no external system deps. SVG outputs are infinitely scalable; cairosvg renders to crisp PNG at any size.',
  'qrcode (PIL-based, less SVG-friendly), Inkscape CLI (heavy).'));

c.push(SPACER());
c.push(H2('Hosting / DevOps tools'));
c.push(...TOOL('GitHub',
  'Version control + CI/CD.',
  'Standard. GitHub Actions for tests on every push. Branch protection on main.',
  'GitLab (smaller community), Bitbucket.'));

c.push(...TOOL('Cloudflare Pages',
  'Hosts the standalone HTML showcase at clincase-demo-26697.s3-website-us-east-1.amazonaws.com.',
  'Free tier handles our traffic. Drag-drop deploy. Auto HTTPS via Cloudflare. Custom domain in 2 clicks.',
  'Netlify (also great), Vercel (also great), GitHub Pages (slower HTTPS, less polished).'));

c.push(...TOOL('Docker + docker-compose',
  'Local dev stack: Postgres + Redis + worker + API.',
  '`docker-compose up` boots the entire local environment in 5 minutes. Same containers ship to ECS Fargate.',
  'Vagrant (slower), Kubernetes locally (overkill).'));
c.push(PB());

// =============================================================
// PART 3 — KEY TECHNICAL DECISIONS
// =============================================================
c.push(H1('Part 3 — Key Technical Decisions'));

c.push(H2('Decision 1 — Pre-LLM PHI sanitisation (not post-output scrubbing)'));
c.push(PARA('Many "HIPAA-compliant AI" tools use AI to scrub PHI from LLM outputs. We rejected this — it is gambling. We strip PHI BEFORE the first LLM call.'));
c.push(BULLET('Why: structural impossibility of leak > policy promise'));
c.push(BULLET('Implementation: phi_sanitizer.py runs on every FHIR Bundle at ingestion'));
c.push(BULLET('Result: HIPAA-compliant by architecture, not by policy'));
c.push(SPACER());

c.push(H2('Decision 2 — Deterministic verdict synthesis (not LLM-as-judge)'));
c.push(PARA('Some teams let the LLM pick APPROVE/REFER/DENY directly. We rejected this.'));
c.push(BULLET('Why: reproducibility. Same input must produce same verdict, every time.'));
c.push(BULLET('Implementation: verdict_synthesizer.py is pure Python — 30 lines of if/else'));
c.push(BULLET('Result: when Sonnet 5 ships, our verdicts do not change'));
c.push(SPACER());

c.push(H2('Decision 3 — Per-criterion parallel fan-out (not single-prompt eval)'));
c.push(PARA('We considered: one big prompt asking the LLM to evaluate all 8 criteria at once.'));
c.push(BULLET('Why parallel: 8x faster, more accurate, per-criterion grader scores'));
c.push(BULLET('Implementation: evidence_matcher fired N times via asyncio.gather()'));
c.push(BULLET('Result: 60-second decisions instead of 5-minute decisions'));
c.push(SPACER());

c.push(H2('Decision 4 — Provider abstraction (LLMClient interface)'));
c.push(PARA('Three LLM providers wired in: Bedrock (production), Anthropic direct (fallback), OpenRouter (development).'));
c.push(BULLET('Why: vendor lock-in is the biggest risk for a 5-year project'));
c.push(BULLET('Implementation: LLMClient protocol class, 3 implementations'));
c.push(BULLET('Result: switch via env var. Bedrock outage = flip to Anthropic in 30 seconds'));
c.push(SPACER());

c.push(H2('Decision 5 — Hash chain in Postgres triggers (not in app code)'));
c.push(PARA('Hash chains in code are easy to bypass. Hash chains as DB triggers are not.'));
c.push(BULLET('Why: integrity is a database guarantee, not an app convention'));
c.push(BULLET('Implementation: BEFORE INSERT trigger computes SHA-256(prev_hash + payload)'));
c.push(BULLET('Result: tamper-evident audit by kernel constraint, not by hope'));
c.push(SPACER());

c.push(H2('Decision 6 — System prompts as .txt files (not in code)'));
c.push(PARA('Most LangChain tutorials embed prompts as Python strings. We rejected this.'));
c.push(BULLET('Why: prompts change more than code. Editing a prompt should not require redeploy.'));
c.push(BULLET('Implementation: backend/app/prompts/{agent}/{role}.txt loaded at agent init'));
c.push(BULLET('Result: prompt experiments without rebuilding containers'));
c.push(PB());

// =============================================================
// PART 4 — BUGS WE HIT AND FIXED
// =============================================================
c.push(H1('Part 4 — The 6 Systemic Bugs (and Their Fixes)'));
c.push(PARA('During the 24-hour MVP sprint and the post-build polish, we hit 6 systemic bugs. Each one taught us something. Here is the honest log.'));
c.push(SPACER());

c.push(H2('Bug 1 — JSON truncation in counter_evidence_finder'));
c.push(BULLET('Symptom: agent fails with "EOF while parsing JSON at line 5 column 16"'));
c.push(BULLET('Root cause: max_tokens too low (1500). Output was getting cut mid-sentence.'));
c.push(BULLET('Fix: Created SONNET_LONG_JSON spec with max_tokens=8000 for agents that produce large structured output'));
c.push(BULLET('Lesson: Default max_tokens (1500) was a footgun. We later bumped the global default to 3000.'));
c.push(SPACER());

c.push(H2('Bug 2 — Same JSON truncation in letter_composer'));
c.push(BULLET('Symptom: 600-word appeal letters truncated at the 4th paragraph'));
c.push(BULLET('Root cause: same as Bug 1, different agent'));
c.push(BULLET('Fix: switched to SONNET_LONG_JSON spec'));
c.push(BULLET('Lesson: when you fix a class of bug, search for ALL instances, not just the one you found'));
c.push(SPACER());

c.push(H2('Bug 3 — Schema mismatch in appeal_path_recommender'));
c.push(BULLET('Symptom: Pydantic validation error: "strategy.primary_angle: Field required"'));
c.push(BULLET('Root cause: prompt did not show the LLM the FULL nested JSON structure. LLM produced flat {"appeal_strategy": "...", "turn_probability": 0.78} instead of {"strategy": {"primary_angle": "...", ...}}'));
c.push(BULLET('Fix: rewrote prompt with explicit JSON structure example + critical field-name rules'));
c.push(BULLET('Lesson: never assume the LLM will infer your schema. Show it the exact shape, every time.'));
c.push(SPACER());

c.push(H2('Bug 4 — Grader silently truncating EVERY output'));
c.push(BULLET('Symptom: GraderScore JSON invalid, "EOF at line 5 column 16"'));
c.push(BULLET('Root cause: HAIKU_GRADER had max_tokens=400. GraderScore (4 floats + paragraph feedback) needs ~350-500 tokens. Truncating mid-feedback.'));
c.push(BULLET('Critical observation: this was firing on EVERY agent output. The grader was failing silently behind every other call.'));
c.push(BULLET('Fix: bumped HAIKU_GRADER max_tokens to 1500'));
c.push(BULLET('Lesson: small numbers compound. A bug in one shared component (the Grader) had affected all 22 agents.'));
c.push(SPACER());

c.push(H2('Bug 5 — Frontend case-detail route regex'));
c.push(BULLET('Symptom: navigating to /cases/case_8f4ad9c2 silently fell back to Dashboard'));
c.push(BULLET('Root cause: route regex was /^#\\/cases\\/(AUTH-.+)$/ — only matched AUTH- prefix. Demo fixtures use case_ prefix.'));
c.push(BULLET('Fix: broadened regex to /^#\\/cases\\/(.+)$/ with explicit exclusion of /cases/bulk-import'));
c.push(BULLET('Lesson: assumptions about ID format from one source bleed into routing code. Centralise ID validation.'));
c.push(SPACER());

c.push(H2('Bug 6 — Print preview "many sheets of paper"'));
c.push(BULLET('Symptom: A3 portrait architecture poster prints across 2 A4 pages'));
c.push(BULLET('Root cause: Chrome\'s print dialog defaulted to A4. Our @page rule said A3 portrait but the printer destination overrode.'));
c.push(BULLET('Fix: (a) added height: 394mm + overflow: hidden to clamp the page boundary, (b) documented "set Paper size to A3 in print dialog"'));
c.push(BULLET('Lesson: CSS @page rules are advisory, not authoritative. Always test the actual print, not just the screen.'));
c.push(SPACER());

c.push(CALLOUT('Pattern across all 6 bugs',
  'Five of the six were configuration/sizing bugs (max_tokens too low, A4 vs A3, AUTH-only regex). Only one was a real architectural mismatch (the prompt-vs-schema in Bug 3). This taught us: under time pressure, our code was usually right but our defaults were wrong. Spend more time on configuration audit, less on architecture re-thinking.',
  'D97706', 'FEF3C7'));
c.push(PB());

// =============================================================
// PART 5 — LESSONS LEARNED
// =============================================================
c.push(H1('Part 5 — Lessons We Learned (and what we would tell our past selves)'));

c.push(H2('Lesson 1 — Pre-build the spec, then sprint the code'));
c.push(PARA('We spent 11 days writing PROPOSAL.md before May 5. Some teammates thought this was wasteful — "we are not writing code". They were wrong. When the 24-hour clock started, every file already had a known shape, every endpoint had a known contract, every agent had a known prompt. We typed for 24 hours straight without arguing about architecture once.'));
c.push(SPACER());

c.push(H2('Lesson 2 — Test the LLM at the boundary, not in the middle'));
c.push(PARA('We started by trying to validate LLM outputs in agent business logic. This was wrong. The right place is at the schema boundary — Pydantic v2 with strict types, validated immediately on output. If the LLM produces invalid data, it fails before propagation. Saved us hours of debugging.'));
c.push(SPACER());

c.push(H2('Lesson 3 — Hash chains belong in the database, not in app code'));
c.push(PARA('We initially wrote the hash chain in Python — append a row, compute hash, save. This works until someone forgets to compute the hash on one code path. Moving the hash computation into a Postgres BEFORE INSERT trigger meant the chain was enforced by the kernel. Mistakes became impossible.'));
c.push(SPACER());

c.push(H2('Lesson 4 — Default tokens are footguns'));
c.push(PARA('Every LLM library has a default max_tokens — usually 1000-2000. Almost every healthcare AI output we cared about was bigger than that. Bumping defaults to 3000 saved us from 5 of the 6 bugs we hit. Our advice: explicitly set max_tokens for every agent. Never trust defaults.'));
c.push(SPACER());

c.push(H2('Lesson 5 — Grader runs on every output, so size it accordingly'));
c.push(PARA('We sized HAIKU_GRADER at 400 tokens, thinking "it just produces a score". Wrong — GraderScore has 4 floats + a paragraph feedback. At 400 tokens, the feedback was always cut off. Lesson: your grader is in the hot path. Size it for the realistic output, not the minimum.'));
c.push(SPACER());

c.push(H2('Lesson 6 — Print-ready means actually print it'));
c.push(PARA('We assumed our HTML printable docs would print correctly because they looked right on screen. Wrong. Chrome\'s print dialog overrode our @page rules. Always do a test print on the actual printer + paper combination. Then do another one. Then a third.'));
c.push(SPACER());

c.push(H2('Lesson 7 — Build the standalone first, the React app second'));
c.push(PARA('When Claude Design hit credit limits, we panicked. But the standalone HTML showcase turned out to be MORE valuable than the React app for the demo. Reason: it runs without a backend. If our Postgres had crashed on stage, we could have switched to clincase-demo-26697.s3-website-us-east-1.amazonaws.com in 2 seconds. The React app is the canonical product. The standalone is the insurance.'));
c.push(SPACER());

c.push(H2('Lesson 8 — Documentation is a multiplier, not overhead'));
c.push(PARA('We wrote 8 detailed Word documents (these). Some teams skip this — "judges will not read them". But the act of writing them forced us to articulate what we built, which exposed gaps we had not noticed. Plus, the documents become the leave-behind that judges study after the demo. They scored us on "demo quality" partly because we showed up with a full press kit.'));
c.push(SPACER());

c.push(H2('Lesson 9 — the partner alignment is not buzzword-stuffing, it is structural'));
c.push(PARA('We did not just say "Neuro-SAN AAOSA-aligned". We actually built it that way — bounded responsibility per agent, stateful continuity via LangGraph state, observability via SSE + audit ledger. When asked to defend the alignment, we point at the code, not at a slide. Real alignment beats branded alignment.'));
c.push(SPACER());

c.push(H2('Lesson 10 — Demo day is not when you present. It is when you defend.'));
c.push(PARA('The hackathon is 10 minutes of pitch + 15 minutes of Q&A. The Q&A is twice as long. We optimised for Q&A: 100 anticipated questions, 50 power lines, 60+ technical glossary terms, 30-second answers per question. When judges asked, we did not stutter. That is what separates winners from runner-ups.'));
c.push(PB());

// =============================================================
// PART 6 — WHAT WOULD WE DO DIFFERENTLY
// =============================================================
c.push(H1('Part 6 — What We Would Do Differently'));

c.push(H2('We would size all max_tokens explicitly from day 1'));
c.push(PARA('Five of our six bugs were max_tokens too low. Setting them explicitly per-agent in the spec phase would have saved us 6+ hours of debugging during the sprint.'));
c.push(SPACER());

c.push(H2('We would build the Grader first, not last'));
c.push(PARA('We added the Grader after agents were working. This meant we did not catch quality issues until the integration phase. Building the Grader first would have surfaced bad prompts on day 1, not day 5.'));
c.push(SPACER());

c.push(H2('We would write contract tests before agents'));
c.push(PARA('We wrote agent code first, contract tests second. Better to write the test (which is just "given this input, expect this output") FIRST, then implement until the test passes. Test-driven development at the agent level.'));
c.push(SPACER());

c.push(H2('We would version-pin all dependencies from day 1'));
c.push(PARA('We had a 30-minute debug session because Pydantic v2.6 behaved differently from v2.7. Pinning versions in requirements.txt from day 1 = no surprises.'));
c.push(SPACER());

c.push(H2('We would budget more time for the printable kit'));
c.push(PARA('We left the printed materials for the last 24 hours. Tighter than we would have liked. Next time: parallel-track the build (Days 1-23) with the print kit (Days 21-25), so the kit has 5 days, not 1.'));
c.push(SPACER());

c.push(H2('We would have hosted at clincase-demo-26697.s3-website-us-east-1.amazonaws.com from day 1'));
c.push(PARA('We hosted late. The QR codes on our printed materials assumed the URL would resolve. If the print shop had returned brochures before we hosted, the QR would have been a dead link for 12 hours. Lesson: register and host the domain first, build to it second.'));
c.push(PB());

// =============================================================
// PART 7 — TEAM ROLES DURING THE BUILD
// =============================================================
c.push(H1('Part 7 — Team Roles During the Build'));
c.push(PARA('We had 4 people. Each owned a quarter of the system end-to-end. No overlap, no gaps.'));
c.push(SPACER());

c.push(H3('Danish A. G. — Team Lead, Chief Architect'));
c.push(BULLET('Wrote PROPOSAL.md and the architectural spec'));
c.push(BULLET('Built the agent framework + 7 parent orchestrators'));
c.push(BULLET('Wired the LangGraph DAG'));
c.push(BULLET('Owned the AWS Bedrock integration'));
c.push(BULLET('On stage during demo, answers all architecture and AWS questions'));
c.push(SPACER());

c.push(H3('Preethi Sivachandran — Product & Demo Lead, UX'));
c.push(BULLET('Built the React frontend (20 routes, 36 components)'));
c.push(BULLET('Built the standalone HTML showcase'));
c.push(BULLET('Designed the Tweaks panel for live demo control'));
c.push(BULLET('Wrote pitch script, drilled Q&A'));
c.push(BULLET('On stage during demo, runs the demo + walks the UX'));
c.push(SPACER());

c.push(H3('Sanjay N — Backend & Compliance Engineer'));
c.push(BULLET('Built the Postgres schema + RLS policies'));
c.push(BULLET('Implemented the hash-chained audit ledger (Postgres triggers)'));
c.push(BULLET('Wrote PHI sanitizer + FHIR validator'));
c.push(BULLET('Implemented CMS-0057-F § IV mapping in code'));
c.push(BULLET('On stage during demo, answers all compliance and data questions'));
c.push(SPACER());

c.push(H3('Gayathri B — Healthcare Domain & Business Analyst'));
c.push(BULLET('Researched and sourced every market number (CAQH 2024, KFF, AMA, ASCO QOPI)'));
c.push(BULLET('Wrote the ROI calculator + business model'));
c.push(BULLET('Identified pilot targets (Tata Memorial, Apollo Hyderabad)'));
c.push(BULLET('Drafted competitive landscape analysis'));
c.push(BULLET('On stage during demo, answers all business and market questions'));
c.push(PB());

// =============================================================
// PART 8 — WHAT IS LEFT
// =============================================================
c.push(H1('Part 8 — What Is Still Left (Honestly)'));
c.push(PARA('We are not pretending we built a finished product in 24 hours. Here is what is real, what is mocked, and what is still ahead.'));
c.push(SPACER());

c.push(H2('Real and verified end-to-end'));
c.push(BULLET('All 7 parent agents fire correctly on demo fixtures'));
c.push(BULLET('All 22 sub-agents implemented and tested'));
c.push(BULLET('Full LangGraph DAG runs from FHIR input → verdict + citations + appeal letter'));
c.push(BULLET('Hash-chained audit ledger working with verify_chain() SQL function'));
c.push(BULLET('PHI sanitizer working on all FHIR Bundle inputs'));
c.push(BULLET('SSE streaming live to the React frontend'));
c.push(BULLET('98 LLM calls, $1.01 per case, 0 errors verified May 5, 2026'));
c.push(BULLET('Standalone HTML showcase live at clincase-demo-26697.s3-website-us-east-1.amazonaws.com'));
c.push(SPACER());

c.push(H2('Mocked / synthesised (clearly labeled in code)'));
c.push(BULLET('Demo data — Synthea-generated synthetic patients (no real PHI)'));
c.push(BULLET('Payer policies — sample subsets of real Aetna/UHC/NCCN policies, not the full corpus'));
c.push(BULLET('TriZetto submission — adapter exists but production payer connection requires the partner integration'));
c.push(BULLET('Cost numbers — based on Bedrock pricing as of May 2026; will adjust with rate changes'));
c.push(SPACER());

c.push(H2('Roadmap items (honest about scope)'));
c.push(BULLET('Adjacent verticals (UM, claim denials, RCM) — architecture supports, not yet built'));
c.push(BULLET('Multi-cloud (Azure, GCP) — the partner uses AWS today, multi-cloud is Year 2'));
c.push(BULLET('Multi-language patient communication — supported by architecture, demo is English-only'));
c.push(BULLET('FDA / regulatory clearance — we are clinical decision support (no FDA needed) but Series-A funds formal compliance attestation'));
c.push(BULLET('Real-time policy ingestion pipeline — currently manual; automation is next quarter'));
c.push(SPACER());

c.push(CALLOUT('Why this honesty matters',
  'Most hackathon teams overclaim and underdeliver. We do the opposite. By telling judges exactly what is real (a lot) and what is mocked (a little), we earn credibility that "everything works perfectly" pitches do not. When the verdict comes back showing we won, this honesty was part of why.',
  '4F46E5', 'EEF2FF'));
c.push(PB());

// =============================================================
// CLOSING
// =============================================================
c.push(H1('Closing — The 25-Day Build, In One Paragraph'));
c.push(PARA('We started with no code on April 4. We submitted our idea on April 12. We ran the Agent Builder Challenge on April 23. We pre-wrote 1,392 lines of architectural spec by May 4. We built the working MVP in 24 hours on May 5. We polished, hosted, printed materials, and recorded videos through May 6-7. We arrived on demo day with a working system, a press-kit-quality leave-behind, and 8 detailed documentation files. The architecture is the moat. The team is the engine. the enterprise stack is the distribution. The 25 days were a sprint, but the next 5 years are the marathon.'));
c.push(SPACER());

c.push(CALLOUT('Final advice for any future student team',
  '(1) Pre-write your spec. The 24-hour build is faster if you spent 11 days planning. (2) Test at the boundary. Pydantic at every interface saves debugging time. (3) Default settings are footguns. Audit every max_tokens, every timeout, every retry budget. (4) Documentation is a multiplier, not overhead. The 8 documents we wrote helped us as much as they helped the judges. (5) Demo day is Q&A day. Memorise lines, not slides.',
  '047857', 'F0FDF4'));
c.push(SPACER());

c.push(PARA('— Team AeroFyta', { italics: true, color: '64748B' }));
c.push(PARA('Danish A. G. · Preethi Sivachandran · Sanjay N · Gayathri B', { italics: true, color: '64748B' }));
c.push(PARA('the 2026 hackathon · Pune · May 7, 2026', { italics: true, color: '64748B' }));

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, font: 'Calibri', color: '0F172A' }, paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, font: 'Calibri', color: '1E293B' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, font: 'Calibri', color: '4F46E5' }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: PAGE, margin: MARGIN } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'ClinCase · How We Built It · Doc 8 of 8', size: 18, color: '94A3B8' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', size: 18, color: '94A3B8' }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '94A3B8' }), new TextRun({ text: ' · Team AeroFyta · Build journal April 4 — May 7, 2026', size: 18, color: '94A3B8' })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('Wrote', OUT, '(' + buf.length + ' bytes)'); });
