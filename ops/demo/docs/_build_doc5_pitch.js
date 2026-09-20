/* ============================================================
   DOC 5 — Top 50 Pitch Lines (mapped to evaluation criteria)
   ============================================================ */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber,
} = require('docx');

const OUT = path.join(__dirname, 'ClinCase_05_Top_50_Pitch_Lines.docx');
const PAGE = { width: 11906, height: 16838 };
const MARGIN = { top: 1440, right: 1200, bottom: 1440, left: 1200 };
const CONTENT_W = 9506;
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 }, children: [new TextRun({ text: t, bold: true, size: 32, color: '0F172A' })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, bold: true, size: 26, color: '1E293B' })] });
const PARA = (t, opts = {}) => new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: t, size: 22, ...opts })] });
const PB = () => new Paragraph({ children: [new PageBreak()] });
const SPACER = () => new Paragraph({ spacing: { after: 100 }, children: [new TextRun('')] });

const LINE = (n, line, when, dim) => [
  new Paragraph({
    spacing: { before: 220, after: 60 },
    children: [
      new TextRun({ text: `${n}. `, bold: true, color: '4F46E5', size: 24 }),
      new TextRun({ text: '"' + line + '"', bold: true, color: '0F172A', size: 24 }),
    ],
  }),
  new Paragraph({ spacing: { after: 30 }, children: [
    new TextRun({ text: 'When to use: ', bold: true, color: '047857', size: 21 }),
    new TextRun({ text: when, size: 21 }),
  ]}),
  new Paragraph({ spacing: { after: 100 }, children: [
    new TextRun({ text: 'Scores on: ', bold: true, color: '0891B2', size: 21 }),
    new TextRun({ text: dim, italics: true, size: 21 }),
  ]}),
];

const c = [];

// COVER
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: 'CLINCASE', bold: true, size: 56, color: '4F46E5' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'Top 50 Pitch Lines — mapped to evaluation scoring', size: 26, color: '475569' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: 'Memorise these. Use them like a deck of cards on stage.', italics: true, size: 22, color: '64748B' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Document 5 of 7 · the 2026 hackathon', size: 22, color: '64748B' })] }));
c.push(PB());

c.push(H1('How to use these lines'));
c.push(PARA('Each line is a 5-15 word power statement. Tuned to land in 3 seconds. The judge\'s ear catches it; the line earns the point.'));
c.push(PARA('Format: line · when to use it · which evaluation criterion it scores on.'));
c.push(SPACER());
c.push(PARA('evaluation criteria (scoring map):', { bold: true }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'PROBLEM CLARITY — does the team understand the pain?', size: 22 })] }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'MVP COMPLETENESS — did they actually build it?', size: 22 })] }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'TECH DESIGN — is the architecture clean and explainable?', size: 22 })] }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'DEMO QUALITY — crisp delivery, every member can answer', size: 22 })] }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'BUSINESS IMPACT — does it work beyond the hack?', size: 22 })] }));
c.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: 'AWS / GENAI — meaningful use of the enterprise stack', size: 22 })] }));
c.push(PB());

// =============================================================
// TIER 1 — Power openers (1-10)
// =============================================================
c.push(H1('Tier 1 — Power Openers (use in the first 60 seconds)'));

c.push(...LINE(1, 'ClinCase turns a $1,500, 14-day fax-fight into a $1.01, 60-second cited verdict.',
  'Stage opening. Says everything. Memorise word-for-word.',
  'Problem Clarity + Business Impact + MVP Completeness'));

c.push(...LINE(2, 'Built on the same Bedrock, Claude Sonnet, and MCP stack the partner standardised on November 4, 2024.',
  'Establishes the partner fit in the first 30 seconds.',
  'AWS / GenAI Usage'));

c.push(...LINE(3, 'Seven specialised agents, twenty-two sub-agents, six concentric architectural layers.',
  'Right after the title slide. Anchors the technical depth.',
  'Tech Design'));

c.push(...LINE(4, 'Every claim bound to a FHIR resource. Every decision bound to a policy section. Every byte verifiable.',
  'When you reach the architecture explanation.',
  'Tech Design + Compliance'));

c.push(...LINE(5, 'CMS-0057-F mandates this be solved by January 2027. We are eighteen months early.',
  'Justifies regulatory tailwind. Use during the problem framing.',
  'Problem Clarity + Business Impact'));

c.push(...LINE(6, 'We are not pitching a hackathon project. We are pitching the missing piece of the Anthropic-enterprise healthcare stack.',
  'Closing line. Memorise. Drop the mic.',
  'Strategic Fit (all criteria)'));

c.push(...LINE(7, 'Provider-side, FHIR-native, citation-grounded — the niche no other AI prior-auth startup occupies.',
  'When asked "what makes you different".',
  'Business Impact'));

c.push(...LINE(8, 'Verified end-to-end on 2026-05-05: 98 LLM calls, 0 errors, $1.01 per case.',
  'When asked "is it actually built".',
  'MVP Completeness'));

c.push(...LINE(9, 'A 200-bed cancer centre saves $225,000 per month. Payback under 1 day per case.',
  'When the business judges lean forward.',
  'Business Impact'));

c.push(...LINE(10, 'The architecture is the compliance posture. Audit is not bolted on. It is the foundation.',
  'When healthcare or compliance comes up.',
  'Tech Design + Problem Clarity'));

c.push(PB());

// =============================================================
// TIER 2 — Architecture lines (11-20)
// =============================================================
c.push(H1('Tier 2 — Architecture Lines (during the demo / arch walkthrough)'));

c.push(...LINE(11, 'Six layers, single responsibility per layer, top-down dependency only.',
  'When pointing at the architecture poster.',
  'Tech Design'));

c.push(...LINE(12, 'Neuro-SAN AAOSA-aligned: bounded responsibility, stateful continuity, observable every hop.',
  'When the technical judge asks about agent design pattern.',
  'Tech Design + Strategic Fit'));

c.push(...LINE(13, 'Each agent has one job. Twenty-two specialist competencies. Zero overlap, zero gaps.',
  'When defending the 7-agent + 22-sub-agent count.',
  'Tech Design'));

c.push(...LINE(14, 'PHI never enters the LLM. Our sanitizer runs before the first token is generated.',
  'When HIPAA or privacy comes up.',
  'Tech Design + Problem Clarity'));

c.push(...LINE(15, 'Verdict synthesis is deterministic. The LLM produces evidence; the deterministic synthesizer produces the verdict.',
  'When the sceptic asks "what if the LLM is wrong".',
  'Tech Design'));

c.push(...LINE(16, 'Hash-chained audit ledger. Tamper-evident. Verifiable in under one second by SQL function.',
  'When auditability comes up.',
  'Tech Design + Compliance'));

c.push(...LINE(17, 'Three LLM providers wired in: Bedrock, Anthropic direct, OpenRouter. Switch via environment variable.',
  'When asked "what if Bedrock fails".',
  'Tech Design + AWS Usage'));

c.push(...LINE(18, 'AMBIGUOUS is a first-class outcome. We refuse to manufacture verdicts when evidence is missing.',
  'When the sceptic asks "what about edge cases".',
  'Tech Design + Problem Clarity'));

c.push(...LINE(19, 'Region-pinned to ap-south-1 — Mumbai — for eleven-millisecond latency to the Pune onsite.',
  'When AWS region choice comes up.',
  'AWS Usage'));

c.push(...LINE(20, 'The grader runs on Haiku. Five times cheaper. Fast enough for every output. Strict enough to reject hallucinations.',
  'When asked about the cost-vs-quality trade-off.',
  'Tech Design + AWS Usage'));

c.push(PB());

// =============================================================
// TIER 3 — Business / market lines (21-30)
// =============================================================
c.push(H1('Tier 3 — Business / Market Lines (for non-tech judges)'));

c.push(...LINE(21, 'Total addressable market: $30 billion of US prior-auth admin waste, sourced from CAQH 2024.',
  'When the market-sizing question comes up.',
  'Business Impact'));

c.push(...LINE(22, 'We sell through the payer organization — forty-seven of the top fifty US payers, two hundred providers, one procurement vehicle.',
  'When asked about distribution / GTM.',
  'Business Impact + Strategic Fit'));

c.push(...LINE(23, 'Three pricing tiers: pilot $9 per case, growth $6, enterprise $4. Per-case fee, not subscription.',
  'When asked about the pricing model.',
  'Business Impact'));

c.push(...LINE(24, 'Net savings per case: $1,499.75. ROI on the pilot subscription: sixteen thousand percent.',
  'When the ROI question lands.',
  'Business Impact'));

c.push(...LINE(25, 'First two pilots free. Ninety-day decision window. No lock-in, no cancellation fee.',
  'When asked about commercial terms.',
  'Business Impact'));

c.push(...LINE(26, 'Ninety-four percent of physicians say prior auth delays patient care. Eighty point seven percent of appealed denials get overturned.',
  'During the problem framing. Both numbers are sourced.',
  'Problem Clarity'));

c.push(...LINE(27, 'Olive AI raised eight hundred and fifty-two million and folded in 2023. We are the auditable, citation-grounded successor.',
  'When competitive landscape comes up.',
  'Business Impact + Tech Design'));

c.push(...LINE(28, 'TAM thirty billion. SAM two hundred million. SOM twenty million in five years. Conservative.',
  'When asked to size the opportunity.',
  'Business Impact'));

c.push(...LINE(29, 'Same architecture serves utilisation management, claim denials, revenue cycle. Six times the prior-auth TAM.',
  'When asked about adjacent markets.',
  'Business Impact'));

c.push(...LINE(30, 'Series-A target Q3 2027. Lead by enterprise SaaS or healthcare-AI fund. Use of funds: three more agents, AWS Marketplace, eight enterprise referral channels.',
  'When asked about funding plans.',
  'Business Impact'));

c.push(PB());

// =============================================================
// TIER 4 — the partner fit lines (31-40)
// =============================================================
c.push(H1('Tier 4 — Strategic Fit Lines (the "why us" answers)'));

c.push(...LINE(31, 'Bedrock plus Claude Sonnet 4.6 plus MCP — three components, all enterprise-standard, all in our stack.',
  'When the AWS / GenAI judge looks at the architecture.',
  'AWS Usage + Strategic Fit'));

c.push(...LINE(32, 'Agent Foundry-compatible: manifest, model card, evaluation harness, observability spec.',
  'When asked about productisation readiness.',
  'Tech Design + Strategic Fit'));

c.push(...LINE(33, 'TriZetto integration ready. Structured-envelope submission. Mock and production adapters both written.',
  'When asked about payer integration.',
  'Strategic Fit + Tech Design'));

c.push(...LINE(34, 'the payer organization sells in oncology PA already. We are the first auditable copilot for that segment.',
  'When asked about the partner\'s vertical strategy.',
  'Business Impact + Strategic Fit'));

c.push(...LINE(35, 'Anthropic-enterprise partnership announced November 4, 2024. We built on that exact stack two months later.',
  'When the AWS / Bedrock question comes up.',
  'AWS Usage + Strategic Fit'));

c.push(...LINE(36, 'Kiro IDE specs on disk. Spec-driven development. Proves the enterprise IDE story without leaving the project.',
  'When asked about the partner\'s tooling alignment.',
  'Strategic Fit'));

c.push(...LINE(37, 'We are not asking the partner to adopt new technology. We use theirs.',
  'The "why us, not someone else" question.',
  'Strategic Fit'));

c.push(...LINE(38, 'Provider abstraction means we are infrastructure-agnostic. Drop us into any AWS account, change one environment variable, deploy.',
  'When asked about deployment flexibility.',
  'AWS Usage + Tech Design'));

c.push(...LINE(39, 'BAA-ready, HIPAA-eligible Bedrock, encrypted at rest with KMS, in transit with TLS 1.3, in process with memory-only PHI.',
  'When asked about healthcare compliance posture.',
  'Tech Design + Strategic Fit'));

c.push(...LINE(40, 'the partner has the distribution. Anthropic has the model. We have the application. The triangle closes.',
  'When asked about partnership strategy.',
  'Strategic Fit + Business Impact'));

c.push(PB());

// =============================================================
// TIER 5 — Closing / call to action (41-50)
// =============================================================
c.push(H1('Tier 5 — Closing / Call-to-Action Lines'));

c.push(...LINE(41, 'Run the QR. Live demo on your phone, thirteen routes, three demo paths, zero backend.',
  'When inviting the judges to verify.',
  'MVP Completeness + Demo Quality'));

c.push(...LINE(42, 'Three asks: first prize recognition, the payer organization pilot referral, internship for the team.',
  'When asked "what do you want from us".',
  'Demo Quality'));

c.push(...LINE(43, 'Four roles, no overlap. Each member owns one evaluation criterion.',
  'When introducing the team.',
  'Demo Quality'));

c.push(...LINE(44, 'We delivered the working system in twenty-four hours. We can ship at enterprise pace tomorrow.',
  'When asked about team execution capability.',
  'Demo Quality + MVP Completeness'));

c.push(...LINE(45, 'Test-print of the kit went out yesterday. Standalone demo deployed. Domain live. Verified end-to-end.',
  'When asked about preparation depth.',
  'Demo Quality + MVP Completeness'));

c.push(...LINE(46, 'ClinCase is not an LLM. ClinCase is an architecture. The LLM is one swappable component.',
  'When the sceptic says "but ChatGPT could do this".',
  'Tech Design'));

c.push(...LINE(47, 'When Sonnet 5 ships, we update one line of code and inherit the improvement. We are forward-compatible by design.',
  'When asked about future-proofing.',
  'Tech Design'));

c.push(...LINE(48, 'Verify the math: open the audit ledger, count the citations, trace the hash chain. Everything we say is auditable.',
  'When the sceptic asks for proof.',
  'MVP Completeness + Compliance'));

c.push(...LINE(49, 'Eighteen months from now, every payer and provider in the United States must do this. We are a head start.',
  'When asked about market timing.',
  'Business Impact'));

c.push(...LINE(50, 'We are not the future of prior auth. We are the present of prior auth — the rest of the industry has not caught up yet.',
  'The mic-drop close. Use sparingly, use deliberately.',
  'All criteria'));

c.push(SPACER());
c.push(H1('Memorise these in three rounds'));
c.push(PARA('Round 1: lines 1, 2, 3, 6 — the four power openers. If you get nothing else, get these.'));
c.push(PARA('Round 2: lines 8, 14, 21, 24 — the four MVP / market / compliance lines. These will be asked.'));
c.push(PARA('Round 3: lines 31-37 — the partner fit lines. These are your differentiators in this specific hackathon.'));

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, font: 'Calibri', color: '0F172A' }, paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, font: 'Calibri', color: '1E293B' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: PAGE, margin: MARGIN } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'ClinCase · Top 50 Pitch Lines · Doc 5 of 7', size: 18, color: '94A3B8' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', size: 18, color: '94A3B8' }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '94A3B8' }), new TextRun({ text: ' · Team AeroFyta', size: 18, color: '94A3B8' })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('Wrote', OUT, '(' + buf.length + ' bytes)'); });
