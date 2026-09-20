/* ============================================================
   CLINCASE — WINNING PITCH DECK · 18 slides · 16:9 widescreen
   For the 2026 hackathon · May 7, 2026
   ============================================================ */
const PPTXGenJS = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const pres = new PPTXGenJS();
pres.layout = 'LAYOUT_WIDE';                  // 13.333 × 7.5 inches
pres.author = 'Team AeroFyta';
pres.company = 'ClinCase';
pres.title = 'ClinCase · the 2026 hackathon';

// =============================================================
// COLOR PALETTE — ClinCase brand, "Midnight Executive" variant
// =============================================================
const C = {
  navy:    '0F172A',    // dark sections, hero backdrops (60-70% dominant)
  indigo:  '4F46E5',    // brand primary, callouts, accents
  cyan:    '0891B2',    // brand secondary, highlights, citations
  white:   'FFFFFF',
  light:   'F8FAFC',    // light section backgrounds
  surface: 'F1F5F9',    // card backgrounds on light slides
  border:  'E2E8F0',
  textMuted: '64748B',
  textBody:  '334155',
  textInk:   '0F172A',
  green:   '047857',    // positive stats, savings
  amber:   'D97706',    // warnings, the partner amber
  red:     'BE123C',    // problem urgency
  violet:  '7C3AED',    // alt accent for innovation
  emerald: '10B981',    // alt success
};

// Fonts (PowerPoint built-ins)
const F = { head: 'Segoe UI', body: 'Segoe UI', mono: 'Consolas' };

// =============================================================
// HELPER FUNCTIONS
// =============================================================
function addPageNum(slide, n, total, dark = false) {
  slide.addText(`${String(n).padStart(2, '0')} / ${total}`, {
    x: 12.4, y: 7.15, w: 0.8, h: 0.25,
    fontSize: 10, fontFace: F.mono, color: dark ? '94A3B8' : '94A3B8',
    align: 'right', italic: false,
  });
}

function addBrandStrip(slide, dark = false) {
  // META — keep small so it doesn't compete with content; widen right box.
  slide.addText('CLINCASE', {
    x: 0.5, y: 0.25, w: 2, h: 0.3,
    fontSize: 12, fontFace: F.head, bold: true,
    color: dark ? C.cyan : C.indigo, charSpacing: 4,
  });
  slide.addText('the hackathon · 2026', {
    x: 9.5, y: 0.25, w: 3.4, h: 0.3,
    fontSize: 10, fontFace: F.mono,
    color: dark ? '94A3B8' : C.textMuted,
    align: 'right', charSpacing: 1,
  });
}

function addSourceFooter(slide, sources, dark = false) {
  slide.addText(`Sources: ${sources}`, {
    x: 0.5, y: 7.0, w: 11.5, h: 0.4,
    fontSize: 11, fontFace: F.mono, italic: true,
    color: dark ? '64748B' : C.textMuted,
    align: 'left', charSpacing: 0.5,
  });
}

// Background helpers
function darkBackground(slide) {
  slide.background = { color: C.navy };
  // Subtle accent shape top-right (gradient circle)
  slide.addShape('ellipse', {
    x: 11, y: -1, w: 4, h: 4,
    fill: { color: C.indigo, transparency: 80 },
    line: { type: 'none' },
  });
  slide.addShape('ellipse', {
    x: 12, y: 5, w: 3, h: 3,
    fill: { color: C.cyan, transparency: 85 },
    line: { type: 'none' },
  });
}

function lightBackground(slide) {
  slide.background = { color: C.white };
  // Subtle accent strip on left
  slide.addShape('rect', {
    x: 0, y: 0, w: 0.15, h: 7.5,
    fill: { color: C.indigo },
    line: { type: 'none' },
  });
}

// =============================================================
// SLIDE 1 — COVER
// =============================================================
{
  const s = pres.addSlide();
  darkBackground(s);

  // Eyebrow
  s.addText('THE 2026 HACKATHON · NATIONAL FINALS', {
    x: 0.5, y: 1.2, w: 12, h: 0.4,
    fontSize: 14, fontFace: F.mono, color: C.cyan,
    charSpacing: 6, bold: true,
  });

  // Main title
  s.addText('CLINCASE', {
    x: 0.5, y: 1.7, w: 12, h: 1.6,
    fontSize: 96, fontFace: F.head, bold: true,
    color: C.white, charSpacing: 2,
  });

  // Tagline
  s.addText('The auditable AI copilot for oncology prior authorization.', {
    x: 0.5, y: 3.4, w: 12, h: 0.8,
    fontSize: 28, fontFace: F.head, italic: true,
    color: 'CBD5E1',
  });

  // Tagline subline (gradient-style emphasis)
  s.addText([
    { text: 'Verify clinical. ', options: { color: C.cyan, bold: true } },
    { text: 'Cite policy. ', options: { color: 'A78BFA', bold: true } },
    { text: 'Decide in 60 seconds.', options: { color: C.white, bold: true } },
  ], {
    x: 0.5, y: 4.2, w: 12, h: 0.6,
    fontSize: 22, fontFace: F.head,
  });

  // Divider line
  s.addShape('rect', {
    x: 0.5, y: 5.2, w: 1.2, h: 0.04,
    fill: { color: C.cyan }, line: { type: 'none' },
  });

  // Team
  s.addText('Team AeroFyta', {
    x: 0.5, y: 5.4, w: 12, h: 0.4,
    fontSize: 20, fontFace: F.head, bold: true, color: C.white,
  });
  s.addText('Danish A. G. (Lead) · Preethi Sivachandran · Sanjay N · Gayathri B', {
    x: 0.5, y: 5.85, w: 12, h: 0.35,
    fontSize: 16, fontFace: F.body, color: '94A3B8',
  });
  s.addText('Chennai Institute of Technology · 2027 Engineering · Pune · May 7, 2026', {
    x: 0.5, y: 6.2, w: 12, h: 0.35,
    fontSize: 14, fontFace: F.mono, color: '64748B', italic: true,
  });
}

// =============================================================
// SLIDE 2 — PROBLEM HOOK
// =============================================================
{
  const s = pres.addSlide();
  darkBackground(s);
  addBrandStrip(s, true);

  // Eyebrow
  s.addText('1 · THE PROBLEM', {
    x: 0.5, y: 1.0, w: 12, h: 0.4,
    fontSize: 16, fontFace: F.mono, color: C.red,
    charSpacing: 6, bold: true,
  });

  // The hook number
  s.addText('Every 2 seconds.', {
    x: 0.5, y: 1.7, w: 12, h: 1.8,
    fontSize: 96, fontFace: F.head, bold: true,
    color: C.white, italic: false,
  });

  // The hook line
  s.addText('a prior authorization is filed in the United States.', {
    x: 0.5, y: 3.5, w: 12, h: 0.6,
    fontSize: 24, fontFace: F.head, color: '94A3B8',
  });

  // The consequence
  s.addText('A doctor waits. A patient delays. A diagnosis ages.', {
    x: 0.5, y: 4.4, w: 12, h: 0.5,
    fontSize: 22, fontFace: F.head, italic: true,
    color: C.cyan,
  });

  // The headline number callout
  s.addShape('rect', {
    x: 0.5, y: 5.4, w: 12, h: 1.0,
    fill: { color: C.red, transparency: 70 },
    line: { color: C.red, width: 2 },
  });
  s.addText([
    { text: '14 days', options: { fontSize: 32, bold: true, color: C.white } },
    { text: '   to a verdict.   ', options: { fontSize: 20, color: 'FCA5A5' } },
    { text: '$1,500', options: { fontSize: 32, bold: true, color: C.white } },
    { text: '   per case in admin labour.   ', options: { fontSize: 20, color: 'FCA5A5' } },
    { text: '600M', options: { fontSize: 32, bold: true, color: C.white } },
    { text: '   PAs/year.', options: { fontSize: 20, color: 'FCA5A5' } },
  ], {
    x: 0.7, y: 5.55, w: 11.6, h: 0.7,
    fontFace: F.head, valign: 'middle',
  });

  addSourceFooter(s, 'CAQH Index 2024 · AMA Prior Auth Survey 2024', true);
  addPageNum(s, 2, 20, true);
}

// =============================================================
// SLIDE 3 — PROBLEM NUMBERS
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s, false);

  // Section header
  s.addText('1 · PROBLEM STATEMENT', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('The cost of broken prior authorization', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 36, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('Four numbers that explain why CMS-0057-F mandated this be solved by January 2027.', {
    x: 0.5, y: 1.95, w: 12, h: 0.5,
    fontSize: 18, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // 4 big stat tiles in a 2×2 grid
  const stats = [
    { v: '$30B', lbl: 'annual US prior-auth admin waste', src: 'CAQH 2024', color: C.red },
    { v: '94%',  lbl: 'of physicians say PA delays patient care', src: 'AMA 2024', color: C.amber },
    { v: '80.7%', lbl: 'of appealed Medicare-Advantage denials are overturned', src: 'KFF 2024', color: C.green },
    { v: '38%',  lbl: 'YoY growth in oncology PA volume', src: 'ASCO QOPI 2024', color: C.indigo },
  ];

  const tw = 5.8, th = 2.05;
  const xs = [0.5, 6.85];
  const ys = [2.7, 4.85];

  stats.forEach((stat, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = xs[col], y = ys[row];

    // Card background
    s.addShape('rect', {
      x, y, w: tw, h: th,
      fill: { color: C.white },
      line: { color: C.border, width: 1 },
    });
    // Top accent stripe
    s.addShape('rect', {
      x, y, w: tw, h: 0.08,
      fill: { color: stat.color }, line: { type: 'none' },
    });

    // Big number
    s.addText(stat.v, {
      x: x + 0.25, y: y + 0.18, w: tw - 0.5, h: 1.1,
      fontSize: 64, fontFace: F.head, bold: true,
      color: stat.color, charSpacing: -2,
    });
    // Label
    s.addText(stat.lbl, {
      x: x + 0.25, y: y + 1.3, w: tw - 0.5, h: 0.5,
      fontSize: 16, fontFace: F.body, color: C.textBody,
    });
    // Source mini
    s.addText('Source: ' + stat.src, {
      x: x + 0.25, y: y + th - 0.32, w: tw - 0.5, h: 0.25,
      fontSize: 11, fontFace: F.mono, color: C.textMuted, italic: true,
    });
  });

  addSourceFooter(s, 'CAQH Index 2024 · AMA Prior Auth Survey 2024 · KFF Medicare Advantage 2024 · ASCO QOPI 2024', false);
  addPageNum(s, 3, 20);
}

// =============================================================
// SLIDE 4 — SOLUTION
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('2 · SOLUTION DESCRIPTION', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('ClinCase turns 14-day fax-fights into 60-second verdicts.', {
    x: 0.5, y: 1.25, w: 12, h: 1.0,
    fontSize: 32, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('A 7-agent LangGraph DAG reads FHIR clinical data + payer policy, produces a citation-grounded verdict, and auto-drafts an NCCN-cited appeal letter when the case is denied — every claim bound to a stable pointer, every byte verifiable.', {
    x: 0.5, y: 2.35, w: 12, h: 1.2,
    fontSize: 18, fontFace: F.body, color: C.textBody,
  });

  // 5 differentiator chips
  const diffs = [
    { v: '7', lbl: 'Parent agents', sub: 'LangGraph DAG' },
    { v: '22', lbl: 'Sub-agents', sub: 'bounded competencies' },
    { v: '60s', lbl: 'End-to-end decision', sub: 'verified live' },
    { v: '$1.01', lbl: 'Real per-case cost', sub: 'vs $1,500 manual' },
    { v: '8/8', lbl: 'CMS-0057-F clauses', sub: '§ IV mapped' },
  ];

  const cw = 2.4, ch = 1.7;
  diffs.forEach((d, i) => {
    const x = 0.5 + i * 2.55, y = 4.1;
    s.addShape('rect', {
      x, y, w: cw, h: ch,
      fill: { color: C.surface },
      line: { color: C.border, width: 1 },
    });
    s.addShape('rect', {
      x, y, w: cw, h: 0.06,
      fill: { color: C.indigo }, line: { type: 'none' },
    });
    s.addText(d.v, {
      x: x + 0.2, y: y + 0.2, w: cw - 0.4, h: 0.7,
      fontSize: 36, fontFace: F.head, bold: true, color: C.indigo,
    });
    s.addText(d.lbl, {
      x: x + 0.2, y: y + 0.95, w: cw - 0.4, h: 0.35,
      fontSize: 14, fontFace: F.body, bold: true, color: C.textInk,
    });
    s.addText(d.sub, {
      x: x + 0.2, y: y + 1.3, w: cw - 0.4, h: 0.3,
      fontSize: 12, fontFace: F.mono, color: C.textMuted,
    });
  });

  // Five non-negotiables strip at bottom
  s.addShape('rect', {
    x: 0.5, y: 6.05, w: 12.3, h: 0.7,
    fill: { color: C.navy }, line: { type: 'none' },
  });
  s.addText([
    { text: '1. PROVIDER-SIDE   ', options: { color: C.cyan, bold: true } },
    { text: '·   ', options: { color: '64748B' } },
    { text: '2. FHIR-NATIVE   ', options: { color: C.cyan, bold: true } },
    { text: '·   ', options: { color: '64748B' } },
    { text: '3. CITATION-GROUNDED   ', options: { color: C.cyan, bold: true } },
    { text: '·   ', options: { color: '64748B' } },
    { text: '4. APPEALS AS SIDE-EFFECT   ', options: { color: C.cyan, bold: true } },
    { text: '·   ', options: { color: '64748B' } },
    { text: '5. AUDIT-FIRST', options: { color: C.cyan, bold: true } },
  ], {
    x: 0.5, y: 6.05, w: 12.3, h: 0.7,
    fontSize: 13, fontFace: F.mono, valign: 'middle', align: 'center', charSpacing: 1,
  });

  addPageNum(s, 4, 20);
}

// =============================================================
// SLIDE 5 — UNIQUENESS / INNOVATIVENESS
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('3 · UNIQUENESS / INNOVATIVENESS', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('What no one else does — on a multi-agent DAG.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 32, fontFace: F.head, bold: true, color: C.textInk,
  });

  // 6 USP cards in 2x3 grid
  const usps = [
    { num: '01', title: 'Provider-side, by design',
      desc: 'We work for the doctor, not the payer. Our incentive: overturning denials, not creating them.' },
    { num: '02', title: 'Citation-grounded by architecture',
      desc: 'Every claim binds to a FHIR resource ID + policy section. Cannot ship without citations.' },
    { num: '03', title: 'Appeals as side-effect',
      desc: 'When we deny, the NCCN-cited appeal letter is already drafted. Doctor never starts from blank.' },
    { num: '04', title: 'Hash-chained audit ledger',
      desc: 'SHA-256 chain in Postgres triggers. Tamper-evident by kernel constraint, not by hope.' },
    { num: '05', title: 'AMBIGUOUS as 1st-class verdict',
      desc: 'Three outcomes (APPROVE/REFER/DENY). Refuse to manufacture verdicts when evidence is missing.' },
    { num: '06', title: 'the partner-stack native',
      desc: 'Bedrock + Sonnet + MCP — exactly the Anthropic-enterprise Nov 4 2024 partnership stack.' },
  ];

  const cw2 = 4.05, ch2 = 1.65;
  usps.forEach((u, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * 4.18, y = 2.2 + row * 1.85;

    s.addShape('rect', {
      x, y, w: cw2, h: ch2,
      fill: { color: C.surface },
      line: { color: C.border, width: 1 },
    });
    // Number circle
    s.addShape('ellipse', {
      x: x + 0.2, y: y + 0.2, w: 0.6, h: 0.6,
      fill: { color: C.indigo }, line: { type: 'none' },
    });
    s.addText(u.num, {
      x: x + 0.2, y: y + 0.2, w: 0.6, h: 0.6,
      fontSize: 14, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle',
    });

    s.addText(u.title, {
      x: x + 0.95, y: y + 0.18, w: cw2 - 1.15, h: 0.42,
      fontSize: 16, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(u.desc, {
      x: x + 0.95, y: y + 0.65, w: cw2 - 1.15, h: 0.95,
      fontSize: 13, fontFace: F.body, color: C.textBody,
    });
  });

  addSourceFooter(s, 'ClinCase codebase, May 5 2026 audit · Anthropic-enterprise partnership announcement, Nov 4 2024', false);
  addPageNum(s, 5, 20);
}

// =============================================================
// SLIDE 6 — INNOVATION (the engineering differentiators)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('3 · INNOVATIONS WE BROUGHT', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Nine engineering decisions other teams will not make.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });

  // 3-column innovation grid (3 rows × 3 cols = 9 items)
  const innos = [
    { i: '⊕', title: 'Pre-LLM PHI sanitisation', desc: 'PHI never enters context. Structurally impossible to leak.' },
    { i: '◇', title: 'Deterministic verdict synthesis', desc: 'LLM produces evidence; pure Python produces verdict.' },
    { i: '⫶', title: 'Per-criterion parallel fan-out', desc: '8 criteria checked in parallel — 8× faster, more accurate.' },
    { i: '↔', title: 'Provider abstraction', desc: '3 LLM providers wired. Switch via env var. No lock-in.' },
    { i: '#', title: 'Hash chain in DB triggers', desc: 'Audit integrity enforced by Postgres, not by hope.' },
    { i: 'Σ', title: 'Reflection grading on Haiku', desc: 'Every output graded for ~$0.005, +20% accuracy gain.' },
    { i: '◑', title: 'AMBIGUOUS as 1st-class verdict', desc: 'Three outcomes. Refuse to fake confidence.' },
    { i: '✎', title: 'Pre-drafted appeal letters', desc: 'NCCN-cited appeal as DAG side-effect, not afterthought.' },
    { i: '◉', title: 'Live-toggle demo paths', desc: 'Tweaks panel switches APPROVE/REFER/DENY on stage.' },
  ];

  const iw = 4.0, ih = 1.5;
  innos.forEach((it, idx) => {
    const col = idx % 3, row = Math.floor(idx / 3);
    const x = 0.5 + col * 4.18, y = 2.15 + row * 1.65;

    s.addShape('rect', {
      x, y, w: iw, h: ih,
      fill: { color: C.white },
      line: { color: C.border, width: 1 },
    });
    // Icon glyph
    s.addText(it.i, {
      x: x + 0.18, y: y + 0.18, w: 0.6, h: 0.6,
      fontSize: 32, fontFace: F.head, bold: true,
      color: C.indigo, valign: 'middle', align: 'center',
    });
    s.addText(it.title, {
      x: x + 0.85, y: y + 0.18, w: iw - 1.05, h: 0.42,
      fontSize: 15, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(it.desc, {
      x: x + 0.85, y: y + 0.65, w: iw - 1.05, h: 0.75,
      fontSize: 12, fontFace: F.body, color: C.textBody,
    });
  });

  addSourceFooter(s, 'ClinCase source code (github.com/aerofyta/clincase) · Internal architecture spec PROPOSAL.md', false);
  addPageNum(s, 6, 20);
}

// =============================================================
// SLIDE 7 — TECHNICAL ARCHITECTURE OVERVIEW (6 layers)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('5 · TECHNICAL DESIGN & ARCHITECTURE', {
    x: 0.5, y: 0.85, w: 9, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  // AAOSA badge top-right — promotes the partner alignment from footer
  s.addShape('rect', {
    x: 9.7, y: 0.78, w: 3.1, h: 0.5,
    fill: { color: C.navy }, line: { color: C.cyan, width: 1 },
  });
  s.addText('NEURO-SAN AAOSA · ENTERPRISE', {
    x: 9.7, y: 0.78, w: 3.1, h: 0.5,
    fontSize: 11, fontFace: F.mono, bold: true, color: C.cyan,
    align: 'center', valign: 'middle', charSpacing: 3,
  });
  s.addText('Six layers. Concentric. One responsibility each.', {
    x: 0.5, y: 1.35, w: 12, h: 0.7,
    fontSize: 26, fontFace: F.head, bold: true, color: C.textInk,
  });

  // ===========================================================
  // CONCENTRIC RINGS (left half) — L1 innermost, L6 outermost
  // ===========================================================
  const cx = 3.4, cy = 4.4;          // ring centre — pulled up so ring
  // doesn't crash into the source footer at y=7.0.
  const radii = { L6: 2.1, L5: 1.75, L4: 1.4, L3: 1.05, L2: 0.7, L1: 0.35 };

  const ringSpec = [
    { num: 'L6', color: C.green,  outerR: radii.L6, innerR: radii.L5 },
    { num: 'L5', color: '0284C7', outerR: radii.L5, innerR: radii.L4 },
    { num: 'L4', color: C.cyan,   outerR: radii.L4, innerR: radii.L3 },
    { num: 'L3', color: C.indigo, outerR: radii.L3, innerR: radii.L2 },
    { num: 'L2', color: C.violet, outerR: radii.L2, innerR: radii.L1 },
    { num: 'L1', color: C.navy,   outerR: radii.L1, innerR: 0 },  // solid centre
  ];

  // Draw outer rings first; each subsequent (smaller) ellipse paints over
  // the inside of the previous one, leaving only the band visible.
  ringSpec.forEach((r) => {
    s.addShape('ellipse', {
      x: cx - r.outerR, y: cy - r.outerR,
      w: r.outerR * 2, h: r.outerR * 2,
      fill: { color: r.color }, line: { type: 'none' },
    });
  });

  // Ring labels — placed on the TOP of each band (12 o'clock), white text.
  ringSpec.forEach((r) => {
    const labelY = cy - r.outerR + (r.outerR - r.innerR - 0.32) / 2;
    s.addText(r.num, {
      x: cx - 0.4, y: labelY, w: 0.8, h: 0.32,
      fontSize: r.num === 'L1' ? 13 : 12,
      fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 1,
    });
  });

  // ===========================================================
  // RIGHT-HAND LEGEND — six rows, outer (L6) at the top
  // ===========================================================
  const legendX = 7.0, legendW = 5.85;
  const layerInfo = [
    { num: 'L6', name: 'Ops Plane',     color: C.green,  desc: 'Runbooks · evidence packs · compliance scorecard · ROI calc' },
    { num: 'L5', name: 'Surface Plane', color: '0284C7', desc: 'React + Vite + TS · SSE client · standalone HTML showcase' },
    { num: 'L4', name: 'Gateway Plane', color: C.cyan,   desc: 'LLMClient · Bedrock + Anthropic + OpenRouter · cost router' },
    { num: 'L3', name: 'Runtime Plane', color: C.indigo, desc: 'LangGraph DAG · FastAPI + SSE · case_runner · reflection' },
    { num: 'L2', name: 'Agent Plane',   color: C.violet, desc: '7 parents · 22 sub-agents · Pydantic v2 · GraderScore' },
    { num: 'L1', name: 'Data Plane',    color: C.navy,   desc: 'Postgres · audit_ledger · RLS · KMS · 10-yr retention' },
  ];

  const rowH = 0.62;
  layerInfo.forEach((row, i) => {
    const y = 2.15 + i * rowH;
    // Color chip
    s.addShape('rect', {
      x: legendX, y, w: 0.55, h: rowH - 0.06,
      fill: { color: row.color }, line: { type: 'none' },
    });
    s.addText(row.num, {
      x: legendX, y, w: 0.55, h: rowH - 0.06,
      fontSize: 12, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle',
    });
    // Name (bold) + description
    s.addText(row.name, {
      x: legendX + 0.7, y: y + 0.02, w: legendW - 0.7, h: 0.26,
      fontSize: 13, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(row.desc, {
      x: legendX + 0.7, y: y + 0.28, w: legendW - 0.7, h: 0.28,
      fontSize: 10.5, fontFace: F.mono, color: C.textBody,
    });
  });

  // Dependency caption (no arrow shape — keeps the ring as the focal visual)
  s.addText('Top-down dependency only · upper layers depend on lower, never the reverse.', {
    x: 0.5, y: 6.55, w: 12.3, h: 0.35,
    fontSize: 12, fontFace: F.body, italic: true, color: C.textMuted,
    align: 'center', valign: 'middle',
  });

  addSourceFooter(s, 'ClinCase architecture spec (PROPOSAL.md §6) · Neuro-SAN AAOSA reference architecture', false);
  addPageNum(s, 7, 20);
}

// =============================================================
// SLIDE 8 — WHY BOUNDED COMPETENCIES BEAT ONE BIG PROMPT
// (the Neuro-SAN AAOSA argument — explicit, side-by-side)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('5 · WHY THIS BEATS A SINGLE-PROMPT LLM', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Bounded competencies > one big prompt.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('Neuro-SAN AAOSA — Adaptive Agent-Oriented Software Architecture — applied to clinical prior-auth.', {
    x: 0.5, y: 1.85, w: 12, h: 0.32,
    fontSize: 13, fontFace: F.body, italic: true, color: C.textMuted,
  });

  // ===========================================================
  // TWO-COLUMN COMPARE TABLE
  // ===========================================================
  const colY = 2.45;
  const colH = 4.0;
  const leftX = 0.5, leftW = 6.05;
  const rightX = 6.78, rightW = 6.05;

  // Column headers
  s.addShape('rect', {
    x: leftX, y: colY, w: leftW, h: 0.55,
    fill: { color: '7F1D1D' }, line: { type: 'none' },
  });
  s.addText('ONE BIG PROMPT', {
    x: leftX + 0.15, y: colY, w: leftW - 0.3, h: 0.55,
    fontSize: 14, fontFace: F.mono, bold: true, color: C.white,
    valign: 'middle', charSpacing: 6,
  });
  s.addText('typical demo / monolithic LLM', {
    x: leftX, y: colY, w: leftW - 0.15, h: 0.55,
    fontSize: 10, fontFace: F.body, italic: true, color: 'FCA5A5',
    align: 'right', valign: 'middle',
  });

  s.addShape('rect', {
    x: rightX, y: colY, w: rightW, h: 0.55,
    fill: { color: C.indigo }, line: { type: 'none' },
  });
  s.addText('CLINCASE  ·  AAOSA', {
    x: rightX + 0.15, y: colY, w: rightW - 0.3, h: 0.55,
    fontSize: 14, fontFace: F.mono, bold: true, color: C.white,
    valign: 'middle', charSpacing: 6,
  });
  s.addText('7 parents · 22 sub-agents · bounded', {
    x: rightX, y: colY, w: rightW - 0.15, h: 0.55,
    fontSize: 10, fontFace: F.body, italic: true, color: 'A5B4FC',
    align: 'right', valign: 'middle',
  });

  // Rows
  const rows = [
    {
      axis: 'DEBUGGABILITY',
      con: 'One prompt to inspect when a verdict is wrong. Token budget for the whole pipeline. Prompt-engineering by intuition.',
      pro: 'Each agent ≤ 200 LoC + a Pydantic contract + a fixture-driven contract test. Fail an agent in isolation, fix it in isolation.',
    },
    {
      axis: 'GRADING',
      con: 'One score, one direction. "Did the LLM do well?" with no idea which faculty broke.',
      pro: 'Per-agent 5-field GraderScore (correctness · grounding · completeness · format · safety) → composite + per-field deltas.',
    },
    {
      axis: 'AUDITABILITY',
      con: 'Single black box. CMS-0057-F § IV.A asks "show your reasoning" — answer is "trust the model".',
      pro: 'Every hop emits an SSE trace event + writes an audit_ledger row. Verdict is reconstructible from the ledger alone.',
    },
    {
      axis: 'COST · MODEL ROUTING',
      con: 'One model size for everything. Simple keyword filter pays Sonnet rates.',
      pro: 'Sonnet 4.6 on reasoning, Haiku 4.5 on retrieval / probability / grading → 4× cheaper at the same accuracy.',
    },
    {
      axis: 'VERSIONING',
      con: 'Replace the model = re-validate everything. One prompt change = unknown blast radius.',
      pro: 'Replace one agent = run its contract test. Version each prompt + each schema independently.',
    },
  ];

  const rowStartY = colY + 0.65;
  const rowGap = (colH - 0.65) / rows.length;
  rows.forEach((row, i) => {
    const ry = rowStartY + i * rowGap;
    // Axis pill (centred between the two columns visually, but anchored on left col)
    s.addShape('rect', {
      x: leftX, y: ry, w: leftW + rightW + 0.23, h: 0.32,
      fill: { color: C.surface }, line: { type: 'none' },
    });
    s.addText(row.axis, {
      x: leftX + 0.15, y: ry, w: leftW + rightW, h: 0.32,
      fontSize: 11, fontFace: F.mono, bold: true, color: C.textMuted,
      valign: 'middle', charSpacing: 4,
    });
    // CON cell
    s.addText('✕  ' + row.con, {
      x: leftX + 0.15, y: ry + 0.36, w: leftW - 0.3, h: rowGap - 0.4,
      fontSize: 11, fontFace: F.body, color: '7F1D1D',
    });
    // PRO cell
    s.addText('✓  ' + row.pro, {
      x: rightX + 0.15, y: ry + 0.36, w: rightW - 0.3, h: rowGap - 0.4,
      fontSize: 11, fontFace: F.body, color: C.textInk, bold: true,
    });
  });

  // Bottom payoff strip — kept above the source-footer band (y=7.0)
  s.addShape('rect', {
    x: 0.5, y: 6.5, w: 12.3, h: 0.4,
    fill: { color: C.navy }, line: { type: 'none' },
  });
  s.addText('Each agent is replaceable, gradable, and auditable. The architecture itself is the compliance answer.', {
    x: 0.5, y: 6.5, w: 12.3, h: 0.4,
    fontSize: 12.5, fontFace: F.body, italic: true, color: C.cyan,
    align: 'center', valign: 'middle',
  });

  addSourceFooter(s, 'Neuro-SAN AAOSA reference architecture · CMS-0057-F § IV.A (Audit Trail) · ClinCase llm_invocations + audit_ledger schemas', false);
  addPageNum(s, 8, 20);
}

// =============================================================
// SLIDE 9 — 7-AGENT DAG TOPOLOGY (real flow + APPROVE/REFER/DENY fork)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('5 · ARCHITECTURE — 7-AGENT LANGGRAPH DAG', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Seven parents. Visible flow. Conditional fork.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 26, fontFace: F.head, bold: true, color: C.textInk,
  });

  // ================================================================
  // TOP ROW — linear path: Extractor → Retriever → Necessity → Decision
  // ================================================================
  const topAgents = [
    { name: 'Clinical\nExtractor',   model: 'sonnet 4.6', color: C.green },
    { name: 'Policy\nRetriever',     model: 'haiku 4.5',  color: '0284C7' },
    { name: 'Necessity\nReasoner',   model: 'sonnet 4.6', color: C.violet },
    { name: 'Decision\nComposer',    model: 'sonnet 4.6', color: C.indigo },
  ];

  const topY = 2.15;
  const aW = 2.55, aH = 1.15;
  const gap = 0.45;
  const startX = 0.5;
  const drawAgentBox = (x, y, a) => {
    s.addShape('roundRect', {
      x, y, w: aW, h: aH,
      fill: { color: C.white }, line: { color: a.color, width: 1.5 },
      rectRadius: 0.08,
    });
    // Top accent bar
    s.addShape('rect', {
      x, y, w: aW, h: 0.07,
      fill: { color: a.color }, line: { type: 'none' },
    });
    // Name
    s.addText(a.name.replace(/\n/g, ' '), {
      x: x + 0.15, y: y + 0.15, w: aW - 0.3, h: 0.45,
      fontSize: 14, fontFace: F.head, bold: true, color: C.textInk,
    });
    // Model pill
    s.addShape('roundRect', {
      x: x + 0.15, y: y + 0.7, w: 1.5, h: 0.28,
      fill: { color: a.color }, line: { type: 'none' },
      rectRadius: 0.04,
    });
    s.addText(a.model, {
      x: x + 0.15, y: y + 0.7, w: 1.5, h: 0.28,
      fontSize: 10, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 1,
    });
  };

  topAgents.forEach((a, i) => {
    const x = startX + i * (aW + gap);
    drawAgentBox(x, topY, a);
    // Arrow to next box (skip after last)
    if (i < topAgents.length - 1) {
      s.addShape('rightArrow', {
        x: x + aW + 0.04, y: topY + aH / 2 - 0.13, w: gap - 0.08, h: 0.26,
        fill: { color: C.textMuted }, line: { type: 'none' },
      });
    }
  });

  // ================================================================
  // FORK — Decision Composer's verdict branches three ways
  // ================================================================
  // Vertical drop from Decision Composer down to fork hub
  const decisionX = startX + 3 * (aW + gap);            // x of Decision box
  const forkHubX = decisionX + aW / 2;                  // centred under it
  const forkHubY = 3.95;
  s.addShape('rect', {
    x: forkHubX - 0.02, y: topY + aH, w: 0.04, h: forkHubY - (topY + aH),
    fill: { color: C.indigo }, line: { type: 'none' },
  });
  // Fork diamond label
  s.addShape('roundRect', {
    x: forkHubX - 0.9, y: forkHubY, w: 1.8, h: 0.45,
    fill: { color: C.indigo }, line: { type: 'none' },
    rectRadius: 0.05,
  });
  s.addText('verdict ?', {
    x: forkHubX - 0.9, y: forkHubY, w: 1.8, h: 0.45,
    fontSize: 12, fontFace: F.mono, bold: true, color: C.white,
    align: 'center', valign: 'middle', charSpacing: 2,
  });

  // Three branches from the verdict box
  const branchY = forkHubY + 0.8;
  const branches = [
    { label: 'APPROVE', color: C.green, target: 'TriZetto submission · done' },
    { label: 'REFER',   color: C.amber, target: 'Reviewer queue · HITL' },
    { label: 'DENY',    color: C.red,   target: 'Denial Forecaster →' },
  ];
  // Spread the three branches evenly across the slide width below the verdict
  const branchXs = [1.1, 5.6, 10.1];
  branches.forEach((b, i) => {
    // L-shape connector from verdict box to branch label
    const branchCx = branchXs[i] + 1.55;
    // horizontal arm at y = forkHubY + 0.6
    const armY = forkHubY + 0.6;
    s.addShape('rect', {
      x: Math.min(forkHubX, branchCx) - 0.02, y: armY,
      w: Math.abs(branchCx - forkHubX) + 0.04, h: 0.04,
      fill: { color: b.color }, line: { type: 'none' },
    });
    // vertical drop into the branch label
    s.addShape('rect', {
      x: branchCx - 0.02, y: armY, w: 0.04, h: branchY - armY,
      fill: { color: b.color }, line: { type: 'none' },
    });
    // Branch tag (label)
    s.addShape('roundRect', {
      x: branchXs[i], y: branchY, w: 3.1, h: 0.42,
      fill: { color: b.color }, line: { type: 'none' },
      rectRadius: 0.04,
    });
    s.addText(b.label, {
      x: branchXs[i], y: branchY, w: 3.1, h: 0.42,
      fontSize: 13, fontFace: F.head, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 4,
    });
    // Target description
    s.addText(b.target, {
      x: branchXs[i], y: branchY + 0.5, w: 3.1, h: 0.3,
      fontSize: 11, fontFace: F.mono, color: C.textBody,
      align: 'center', italic: true,
    });
  });

  // ================================================================
  // DENY tail — three more agents under the DENY branch
  // ================================================================
  const tailY = 5.7;
  const tailAgents = [
    { name: 'Denial Forecaster',     model: 'haiku 4.5',  color: C.amber, sub: 'P(denial) + reason' },
    { name: 'Appeals Drafter',       model: 'sonnet 4.6', color: C.red,   sub: 'NCCN-cited letter' },
    { name: 'Patient Communicator',  model: 'sonnet 4.6', color: C.cyan,  sub: '6th-grade · zero PHI' },
  ];
  const tailW = 3.85, tailH = 0.85, tailGap = 0.27;
  const tailStartX = 0.6;
  const pillW = 1.4;
  tailAgents.forEach((a, i) => {
    const x = tailStartX + i * (tailW + tailGap);
    s.addShape('roundRect', {
      x, y: tailY, w: tailW, h: tailH,
      fill: { color: C.white }, line: { color: a.color, width: 1.5 },
      rectRadius: 0.06,
    });
    s.addShape('rect', {
      x, y: tailY, w: 0.08, h: tailH,
      fill: { color: a.color }, line: { type: 'none' },
    });
    s.addText(a.name, {
      x: x + 0.2, y: tailY + 0.06, w: tailW - 0.3, h: 0.3,
      fontSize: 13, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(a.sub, {
      x: x + 0.2, y: tailY + 0.4, w: tailW - pillW - 0.35, h: 0.4,
      fontSize: 10.5, fontFace: F.mono, color: C.textBody, italic: true,
    });
    // Model pill (right end)
    s.addShape('roundRect', {
      x: x + tailW - pillW - 0.15, y: tailY + 0.45, w: pillW, h: 0.28,
      fill: { color: a.color }, line: { type: 'none' },
      rectRadius: 0.04,
    });
    s.addText(a.model, {
      x: x + tailW - pillW - 0.15, y: tailY + 0.45, w: pillW, h: 0.28,
      fontSize: 10, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 1,
    });
    if (i < tailAgents.length - 1) {
      s.addShape('rightArrow', {
        x: x + tailW + 0.02, y: tailY + tailH / 2 - 0.1, w: tailGap - 0.06, h: 0.2,
        fill: { color: C.textMuted }, line: { type: 'none' },
      });
    }
  });

  // SSE / state-object annotation — tucked above the source footer
  s.addText('every hop → SSE trace + audit_ledger row · Pydantic v2 state', {
    x: 0.5, y: 6.65, w: 12.3, h: 0.3,
    fontSize: 11, fontFace: F.mono, color: C.textMuted, italic: true, align: 'center',
  });

  addSourceFooter(s, 'ClinCase source code · 98 LLM calls verified end-to-end on case_8f4ad9c2 (May 5 2026)', false);
  addPageNum(s, 9, 20);
}

// =============================================================
// SLIDE 10 — REAL-WORLD INPUTS · DOCUMENT INTAKE
//   Indian hospital reality: handwritten Rx, scanned reports, faxed denials.
//   The 7-agent DAG only runs on a typed ClinicalSnapshot — Document Intake
//   is what turns the messy real-world input into that typed payload.
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('5 · ARCHITECTURE — DOCUMENT INTAKE', {
    x: 0.5, y: 0.85, w: 9, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  // "Pre-DAG" badge top-right
  s.addShape('rect', {
    x: 9.7, y: 0.78, w: 3.1, h: 0.5,
    fill: { color: C.navy }, line: { color: C.cyan, width: 1 },
  });
  s.addText('PRE-DAG · INDIA-READY', {
    x: 9.7, y: 0.78, w: 3.1, h: 0.5,
    fontSize: 11, fontFace: F.mono, bold: true, color: C.cyan,
    align: 'center', valign: 'middle', charSpacing: 3,
  });
  s.addText('Indian hospital reality. Handwritten Rx, scanned reports, faxed denials.', {
    x: 0.5, y: 1.35, w: 12, h: 0.7,
    fontSize: 24, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('The 7-agent DAG only runs on a typed ClinicalSnapshot. Document Intake turns messy inputs into that payload.', {
    x: 0.5, y: 1.92, w: 12, h: 0.32,
    fontSize: 13, fontFace: F.body, italic: true, color: C.textMuted,
  });

  // ===========================================================
  // LEFT — input types (4 cards in a 2x2 grid)
  // ===========================================================
  const inputs = [
    { icon: '✍', label: 'Handwritten Rx',     sub: 'Indian Rx pad · brand names · scribbled doses', color: C.amber },
    { icon: '📄', label: 'Scanned echo',      sub: 'Lab report · structured table · LVEF + EF',     color: C.cyan },
    { icon: '📠', label: 'Faxed denial',      sub: 'Payer letter · printed text · stamped',          color: C.red },
    { icon: '📷', label: 'Phone-camera scan', sub: 'Pathology slip · skewed · variable lighting',    color: C.violet },
  ];
  const inX = 0.5, inY = 2.4, inW = 2.6, inH = 1.55, gapX = 0.18, gapY = 0.22;
  inputs.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = inX + col * (inW + gapX);
    const y = inY + row * (inH + gapY);
    s.addShape('roundRect', {
      x, y, w: inW, h: inH,
      fill: { color: C.white }, line: { color: it.color, width: 1.5 },
      rectRadius: 0.06,
    });
    s.addShape('rect', {
      x, y, w: inW, h: 0.07,
      fill: { color: it.color }, line: { type: 'none' },
    });
    s.addText(it.icon, {
      x: x + 0.15, y: y + 0.18, w: 0.5, h: 0.5,
      fontSize: 24, fontFace: F.body, valign: 'middle',
    });
    s.addText(it.label, {
      x: x + 0.7, y: y + 0.18, w: inW - 0.85, h: 0.4,
      fontSize: 14, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(it.sub, {
      x: x + 0.15, y: y + 0.78, w: inW - 0.3, h: 0.65,
      fontSize: 10.5, fontFace: F.mono, color: C.textBody, italic: true,
    });
  });

  // ===========================================================
  // CENTER — Document Intake pipeline (3 stages)
  // ===========================================================
  // Arrow from input grid → intake box
  s.addShape('rightArrow', {
    x: 6.0, y: 3.7, w: 0.55, h: 0.4,
    fill: { color: C.indigo }, line: { type: 'none' },
  });

  const stages = [
    { num: '1', name: 'Classifier', detail: 'PIL stats · typed/hand/mixed · 0 LLM tokens', color: '0284C7' },
    { num: '2', name: 'Vision Extractor', detail: 'Claude Sonnet 4.6 vision · Bedrock · structured JSON', color: C.indigo },
    { num: '3', name: 'FHIR Shaper', detail: 'partial ClinicalSnapshot · per-field confidence', color: C.violet },
  ];
  const stageX = 6.7, stageY = 2.4, stageW = 3.0, stageH = 1.0, stageGap = 0.15;
  stages.forEach((st, i) => {
    const y = stageY + i * (stageH + stageGap);
    s.addShape('roundRect', {
      x: stageX, y, w: stageW, h: stageH,
      fill: { color: C.white }, line: { color: st.color, width: 1.5 },
      rectRadius: 0.06,
    });
    s.addShape('ellipse', {
      x: stageX + 0.15, y: y + 0.22, w: 0.55, h: 0.55,
      fill: { color: st.color }, line: { type: 'none' },
    });
    s.addText(st.num, {
      x: stageX + 0.15, y: y + 0.22, w: 0.55, h: 0.55,
      fontSize: 14, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle',
    });
    s.addText(st.name, {
      x: stageX + 0.85, y: y + 0.12, w: stageW - 1.0, h: 0.32,
      fontSize: 13, fontFace: F.head, bold: true, color: C.textInk,
    });
    s.addText(st.detail, {
      x: stageX + 0.85, y: y + 0.45, w: stageW - 1.0, h: 0.5,
      fontSize: 10, fontFace: F.mono, color: C.textBody, italic: true,
    });
  });

  // Arrow from intake → DAG
  s.addShape('rightArrow', {
    x: 9.85, y: 3.7, w: 0.55, h: 0.4,
    fill: { color: C.cyan }, line: { type: 'none' },
  });

  // ===========================================================
  // RIGHT — ClinicalSnapshot output card → "into the DAG"
  // ===========================================================
  s.addShape('roundRect', {
    x: 10.55, y: 2.95, w: 2.3, h: 1.9,
    fill: { color: C.navy }, line: { type: 'none' },
    rectRadius: 0.08,
  });
  s.addText('CLINICAL\nSNAPSHOT', {
    x: 10.6, y: 3.05, w: 2.2, h: 0.65,
    fontSize: 14, fontFace: F.mono, bold: true, color: C.cyan,
    align: 'center', charSpacing: 3,
  });
  s.addText('typed · FHIR-shaped\nready for the 7-agent DAG', {
    x: 10.6, y: 3.7, w: 2.2, h: 0.7,
    fontSize: 10.5, fontFace: F.body, italic: true, color: 'CBD5E1',
    align: 'center', valign: 'top',
  });
  s.addText('→ Clinical Extractor', {
    x: 10.6, y: 4.42, w: 2.2, h: 0.32,
    fontSize: 11, fontFace: F.mono, color: C.cyan,
    align: 'center', charSpacing: 1,
  });

  // ===========================================================
  // BOTTOM — HITL safety + audit anchor
  // ===========================================================
  s.addShape('rect', {
    x: 0.5, y: 5.7, w: 12.3, h: 1.0,
    fill: { color: C.surface }, line: { color: C.border, width: 1 },
  });
  s.addText('SAFETY-FIRST · HITL', {
    x: 0.7, y: 5.8, w: 4.5, h: 0.3,
    fontSize: 11, fontFace: F.mono, bold: true, color: C.indigo, charSpacing: 4,
  });
  s.addText('Per-field confidence. Below 0.7 OR a binding field missing → REFER + Reviewer queue. The model never silently APPROVES on a smudged biomarker.', {
    x: 0.7, y: 6.05, w: 7.2, h: 0.55,
    fontSize: 11.5, fontFace: F.body, color: C.textBody, valign: 'top',
  });
  s.addText('CMS-0057-F § IV.A AUDIT', {
    x: 8.2, y: 5.8, w: 4.5, h: 0.3,
    fontSize: 11, fontFace: F.mono, bold: true, color: C.green, charSpacing: 4,
  });
  s.addText('SHA-256 of bytes + engines_used + per-field source_excerpt persisted to intake_documents. A scanned-fax verdict is as auditable as a clean-FHIR verdict.', {
    x: 8.2, y: 6.05, w: 4.6, h: 0.55,
    fontSize: 11.5, fontFace: F.body, color: C.textBody, valign: 'top',
  });

  addSourceFooter(s, 'app/agents/intake/ · prompts/intake/vision_extractor.txt · CMS-0057-F § IV.A · ASCO/CAP HER2 testing guideline 2018', false);
  addPageNum(s, 10, 20);
}

// =============================================================
// SLIDE 11 — TECH STACK
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('5 · TECH STACK · BUILT ON THE ENTERPRISE STANDARD', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Bedrock + Sonnet + MCP — exactly the stack the partner standardised on Nov 4, 2024.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 24, fontFace: F.head, bold: true, color: C.textInk,
  });

  // 4-column stack: AI/LLM | Backend | Frontend | Infra
  const cols = [
    { title: 'AI / LLM', color: C.indigo, items: [
      'Claude Sonnet 4.6 (Bedrock)', 'Claude Haiku 4.5 (grader)', 'LangGraph (DAG orchestration)', 'MCP (tool protocol)', 'Anthropic + OpenRouter (fallback)',
    ]},
    { title: 'Backend', color: C.violet, items: [
      'Python 3.11+ async', 'FastAPI + uvicorn', 'Pydantic v2 schemas', 'AsyncPG · Postgres driver', 'pytest + ruff + mypy strict',
    ]},
    { title: 'Frontend', color: C.cyan, items: [
      'React 18 + Vite 5', 'TypeScript strict', 'Tailwind CSS', 'lucide-react icons', 'SSE live-trace client',
    ]},
    { title: 'Infrastructure', color: C.amber, items: [
      'AWS Bedrock (ap-south-1)', 'AWS Q Business (RAG)', 'ECS Fargate · RDS · S3', 'KMS + IAM + Secrets Mgr', 'CloudWatch observability',
    ]},
  ];

  const cwS = 3.0, chS = 4.4;
  cols.forEach((col, i) => {
    const x = 0.5 + i * 3.13, y = 2.2;

    s.addShape('rect', {
      x, y, w: cwS, h: chS,
      fill: { color: C.white },
      line: { color: C.border, width: 1 },
    });
    // Header
    s.addShape('rect', {
      x, y, w: cwS, h: 0.55,
      fill: { color: col.color }, line: { type: 'none' },
    });
    s.addText(col.title, {
      x: x + 0.15, y: y + 0.1, w: cwS - 0.3, h: 0.4,
      fontSize: 16, fontFace: F.head, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 2,
    });
    // Items
    col.items.forEach((item, j) => {
      const iy = y + 0.7 + j * 0.7;
      // Bullet circle
      s.addShape('ellipse', {
        x: x + 0.15, y: iy + 0.13, w: 0.18, h: 0.18,
        fill: { color: col.color }, line: { type: 'none' },
      });
      s.addText(item, {
        x: x + 0.43, y: iy, w: cwS - 0.55, h: 0.5,
        fontSize: 12, fontFace: F.mono, color: C.textBody, valign: 'middle',
      });
    });
  });

  // Bottom claim — moved up to clear source footer
  s.addShape('rect', {
    x: 0.5, y: 6.5, w: 12.3, h: 0.45,
    fill: { color: C.navy }, line: { type: 'none' },
  });
  s.addText([
    { text: 'No new tech for the partner to adopt. ', options: { color: C.cyan, bold: true } },
    { text: 'We use theirs.', options: { color: C.white, bold: true } },
  ], {
    x: 0.5, y: 6.5, w: 12.3, h: 0.45,
    fontSize: 15, fontFace: F.head, valign: 'middle', align: 'center',
  });

  addSourceFooter(s, 'Anthropic-enterprise partnership announcement (Nov 4, 2024) · AWS Bedrock pricing (May 2026)', false);
  addPageNum(s, 11, 20);
}

// =============================================================
// SLIDE 12 — BUSINESS IMPACT (the headline)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('4 · BUSINESS IMPACT', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('From $1,500 manual labour to 25 cents of AI compute.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 26, fontFace: F.head, bold: true, color: C.textInk,
  });

  // Hero comparison
  s.addShape('rect', {
    x: 0.5, y: 2.2, w: 5.85, h: 2.15,
    fill: { color: C.surface },
    line: { color: C.red, width: 2 },
  });
  s.addText('MANUAL PRIOR AUTH', {
    x: 0.7, y: 2.35, w: 5.5, h: 0.3,
    fontSize: 12, fontFace: F.mono, bold: true, color: C.red, charSpacing: 4,
  });
  s.addText('$1,500', {
    x: 0.7, y: 2.7, w: 5.5, h: 1.1,
    fontSize: 80, fontFace: F.head, bold: true, color: C.red, charSpacing: -2,
  });
  s.addText('per case · 14 days · 3 hours of physician labour', {
    x: 0.7, y: 3.85, w: 5.5, h: 0.4,
    fontSize: 15, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // ClinCase side
  s.addShape('rect', {
    x: 6.95, y: 2.2, w: 5.85, h: 2.15,
    fill: { color: '#F0FDF4' },
    line: { color: C.green, width: 2 },
  });
  s.addText('CLINCASE (verified May 5 2026)', {
    x: 7.15, y: 2.35, w: 5.5, h: 0.3,
    fontSize: 12, fontFace: F.mono, bold: true, color: C.green, charSpacing: 4,
  });
  s.addText('$0.25', {
    x: 7.15, y: 2.7, w: 5.5, h: 1.1,
    fontSize: 80, fontFace: F.head, bold: true, color: C.green, charSpacing: -2,
  });
  s.addText('per clean APPROVE · 60 seconds · 98 LLM calls', {
    x: 7.15, y: 3.85, w: 5.5, h: 0.4,
    fontSize: 15, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // Net impact strip
  s.addShape('rect', {
    x: 0.5, y: 4.55, w: 12.3, h: 1.05,
    fill: { color: C.navy }, line: { type: 'none' },
  });
  s.addText('NET SAVINGS PER CASE', {
    x: 0.7, y: 4.65, w: 5, h: 0.3,
    fontSize: 13, fontFace: F.mono, bold: true, color: C.cyan, charSpacing: 4,
  });
  s.addText('$1,499.75', {
    x: 0.7, y: 4.95, w: 6, h: 0.7,
    fontSize: 44, fontFace: F.head, bold: true, color: C.white, charSpacing: -1,
  });
  s.addText('99.93% cost reduction', {
    x: 0.7, y: 4.95, w: 11.5, h: 0.7,
    fontSize: 20, fontFace: F.head, color: '94A3B8', italic: true,
    align: 'right', valign: 'middle',
  });

  // Scale impact
  s.addShape('rect', {
    x: 0.5, y: 5.85, w: 12.3, h: 1.05,
    fill: { color: C.surface }, line: { color: C.border, width: 1 },
  });
  s.addText('AT ONE 200-BED CANCER CENTRE: 150 oncology PAs/month × $1,499.75 saved =', {
    x: 0.7, y: 5.95, w: 8, h: 0.4,
    fontSize: 15, fontFace: F.body, color: C.textBody, italic: true, valign: 'middle',
  });
  s.addText('$224,962 / month', {
    x: 7.5, y: 5.95, w: 5.2, h: 0.4,
    fontSize: 22, fontFace: F.head, bold: true, color: C.green, valign: 'middle', align: 'right',
  });
  s.addText('Payback: under 0.2 days per case · ROI on Pilot tier subscription: 16,664%', {
    x: 0.7, y: 6.4, w: 11.6, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.textMuted, valign: 'middle',
  });

  addSourceFooter(s, 'AMA Prior Auth Survey 2024 · ClinCase verified llm_invocations table (case_8f4ad9c2, May 5 2026)', false);
  addPageNum(s, 12, 20);
}

// =============================================================
// SLIDE 13 — MARKET HIERARCHY (TAM/SAM/SOM)
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('4 · MARKET OPPORTUNITY', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('$30B → $200M → $20M.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 32, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('Total US prior-auth waste, addressable specialty PA market, and 5-year capture target.', {
    x: 0.5, y: 1.95, w: 12, h: 0.4,
    fontSize: 16, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // 3 stair-stepped layers
  const lays = [
    { tag: 'TAM', value: '$30B', desc: 'Total annual US prior-auth admin waste',
      cite: 'CAQH Index 2024 · 600M PA decisions/year × $50 admin labour each',
      bg: '1E3A8A', tagBg: '93C5FD', x: 0.5 },
    { tag: 'SAM', value: '$200M', desc: 'US specialty-drug PA market at $5/case',
      cite: 'CAQH 2024 + ASCO QOPI 2024 · 40M oncology PAs/year alone · 38% YoY growth',
      bg: '5B21B6', tagBg: 'DDD6FE', x: 1.4 },
    { tag: 'SOM', value: '$20M', desc: '5-year capture · 10% via the payer organization',
      cite: 'Conservative · assumes only the partner existing accounts',
      bg: '047857', tagBg: '6EE7B7', x: 2.3 },
  ];
  lays.forEach((l, i) => {
    const y = 2.6 + i * 1.05;
    const w = 12.3 - l.x;
    s.addShape('rect', {
      x: l.x, y, w, h: 1.0,
      fill: { color: l.bg }, line: { type: 'none' },
    });
    // Tag pill
    s.addShape('rect', {
      x: l.x + 0.25, y: y + 0.32, w: 0.7, h: 0.36,
      fill: { color: l.tagBg }, line: { type: 'none' },
    });
    s.addText(l.tag, {
      x: l.x + 0.25, y: y + 0.32, w: 0.7, h: 0.36,
      fontSize: 13, fontFace: F.mono, bold: true, color: C.textInk,
      align: 'center', valign: 'middle',
    });
    // Value
    s.addText(l.value, {
      x: l.x + 1.1, y: y + 0.18, w: 2.5, h: 0.7,
      fontSize: 38, fontFace: F.head, bold: true, color: C.white, charSpacing: -1,
    });
    // Desc + citation
    s.addText(l.desc, {
      x: l.x + 3.65, y: y + 0.15, w: w - 3.85, h: 0.4,
      fontSize: 16, fontFace: F.head, bold: true, color: C.white,
    });
    s.addText(l.cite, {
      x: l.x + 3.65, y: y + 0.55, w: w - 3.85, h: 0.4,
      fontSize: 11.5, fontFace: F.mono, color: 'CBD5E1', italic: true,
    });
  });

  // Footer note
  s.addShape('rect', {
    x: 0.5, y: 6.0, w: 12.3, h: 0.85,
    fill: { color: C.surface }, line: { color: C.border, width: 1 },
  });
  s.addText([
    { text: '4 · BUSINESS IMPACT (continued): ', options: { bold: true, color: C.indigo } },
    { text: 'Distribution path = ', options: { color: C.textBody } },
    { text: 'the payer organization ', options: { bold: true, color: C.textInk } },
    { text: 'sells to 47 of top 50 US payers + 200+ providers. We slot into the existing procurement vehicle.', options: { color: C.textBody } },
  ], {
    x: 0.7, y: 6.05, w: 12, h: 0.75,
    fontSize: 14, fontFace: F.body, valign: 'middle',
  });

  addSourceFooter(s, 'CAQH Index 2024 · ASCO QOPI 2024 · KFF 2024 · the partner 10-K 2024 (channel reach)', false);
  addPageNum(s, 13, 20);
}

// =============================================================
// SLIDE 14 — SCALABLE / REUSABLE
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('6 · SCALABLE / REUSABLE', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Same architecture, six markets — fixtures-only swap.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('The 7-agent DAG is payload-agnostic. Each adjacent market is a prompts + fixtures swap, not a re-architecture.', {
    x: 0.5, y: 1.95, w: 12, h: 0.5,
    fontSize: 16, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // 6 vertical extension cards
  const verticals = [
    { name: 'Prior Authorisation', tam: '$30B', status: 'TODAY', color: C.indigo, role: 'Oncology wedge · live demo' },
    { name: 'Utilisation Management', tam: '+ $60-90B', status: '2028', color: C.violet, role: 'Inpatient stay justification · level-of-care matching' },
    { name: 'Claim Denials', tam: '+ $45B', status: '2028', color: C.cyan, role: 'Auto-appeal on rejected claims · same NCCN engine' },
    { name: 'Revenue Cycle Mgmt', tam: '+ $60B', status: '2029', color: C.green, role: 'Coding audit · charge-capture validation · same agents' },
    { name: 'Pharmacovigilance', tam: '+ $30B', status: '2029', color: C.amber, role: 'Drug safety signal detection · Life Sciences vertical' },
    { name: 'Continuation of Care', tam: '+ $25B', status: '2030', color: C.red, role: 'Cycle 8 still appropriate? · longitudinal review' },
  ];

  const vw = 4.0, vh = 1.6;
  verticals.forEach((v, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * 4.18, y = 2.65 + row * 1.75;

    s.addShape('rect', {
      x, y, w: vw, h: vh,
      fill: { color: C.white },
      line: { color: v.color, width: 1.5 },
    });
    // Status badge
    s.addShape('rect', {
      x: x + vw - 1.0, y: y + 0.15, w: 0.85, h: 0.3,
      fill: { color: v.color }, line: { type: 'none' },
    });
    s.addText(v.status, {
      x: x + vw - 1.0, y: y + 0.15, w: 0.85, h: 0.3,
      fontSize: 11, fontFace: F.mono, bold: true, color: C.white,
      align: 'center', valign: 'middle', charSpacing: 1,
    });
    // Name
    s.addText(v.name, {
      x: x + 0.18, y: y + 0.15, w: vw - 1.2, h: 0.4,
      fontSize: 16, fontFace: F.head, bold: true, color: C.textInk,
    });
    // TAM
    s.addText(v.tam, {
      x: x + 0.18, y: y + 0.55, w: vw - 0.36, h: 0.4,
      fontSize: 22, fontFace: F.head, bold: true, color: v.color,
    });
    // Role
    s.addText(v.role, {
      x: x + 0.18, y: y + 1.05, w: vw - 0.36, h: 0.5,
      fontSize: 12, fontFace: F.body, color: C.textBody,
    });
  });

  // Bottom claim
  s.addText('Total adjacent TAM = ~6× the prior-auth opportunity. Same architecture. Same the partner distribution.', {
    x: 0.5, y: 6.55, w: 12.3, h: 0.4,
    fontSize: 16, fontFace: F.body, italic: true,
    color: C.textBody, align: 'center', bold: true,
  });

  addSourceFooter(s, 'CAQH 2024 · Industry analyst aggregations · ClinCase internal market sizing', false);
  addPageNum(s, 14, 20);
}

// =============================================================
// SLIDE 15 — STRATEGIC FIT
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('STRATEGIC FIT · WHY US, NOT SOMEONE ELSE', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.amber,
    charSpacing: 6, bold: true,
  });
  s.addText('The Anthropic-enterprise stack is our default, not our adaptation.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 26, fontFace: F.head, bold: true, color: C.textInk,
  });

  // 6 alignment rows in a table-like layout
  const aligns = [
    ['Anthropic stack · Nov 4 2024', 'Bedrock + Claude Sonnet 4.6 + MCP — exactly the stack the partner standardised on.'],
    ['Neuro-SAN AAOSA pattern', '7-parent bounded-responsibility DAG · stateful continuity · per-tenant adaptation · observability of every hop.'],
    ['the payer organization', 'Oncology PA wedge fits the named 2026 vertical focus — 38% YoY oncology PA volume growth.'],
    ['the Agent Foundry', 'Foundry-compatible manifest · model card · evaluation harness · observability spec.'],
    ['TriZetto integration', 'Provider→payer structured-envelope submission. Mock + real adapters both written.'],
    ['Kiro IDE', 'Spec-driven development. .kiro/specs/ on disk. Proves the enterprise IDE story without leaving the project.'],
  ];

  aligns.forEach((a, i) => {
    const y = 2.2 + i * 0.72;
    s.addShape('rect', {
      x: 0.5, y, w: 12.3, h: 0.62,
      fill: { color: i % 2 === 0 ? C.white : C.surface },
      line: { color: C.border, width: 1 },
    });
    // Left column: alignment topic
    s.addShape('rect', {
      x: 0.5, y, w: 0.06, h: 0.62,
      fill: { color: C.amber }, line: { type: 'none' },
    });
    s.addText(a[0], {
      x: 0.7, y: y + 0.05, w: 3.3, h: 0.55,
      fontSize: 14, fontFace: F.head, bold: true, color: C.textInk, valign: 'middle',
    });
    s.addText(a[1], {
      x: 4.1, y: y + 0.05, w: 8.6, h: 0.55,
      fontSize: 13, fontFace: F.body, color: C.textBody, valign: 'middle',
    });
  });

  // Bottom claim — moved up to clear source footer
  s.addShape('rect', {
    x: 0.5, y: 6.45, w: 12.3, h: 0.45,
    fill: { color: C.amber }, line: { type: 'none' },
  });
  s.addText('We are not asking the partner to adopt new technology. We use theirs.', {
    x: 0.5, y: 6.45, w: 12.3, h: 0.45,
    fontSize: 15, fontFace: F.head, bold: true, italic: true,
    color: C.white, align: 'center', valign: 'middle',
  });

  addSourceFooter(s, 'Anthropic-enterprise partnership announcement Nov 4 2024 · Neuro-SAN AAOSA reference', false);
  addPageNum(s, 15, 20);
}

// =============================================================
// SLIDE 16 — COMPLIANCE
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('COMPLIANCE · CMS-0057-F § IV READINESS', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Eight of eight federal clauses in force today.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });
  s.addText('Federal mandate enforces January 2027. We are 18 months early.', {
    x: 0.5, y: 1.95, w: 12, h: 0.4,
    fontSize: 16, fontFace: F.body, color: C.textMuted, italic: true,
  });

  // Donut "8 of 8" panel (left)
  s.addShape('roundRect', {
    x: 0.5, y: 2.6, w: 4.0, h: 4.2,
    fill: { color: C.green },
    line: { type: 'none' },
    rectRadius: 0.1,
  });
  // Big donut number
  s.addText('8 / 8', {
    x: 0.5, y: 2.9, w: 4.0, h: 1.6,
    fontSize: 90, fontFace: F.head, bold: true,
    color: C.white, align: 'center', charSpacing: -2,
  });
  s.addText('§ IV CLAUSES IN FORCE', {
    x: 0.5, y: 4.5, w: 4.0, h: 0.4,
    fontSize: 15, fontFace: F.mono, bold: true,
    color: C.white, align: 'center', charSpacing: 4,
  });
  s.addShape('rect', {
    x: 1.5, y: 5.0, w: 2.0, h: 0.04,
    fill: { color: C.white }, line: { type: 'none' },
  });
  s.addText('Verified end-to-end\non 2026-05-05', {
    x: 0.5, y: 5.15, w: 4.0, h: 1.0,
    fontSize: 14, fontFace: F.body, italic: true,
    color: '#A7F3D0', align: 'center',
  });
  s.addText('CMS-0057-F enforcement\nJanuary 2027', {
    x: 0.5, y: 6.05, w: 4.0, h: 0.7,
    fontSize: 13, fontFace: F.mono,
    color: '#6EE7B7', align: 'center',
  });

  // 8 clauses on right (2 columns)
  const clauses = [
    ['§ IV.A', 'Auditable decisions'],
    ['§ IV.B', 'Citation grounding (policy)'],
    ['§ IV.C', 'Citation grounding (clinical)'],
    ['§ IV.D', 'Structured payer-API integration'],
    ['§ IV.E', 'Appeal window standardisation'],
    ['§ IV.F', 'PHI handling (minimum necessary)'],
    ['§ IV.G', 'Reviewer transparency'],
    ['§ IV.H', 'Quarterly evidence pack'],
  ];

  clauses.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 4.85 + col * 4.0, y = 2.6 + row * 1.05;
    s.addShape('rect', {
      x, y, w: 3.95, h: 0.95,
      fill: { color: C.white },
      line: { color: C.green, width: 1 },
    });
    // Check icon
    s.addShape('ellipse', {
      x: x + 0.2, y: y + 0.18, w: 0.55, h: 0.55,
      fill: { color: C.green }, line: { type: 'none' },
    });
    s.addText('✓', {
      x: x + 0.2, y: y + 0.18, w: 0.55, h: 0.55,
      fontSize: 20, fontFace: F.head, bold: true, color: C.white,
      align: 'center', valign: 'middle',
    });
    // Tag
    s.addText(c[0], {
      x: x + 0.85, y: y + 0.13, w: 1.0, h: 0.35,
      fontSize: 13, fontFace: F.mono, bold: true, color: C.green, charSpacing: 2,
    });
    // Description
    s.addText(c[1], {
      x: x + 0.85, y: y + 0.45, w: 3.0, h: 0.4,
      fontSize: 13, fontFace: F.body, color: C.textBody,
    });
  });

  addSourceFooter(s, 'CMS Federal Register CMS-0057-F (Final Rule) · ClinCase compliance audit (May 5 2026)', false);
  addPageNum(s, 16, 20);
}

// =============================================================
// SLIDE 17 — ROADMAP
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('7 · ROADMAP', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('From hackathon win to $5M ARR · 30 months.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });

  // Timeline with 6 milestones
  const milestones = [
    { when: 'NOW', what: 'the 2026 hackathon', sub: 'Demo + first prize · pilot referrals · internships', color: C.indigo, isNow: true },
    { when: 'Q3 2026', what: 'First pilot · Tata Memorial Mumbai', sub: 'Trastuzumab + pembrolizumab · 80 cases/month · 90-day pilot to first paying month', color: C.violet },
    { when: 'Q4 2026', what: 'Second pilot · Apollo Hyderabad', sub: 'EGFR + HER2 + MSI-H cohort · multi-payer arbitration · both pilots paying by Dec 2026', color: C.cyan },
    { when: 'Q1 2027', what: 'TriZetto integration go-live', sub: 'the partner payer-side adapters · CMS-0057-F mandate enforcement Jan 1 · structured-envelope submission', color: C.green },
    { when: 'Q3 2027', what: 'Series-A · $4-6M target', sub: '3 more agents (UM · claims · RCM) · AWS Marketplace listing · 8 the partner referral channels', color: C.amber },
    { when: '2028', what: 'Adjacent verticals + $5M ARR', sub: 'UM (Q1) · Claim denials (Q3) · 10 enterprise accounts by Q4 · Series-B conversation', color: C.red },
  ];

  // Vertical timeline line
  s.addShape('rect', {
    x: 1.55, y: 2.3, w: 0.04, h: 4.4,
    fill: { color: C.border }, line: { type: 'none' },
  });

  milestones.forEach((m, i) => {
    const y = 2.3 + i * 0.78;
    // Dot
    s.addShape('ellipse', {
      x: 1.4, y: y + 0.05, w: 0.3, h: 0.3,
      fill: { color: m.color },
      line: m.isNow ? { color: m.color, width: 3 } : { type: 'none' },
    });
    if (m.isNow) {
      // Pulse outer ring (hollow — use white fill matching background)
      s.addShape('ellipse', {
        x: 1.27, y: y - 0.08, w: 0.55, h: 0.55,
        fill: { type: 'none' },
        line: { color: m.color, width: 1 },
      });
    }
    // When tag
    s.addText(m.when, {
      x: 0.5, y: y - 0.05, w: 0.85, h: 0.35,
      fontSize: 13, fontFace: F.mono, bold: true, color: m.color,
      align: 'right', valign: 'middle', charSpacing: 1,
    });
    // What
    s.addText(m.what, {
      x: 1.95, y: y - 0.05, w: 10.7, h: 0.4,
      fontSize: 16, fontFace: F.head, bold: true, color: C.textInk,
    });
    // Sub
    s.addText(m.sub, {
      x: 1.95, y: y + 0.32, w: 10.7, h: 0.4,
      fontSize: 12.5, fontFace: F.body, color: C.textMuted, italic: true,
    });
  });

  addSourceFooter(s, 'ClinCase business plan · the payer organization pipeline · CMS-0057-F mandate timeline', false);
  addPageNum(s, 17, 20);
}

// =============================================================
// SLIDE 18 — TEAM
// =============================================================
{
  const s = pres.addSlide();
  lightBackground(s);
  addBrandStrip(s);

  s.addText('TEAM AEROFYTA · 4 ROLES, NO OVERLAP', {
    x: 0.5, y: 0.85, w: 12, h: 0.4,
    fontSize: 13, fontFace: F.mono, color: C.indigo,
    charSpacing: 6, bold: true,
  });
  s.addText('Each member owns one evaluation criterion.', {
    x: 0.5, y: 1.25, w: 12, h: 0.7,
    fontSize: 28, fontFace: F.head, bold: true, color: C.textInk,
  });

  const team = [
    { initial: 'D', name: 'Danish A. G.', role: 'Team Lead · Chief Architect',
      owns: '7-agent DAG · Bedrock + Sonnet 4.6 · MCP · LLMClient · system design',
      ask: 'Tech Design & Architecture · AWS / GenAI Usage', color: C.indigo },
    { initial: 'P', name: 'Preethi Sivachandran', role: 'Product & Demo Lead · UX',
      owns: 'Live demo · UX flow · Tweaks panel · standalone showcase · pitch script',
      ask: 'Quality of Demo & Presentation', color: C.cyan },
    { initial: 'S', name: 'Sanjay N', role: 'Backend & Compliance Engineer',
      owns: 'FHIR R4 · Postgres + RLS · SHA-256 audit · CMS-0057-F · HIPAA / PHI',
      ask: 'MVP Functional Completeness (data plane)', color: C.violet },
    { initial: 'G', name: 'Gayathri B', role: 'Healthcare Domain & Business Analyst',
      owns: '$30B problem · CAQH/KFF 2024 sourcing · ROI math · pilot pipeline · NCCN',
      ask: 'Problem Clarity · Business Impact', color: C.amber },
  ];

  team.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * 6.18, y = 2.2 + row * 2.35;

    s.addShape('rect', {
      x, y, w: 5.95, h: 2.15,
      fill: { color: C.white },
      line: { color: C.border, width: 1 },
    });
    // Avatar circle
    s.addShape('ellipse', {
      x: x + 0.25, y: y + 0.25, w: 1.0, h: 1.0,
      fill: { color: t.color }, line: { type: 'none' },
    });
    s.addText(t.initial, {
      x: x + 0.25, y: y + 0.25, w: 1.0, h: 1.0,
      fontSize: 36, fontFace: F.head, bold: true, color: C.white,
      align: 'center', valign: 'middle',
    });
    // Name
    s.addText(t.name, {
      x: x + 1.4, y: y + 0.25, w: 4.4, h: 0.42,
      fontSize: 18, fontFace: F.head, bold: true, color: C.textInk,
    });
    // Role
    s.addText(t.role, {
      x: x + 1.4, y: y + 0.7, w: 4.4, h: 0.32,
      fontSize: 13, fontFace: F.mono, bold: true, color: t.color, charSpacing: 1,
    });
    // What they own
    s.addText('Builds: ', {
      x: x + 0.25, y: y + 1.45, w: 0.8, h: 0.3,
      fontSize: 11, fontFace: F.mono, bold: true, color: C.textMuted,
    });
    s.addText(t.owns, {
      x: x + 0.85, y: y + 1.45, w: 4.95, h: 0.3,
      fontSize: 11.5, fontFace: F.body, color: C.textBody,
    });
    // What they answer
    s.addText('Owns Q&A on: ', {
      x: x + 0.25, y: y + 1.75, w: 1.3, h: 0.3,
      fontSize: 11, fontFace: F.mono, bold: true, color: C.textMuted,
    });
    s.addText(t.ask, {
      x: x + 1.45, y: y + 1.75, w: 4.35, h: 0.3,
      fontSize: 11.5, fontFace: F.body, italic: true, color: t.color,
    });
  });

  // Footer note
  s.addText('We delivered the working system in 24 hours. We can ship at enterprise pace tomorrow.', {
    x: 0.5, y: 6.95, w: 12.3, h: 0.4,
    fontSize: 16, fontFace: F.head, italic: true, bold: true,
    color: C.indigo, align: 'center',
  });

  addPageNum(s, 18, 20);
}

// =============================================================
// SLIDE 19 — THE ASK + CLOSING
// =============================================================
{
  const s = pres.addSlide();
  darkBackground(s);
  addBrandStrip(s, true);

  s.addText('THE ASK', {
    x: 0.5, y: 1.0, w: 12, h: 0.4,
    fontSize: 15, fontFace: F.mono, color: C.cyan,
    charSpacing: 6, bold: true,
  });
  s.addText('Three asks. One closing line.', {
    x: 0.5, y: 1.5, w: 12, h: 0.8,
    fontSize: 36, fontFace: F.head, bold: true, color: C.white,
  });

  // 3 ask cards horizontally
  const asks = [
    { num: '1', t: 'First-prize recognition', d: 'Validation that the architecture is industrial-grade.' },
    { num: '2', t: 'the partner pilot referral', d: '1-2 Health Sciences referral accounts to onboard.' },
    { num: '3', t: 'Internships for the team', d: 'We want to keep building ClinCase inside the partner.' },
  ];

  asks.forEach((a, i) => {
    const x = 0.5 + i * 4.18, y = 2.7;
    s.addShape('rect', {
      x, y, w: 4.0, h: 1.95,
      fill: { color: 'FFFFFF' }, line: { type: 'none' },
      transparency: 0,
    });
    // Number ribbon
    s.addShape('rect', {
      x, y, w: 4.0, h: 0.5,
      fill: { color: C.cyan }, line: { type: 'none' },
    });
    s.addText('ASK ' + a.num, {
      x, y, w: 4.0, h: 0.5,
      fontSize: 14, fontFace: F.mono, bold: true, color: C.navy,
      align: 'center', valign: 'middle', charSpacing: 4,
    });
    s.addText(a.t, {
      x: x + 0.2, y: y + 0.65, w: 3.6, h: 0.5,
      fontSize: 18, fontFace: F.head, bold: true, color: C.navy,
    });
    s.addText(a.d, {
      x: x + 0.2, y: y + 1.15, w: 3.6, h: 0.7,
      fontSize: 13, fontFace: F.body, color: C.textBody,
    });
  });

  // Closing line (the killer)
  s.addShape('rect', {
    x: 0.5, y: 5.1, w: 12.3, h: 1.85,
    fill: { color: C.indigo, transparency: 25 }, line: { color: C.cyan, width: 1 },
  });
  s.addText('THE CLOSING LINE', {
    x: 0.7, y: 5.25, w: 12, h: 0.35,
    fontSize: 13, fontFace: F.mono, bold: true, color: C.cyan, charSpacing: 4,
  });
  s.addText('"We are not pitching a hackathon project.\nWe are pitching the missing piece of the Anthropic-enterprise healthcare stack."', {
    x: 0.7, y: 5.65, w: 12, h: 1.25,
    fontSize: 22, fontFace: F.head, italic: true, color: C.white,
    align: 'center', valign: 'middle',
  });

  addPageNum(s, 19, 20, true);
}

// =============================================================
// SLIDE 20 — THANK YOU + QR + SOURCES
// =============================================================
{
  const s = pres.addSlide();
  darkBackground(s);

  // Big thank you
  s.addText('THANK YOU.', {
    x: 0.5, y: 0.7, w: 12, h: 1.4,
    fontSize: 96, fontFace: F.head, bold: true, color: C.white, charSpacing: 2,
  });
  s.addText('Try it now on your phone.', {
    x: 0.5, y: 2.0, w: 12, h: 0.5,
    fontSize: 22, fontFace: F.head, italic: true, color: 'CBD5E1',
  });

  // Live AWS QR — encodes http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com/
  // PNG generated by ops/demo/pptx/_build_qr_png.py (segno, ECC-H, v7, 588x588).
  // White card behind for contrast against the navy slide; QR sits centred inside.
  s.addShape('rect', {
    x: 0.5, y: 2.85, w: 2.5, h: 2.5,
    fill: { color: C.white }, line: { color: C.cyan, width: 2 },
  });
  s.addImage({
    path: path.join(__dirname, '_qr_aws.png'),
    x: 0.65, y: 3.0, w: 2.2, h: 2.2,
  });

  // URL + description
  s.addText('clincase-demo-26697.s3-website-us-east-1.amazonaws.com', {
    x: 3.4, y: 2.85, w: 9, h: 0.6,
    fontSize: 28, fontFace: F.mono, bold: true, color: C.cyan, charSpacing: 1,
  });
  s.addText('13 routes · 3 demo paths (APPROVE / REFER / DENY) · zero backend · runs from anywhere', {
    x: 3.4, y: 3.5, w: 9, h: 0.4,
    fontSize: 15, fontFace: F.body, color: 'CBD5E1', italic: true,
  });

  // Team contacts
  s.addShape('rect', {
    x: 3.4, y: 4.05, w: 9, h: 0.06,
    fill: { color: C.cyan }, line: { type: 'none' },
  });
  s.addText('TEAM CONTACTS', {
    x: 3.4, y: 4.18, w: 9, h: 0.3,
    fontSize: 12, fontFace: F.mono, bold: true, color: C.cyan, charSpacing: 4,
  });
  s.addText([
    { text: 'Danish A. G. ', options: { color: C.white, bold: true } },
    { text: '· agdanishr@gmail.com', options: { color: '94A3B8' } },
  ], { x: 3.4, y: 4.5, w: 9, h: 0.32, fontSize: 14, fontFace: F.body });
  s.addText([
    { text: 'Preethi Sivachandran ', options: { color: C.white, bold: true } },
    { text: '· preethisivachandran0@gmail.com', options: { color: '94A3B8' } },
  ], { x: 3.4, y: 4.85, w: 9, h: 0.32, fontSize: 14, fontFace: F.body });
  s.addText([
    { text: 'Sanjay N · Gayathri B ', options: { color: C.white, bold: true } },
    { text: '· Chennai Institute of Technology · +91-8903099026', options: { color: '94A3B8' } },
  ], { x: 3.4, y: 5.2, w: 9, h: 0.32, fontSize: 14, fontFace: F.body });

  // Sources block (the credibility footer)
  s.addShape('rect', {
    x: 0.5, y: 5.85, w: 12.3, h: 1.35,
    fill: { color: C.indigo, transparency: 60 }, line: { color: C.cyan, width: 1 },
  });
  s.addText('SOURCES & CITATIONS · ALL CLAIMS VERIFIABLE', {
    x: 0.7, y: 5.95, w: 12, h: 0.3,
    fontSize: 12, fontFace: F.mono, bold: true, color: C.cyan, charSpacing: 4,
  });
  s.addText('CAQH Index 2024 (PA volume + waste) · AMA Prior Auth Survey 2024 (manual cost baseline) · KFF Medicare Advantage 2024 (overturn rate) · ASCO QOPI 2024 (oncology PA volume) · CMS Federal Register CMS-0057-F (Jan 2027 mandate) · Anthropic-enterprise partnership announcement (Nov 4 2024) · the partner 10-K 2024 (channel reach) · NCCN BINV-N v3.2026 (clinical guidelines) · AWS Bedrock pricing (May 2026) · ClinCase internal verified llm_invocations table (case_8f4ad9c2, 98 calls, May 5 2026)', {
    x: 0.7, y: 6.25, w: 12, h: 0.95,
    fontSize: 12, fontFace: F.body, color: 'CBD5E1', italic: true,
  });
}

// =============================================================
// SAVE
// =============================================================
const out = path.join(__dirname, 'ClinCase_Winning_Deck.pptx');
pres.writeFile({ fileName: out }).then((fileName) => {
  console.log('SUCCESS · wrote ' + fileName);
  console.log('Total slides: 18');
  console.log('Layout: 16:9 widescreen (13.333 × 7.5 inches)');
});
