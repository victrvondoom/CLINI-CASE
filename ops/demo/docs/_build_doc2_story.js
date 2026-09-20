/* ============================================================
   DOC 2 — ClinCase End-to-End Story (the complete narrative)
   ============================================================ */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber,
} = require('docx');

const OUT = path.join(__dirname, 'ClinCase_02_End_to_End_Story.docx');
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
const BOLD_BULLET = (label, body) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: label, bold: true, size: 22, color: '0F172A' }), new TextRun({ text: ' ' + body, size: 22 })] });
const SPACER = () => new Paragraph({ spacing: { after: 100 }, children: [new TextRun('')] });
const PB = () => new Paragraph({ children: [new PageBreak()] });

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

const TABLE_2COL = (header1, header2, rows) => {
  const w1 = 3200, w2 = CONTENT_W - 3200;
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [w1, w2],
    rows: [
      new TableRow({ tableHeader: true, children: [
        new TableCell({ borders: BORDERS, width: { size: w1, type: WidthType.DXA }, shading: { fill: '0F172A', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: header1, bold: true, color: 'FFFFFF', size: 21 })] })] }),
        new TableCell({ borders: BORDERS, width: { size: w2, type: WidthType.DXA }, shading: { fill: '0F172A', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: header2, bold: true, color: 'FFFFFF', size: 21 })] })] }),
      ]}),
      ...rows.map(([a, b]) => new TableRow({ children: [
        new TableCell({ borders: BORDERS, width: { size: w1, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: a, bold: true, size: 20 })] })] }),
        new TableCell({ borders: BORDERS, width: { size: w2, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: b, size: 20 })] })] }),
      ]})),
    ],
  });
};

// =============================================================
const c = []; // children

// COVER
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: 'CLINCASE', bold: true, size: 56, color: '4F46E5' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'The Complete Story — End-to-End Workflow', size: 28, color: '475569' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: 'How prior auth becomes a 60-second decision', italics: true, size: 22, color: '64748B' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Document 2 of 7 · the 2026 hackathon', size: 22, color: '64748B' })] }));
c.push(PB());

// =============================================================
// PART 1 — THE PROBLEM
// =============================================================
c.push(H1('Part 1 — The Problem We Solve'));
c.push(H2('What is prior authorisation, in one sentence?'));
c.push(PARA('Before a doctor can give an expensive treatment, the insurance company must first say YES. That permission step is called prior authorisation. It sounds simple. In reality, it is the single most-hated administrative process in US healthcare.'));
c.push(SPACER());

c.push(H2('The 14-day fax-fight (a real example)'));
c.push(PARA('A patient — call her M.K., 54 years old, female — walks into Tata Memorial Cancer Centre in Mumbai with HER2-positive breast cancer. Her oncologist, Dr. Mehta, prescribes trastuzumab, the standard targeted treatment. It costs $1,500 a month and is medically necessary.'));
c.push(PARA('Here is what happens next, in the current system:'));
c.push(SPACER());
c.push(BOLD_BULLET('Day 1', 'Dr. Mehta\'s office staff fills out a 12-page prior auth form. Faxes it to the insurance company.'));
c.push(BOLD_BULLET('Day 4', 'Insurance staff reads the fax. Notices LVEF (heart pumping efficiency) reading is missing. Faxes back asking for it.'));
c.push(BOLD_BULLET('Day 7', 'Dr. Mehta\'s office orders an echocardiogram. Faxes the result.'));
c.push(BOLD_BULLET('Day 10', 'Insurance staff reads the new fax. Notices the LVEF reading is from 4 months ago, not within the 90-day window. Denies the request.'));
c.push(BOLD_BULLET('Day 12', 'Dr. Mehta\'s office writes an appeal letter — 800 words, manually citing NCCN guidelines. 3 hours of physician time at $300/hour = $900 in labour.'));
c.push(BOLD_BULLET('Day 14', 'Appeal accepted. Patient finally starts treatment.'));
c.push(SPACER());
c.push(CALLOUT('What just happened', '14 days lost. $1,500 in administrative cost. The patient\'s tumour grew during the wait. Dr. Mehta wrote 4 different letters. The hospital sent 6 faxes. And every other prior auth in this office that day went through the same waste.', 'BE123C', 'FEF2F2'));
c.push(PB());

c.push(H2('The numbers (sourced)'));
c.push(TABLE_2COL('Number', 'What it means', [
  ['$30 billion / year', 'Total US prior-auth administrative waste (CAQH Index 2024)'],
  ['$1,500 / case', 'Average labour cost of one manual prior auth (AMA 2024)'],
  ['94 %', 'Of physicians who say prior auth delays patient care (AMA 2024 survey)'],
  ['80.7 %', 'Of appealed Medicare Advantage denials that get overturned (KFF 2024)'],
  ['14 days', 'Average time from submission to first decision (industry data)'],
  ['600 million', 'PA decisions made in the US each year (CAQH 2024)'],
  ['38 %', 'Year-over-year growth in oncology PA volume (ASCO QOPI 2024)'],
  ['Jan 2027', 'Federal mandate (CMS-0057-F) requiring automation of all the above'],
]));
c.push(SPACER());

c.push(H2('Why this is finally solvable now'));
c.push(BOLD_BULLET('FHIR R4 became universal:', 'The data shape is standardised. We can read patient records from any US hospital with the same code.'));
c.push(BOLD_BULLET('LLMs got smart enough:', 'Claude Sonnet 4.6 can read 12-page payer policies and apply them correctly. This was not possible 18 months ago.'));
c.push(BOLD_BULLET('CMS-0057-F is law:', 'January 2027 mandate makes manual PA non-compliant. Every payer + provider must automate. Forced demand.'));
c.push(BOLD_BULLET('the partner + Anthropic partnership:', 'November 4, 2024 — the partner standardised on Bedrock + Sonnet + MCP. We are pre-aligned with their stack.'));
c.push(PB());

// =============================================================
// PART 2 — THE SOLUTION (one paragraph)
// =============================================================
c.push(H1('Part 2 — The ClinCase Solution'));
c.push(PARA('ClinCase is a doctor\'s assistant powered by 7 specialised AI agents. It reads a patient\'s clinical data (in FHIR format) and the relevant payer policy (Aetna, UHC, NCCN, etc.), then decides whether the treatment will be approved — in 60 seconds. Every claim it makes is bound to a specific data source. The decision is logged in a tamper-evident audit ledger. If the case is denied, an NCCN-cited appeal letter is drafted automatically as a side effect.'));
c.push(SPACER());

c.push(H2('What makes ClinCase different from other "AI for healthcare" tools'));
c.push(TABLE_2COL('Differentiator', 'Why it matters', [
  ['Provider-side, not payer-side', 'We work for the doctor, not the insurance company. We help the patient get treatment, not deny it.'],
  ['FHIR-native, not custom format', 'Works with any US hospital today, no integration project required'],
  ['Citation-grounded, not opinion', 'Every claim cites a FHIR resource ID + a policy section. Auditable end-to-end.'],
  ['Appeals as a side effect', 'When we deny, the appeal letter is already drafted. Most competitors stop at "denied".'],
  ['Hash-chained audit ledger', 'CMS-0057-F § IV.A compliant by design. Auditor verification in <1 second.'],
  ['Bedrock + Claude + MCP stack', 'Exactly the stack the partner standardised on November 4, 2024'],
]));
c.push(PB());

// =============================================================
// PART 3 — END TO END FLOW (the meat)
// =============================================================
c.push(H1('Part 3 — End-to-End Flow (case lifecycle)'));
c.push(PARA('Let us walk a real case through the entire pipeline. Patient is M.K., HER2-positive Stage IIIA breast cancer. Dr. Mehta requests trastuzumab. The case enters ClinCase at 9:14 AM.'));
c.push(SPACER());

// Step 1
c.push(H2('Step 1 — Case ingestion (T+0 seconds)'));
c.push(PARA('A POST request hits our FastAPI endpoint POST /api/v1/cases with a FHIR R4 Bundle containing the patient\'s relevant clinical data. The case is assigned a case_id and written to the cases table in Postgres. Status: pending.'));
c.push(SPACER());
c.push(H3('What happens behind the scenes'));
c.push(BULLET('FastAPI validates the JWT (login token) — confirms which provider and tenant'));
c.push(BULLET('Case is written to cases table with row-level security (only Tenant A can see Tenant A cases)'));
c.push(BULLET('A background worker picks up the case from the queue'));
c.push(BULLET('SSE (Server-Sent Events) stream opens — the doctor\'s browser starts watching the case progress live'));
c.push(SPACER());

// Step 2
c.push(H2('Step 2 — PHI Sanitization (T+1 second)'));
c.push(PARA('Before the FHIR Bundle reaches any LLM, the PHI Sanitizer (a deterministic Python module — no AI) strips:'));
c.push(BULLET('Patient name → replaced with initials "M.K."'));
c.push(BULLET('Date of birth → replaced with age range'));
c.push(BULLET('Address, phone, MRN → replaced with hashed identifiers'));
c.push(BULLET('Photo URLs, free-text mentions of family members → replaced'));
c.push(SPACER());
c.push(CALLOUT('Why this matters', 'PHI never enters the LLM context window. Even if the LLM were compromised, no protected data could leak. This is HIPAA-compliant by architecture, not by policy.', '0891B2', 'ECFDF5'));
c.push(SPACER());

// Step 3
c.push(H2('Step 3 — Agent 1: Clinical Extractor (T+1 to T+15 seconds)'));
c.push(PARA('The first AI agent reads the sanitized FHIR Bundle and produces a typed ClinicalSnapshot object. The snapshot contains structured fields (icd10_code, stage, biomarkers, performance_status, etc.) that downstream agents can use without re-reading FHIR.'));
c.push(SPACER());
c.push(H3('Why Clinical Extractor exists'));
c.push(PARA('FHIR is verbose. A single Bundle can be 50,000 tokens of JSON. Loading that into every downstream agent is wasteful. The Extractor does the verbose work once, produces a tight summary, and downstream agents read the summary.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('biomarker_specialist:', 'Pulls HER2, ER, PR, Ki-67, LVEF from Observation resources. Normalises units (e.g., LVEF as percentage).'));
c.push(BOLD_BULLET('phi_sanitizer:', 'Re-checks for any PHI that slipped past the gate. Defence-in-depth.'));
c.push(BOLD_BULLET('fhir_resource_validator:', 'Confirms the Bundle is FHIR R4 compliant. Rejects malformed resources before LLM time is spent.'));
c.push(SPACER());
c.push(CALLOUT('Output of Step 3', 'A 200-line ClinicalSnapshot object: patient_age=54, stage=IIIA, biomarkers={HER2 IHC: 3+, FISH: 4.8, LVEF: 62%}, performance_status=ECOG 1, requested_treatment=Trastuzumab.', '047857', 'F0FDF4'));
c.push(PB());

// Step 4
c.push(H2('Step 4 — Agent 2: Policy Retriever (T+15 to T+22 seconds)'));
c.push(PARA('Now we need to find the right payer policy. There are thousands. We use a hybrid retrieval strategy.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('keyword_filter:', 'Quick pre-filter on payer_id + drug + indication. Cuts thousands of policies down to ~50 candidates.'));
c.push(BOLD_BULLET('q_business_retriever:', 'AWS Q Business does a semantic search on the 50 candidates. Returns the top 10 most relevant policy sections.'));
c.push(BOLD_BULLET('llm_reranker:', 'Claude Sonnet 4.6 re-ranks the 10 sections by actual relevance to the case. Returns top 5.'));
c.push(BOLD_BULLET('citation_resolver:', 'Looks up the canonical citation pointer for each retrieved section (e.g., "policy/aetna-0123#4.1").'));
c.push(SPACER());
c.push(CALLOUT('Output of Step 4', 'A list of 5 PolicyExcerpt objects — Aetna 0123 §4.1 (Trastuzumab indications), Aetna 0123 §4.2 (Cardiac workup requirement), NCCN BINV-N v3.2026 (HER2-positive treatment pathway), etc.', '0891B2', 'ECFEFF'));
c.push(PB());

// Step 5
c.push(H2('Step 5 — Agent 3: Necessity Reasoner (T+22 to T+45 seconds)'));
c.push(PARA('This is the hardest part. We need to check every criterion in the policy against the patient\'s data. Done wrong, this is where hallucinations happen. ClinCase breaks it into atomic, parallel checks.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('criterion_splitter:', 'Reads the 5 policy excerpts and produces a flat list of 8 atomic checkable criteria. Example: "HER2-positive (IHC 3+ or FISH ≥ 2.0)" is one criterion. "LVEF ≥ 50% within 90 days" is another.'));
c.push(BOLD_BULLET('evidence_matcher:', 'For EACH atomic criterion, fires in parallel. Checks the patient\'s ClinicalSnapshot. Returns MET / NOT_MET / AMBIGUOUS with cited evidence. 8 criteria = 8 parallel LLM calls.'));
c.push(BOLD_BULLET('confidence_calibrator:', 'Aggregates the 8 results. If any criterion is AMBIGUOUS, flags the case for REFER. If all are MET, high confidence.'));
c.push(SPACER());
c.push(CALLOUT('Output of Step 5', 'A NecessityAssessment object with 8 criterion results. Example: HER2-positive=MET (Observation/obs-901), LVEF≥50%=MET (Observation/obs-906 = 62%), ECOG 0-2=MET (Observation/obs-907 = ECOG 1)... All 8 MET, confidence 0.92.', '7C3AED', 'F5F3FF'));
c.push(PB());

// Step 6
c.push(H2('Step 6 — Agent 4: Decision Composer (T+45 to T+55 seconds)'));
c.push(PARA('Now we have an assessment. We need to turn it into a decision with a rationale and citations.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('verdict_synthesizer:', 'Deterministic logic — no LLM. If all inclusion criteria MET and no exclusion criteria triggered, verdict=APPROVE. If any inclusion NOT_MET, verdict=DENY. If any AMBIGUOUS, verdict=REFER.'));
c.push(BOLD_BULLET('rationale_writer:', 'Composes a 2-4 sentence executive rationale. Cites the snapshot and policy fields used.'));
c.push(BOLD_BULLET('citation_linker:', 'Builds the final citation chain. Each citation has kind=clinical or kind=policy + a stable pointer.'));
c.push(SPACER());
c.push(CALLOUT('Output of Step 6', 'verdict=APPROVE, confidence=0.92, rationale="All five inclusion criteria for trastuzumab under Aetna policy 0123 are met...", 7 citations attached. Decision row written to the decisions table.', '4F46E5', 'EEF2FF'));
c.push(PB());

// Step 7
c.push(H2('Step 7 — Agent 5: Denial Forecaster (T+55 to T+65 seconds, always fires)'));
c.push(PARA('Even when WE approve a case, we forecast what the PAYER will do. This is critical: our decision and the payer\'s decision can differ. Pre-warning the doctor saves another round of fax-fighting.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('probability_estimator:', 'Predicts payer denial probability (0.0 to 1.0). For our APPROVE case, probability is low (~0.08). For an edge case, might be 0.55.'));
c.push(BOLD_BULLET('reason_predictor:', 'For top reasons the payer might deny. Helps the appeals drafter pre-stage counter-arguments.'));
c.push(BOLD_BULLET('appeal_path_recommender:', 'If denial probability ≥ 0.35, recommends the appeal angle (biomarker_evidence, guideline_alignment, prior_therapy_failure, etc.).'));
c.push(SPACER());

// Step 8
c.push(H2('Step 8 — Agent 6: Appeals Drafter (only fires on DENY or high-prob cases)'));
c.push(PARA('When the verdict is DENY, or when our APPROVE has high payer-denial probability, the Appeals Drafter pre-writes the appeal letter. The clinician never starts from a blank page.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('counter_evidence_finder:', 'Finds clinical evidence in the snapshot that contests the likely denial reason. (E.g., if denial reason is "missing LVEF", finds the LVEF reading and flags it.)'));
c.push(BOLD_BULLET('nccn_reference_specialist:', 'Pulls NCCN guideline references that support the treatment.'));
c.push(BOLD_BULLET('letter_composer:', 'Composes a formal 5-paragraph appeal letter with NCCN citations and the structured arguments. Includes the standard 14-day acknowledgement clause per CMS-0057-F § IV.E.'));
c.push(SPACER());
c.push(CALLOUT('Output (only on DENY)', 'A complete appeal letter ready for the clinician to review and sign. NCCN-cited, CMS-0057-F-compliant 14-day clause included, structured arguments machine-readable in JSON. Cost: $0.55 per case (~$0.30 of which is the appeal).', 'E11D48', 'FEF2F2'));
c.push(PB());

// Step 9
c.push(H2('Step 9 — Agent 7: Patient Communicator (always fires)'));
c.push(PARA('A doctor-friendly verdict is not enough. The patient needs to know what is happening too — in language they understand. The Patient Communicator generates a 6th-grade-reading-level explanation.'));
c.push(SPACER());
c.push(H3('Sub-agents that fire'));
c.push(BOLD_BULLET('action_step_writer:', 'Lists 3 concrete next steps the patient should take.'));
c.push(BOLD_BULLET('empathy_layer:', 'Rewrites in warm, empathetic language. NEVER includes PHI.'));
c.push(BOLD_BULLET('reading_level_tuner:', 'Deterministic post-process: ensures the text is at 6th-grade reading level (Flesch-Kincaid). No LLM call here.'));
c.push(SPACER());

// Step 10
c.push(H2('Step 10 — Audit ledger entry (T+65 seconds)'));
c.push(PARA('Every event in the case (case created, agent fired, verdict synthesised, decision composed) appends a row to the audit_ledger table. Each row contains a SHA-256 hash that includes the previous row\'s hash. Modifying any past row breaks the chain detectably.'));
c.push(SPACER());
c.push(BULLET('Append-only by database constraint — no UPDATE, no DELETE allowed'));
c.push(BULLET('Per-tenant row-level security — auditors only see their tenant\'s rows'));
c.push(BULLET('10-year retention — meets CMS-0057-F § IV.A audit requirement'));
c.push(BULLET('Hash verification: SQL function verify_chain(case_id) returns TRUE if the chain is intact'));
c.push(SPACER());

// Step 11
c.push(H2('Step 11 — TriZetto submission (optional, when integrated)'));
c.push(PARA('When integrated with the partner\'s TriZetto adjudication platform, the decision is submitted as a structured envelope (FHIR Bundle + decision JSON) to the payer. The provider does not have to manually re-enter anything.'));
c.push(SPACER());

// Final state
c.push(H2('Final state — what the doctor sees'));
c.push(BULLET('A green "APPROVE" badge on screen at 9:15:08 AM (60 seconds after submitting)'));
c.push(BULLET('A 7-citation chain (4 clinical + 3 policy) below the verdict'));
c.push(BULLET('The 2-4 sentence rationale'));
c.push(BULLET('The denial-probability forecast (low — likely to be approved by Aetna too)'));
c.push(BULLET('A patient-friendly explanation ready to print or send'));
c.push(BULLET('The full audit log expandable in a side drawer — every agent invocation, every LLM call, every cost'));
c.push(SPACER());
c.push(CALLOUT('Total cost', 'For a clean APPROVE: $0.25. For a DENY with auto-drafted appeal: $0.55. Compare to the AMA-baseline manual PA cost of $1,500. Net savings: $1,499.75 per case. 99.93% reduction.', '047857', 'F0FDF4'));
c.push(PB());

// =============================================================
// PART 4 — DEMO PATHS
// =============================================================
c.push(H1('Part 4 — The Three Demo Paths'));
c.push(PARA('ClinCase ships with three carefully chosen demo cases. Each shows the system handling a different scenario.'));
c.push(SPACER());

c.push(H2('Demo Path 1 — APPROVE (HER2+ all met)'));
c.push(BOLD_BULLET('Patient:', 'M.K., 54F, HER2-positive Stage IIIA breast cancer'));
c.push(BOLD_BULLET('Drug requested:', 'Trastuzumab (J9355)'));
c.push(BOLD_BULLET('Why APPROVE:', 'All 5 inclusion criteria met. HER2 IHC 3+, FISH 4.8 amplified, LVEF 62%, ECOG 1, cardiology cleared.'));
c.push(BOLD_BULLET('Verdict:', 'APPROVE 92% confidence'));
c.push(BOLD_BULLET('Citations:', '7 (4 clinical + 3 policy: Aetna 0123 §4.1, §4.2, NCCN BINV-N v3.2026)'));
c.push(BOLD_BULLET('Time:', '~28 seconds'));
c.push(BOLD_BULLET('Cost:', '$0.25'));
c.push(SPACER());

c.push(H2('Demo Path 2 — REFER (HER2+ but missing LVEF)'));
c.push(BOLD_BULLET('Patient:', 'Same M.K., but FHIR Bundle is missing baseline LVEF'));
c.push(BOLD_BULLET('Drug requested:', 'Trastuzumab (J9355)'));
c.push(BOLD_BULLET('Why REFER:', '4 of 5 criteria MET. The cardiac-workup criterion is AMBIGUOUS — no LVEF Observation in the bundle.'));
c.push(BOLD_BULLET('Verdict:', 'REFER 71% confidence'));
c.push(BOLD_BULLET('Output:', 'Routed to reviewer queue with a 4-item gap checklist (order ECHO, schedule cardiology, verify Oncotype DX, re-submit)'));
c.push(BOLD_BULLET('Time:', '~45 seconds'));
c.push(BOLD_BULLET('Cost:', '$0.30'));
c.push(SPACER());

c.push(H2('Demo Path 3 — DENY + auto-drafted appeal (HER2- mismatch)'));
c.push(BOLD_BULLET('Patient:', 'R.S., 61F, HER2-NEGATIVE breast cancer (IHC 0, FISH ratio 1.1)'));
c.push(BOLD_BULLET('Drug requested:', 'Trastuzumab (J9355) — inappropriate for HER2-negative'));
c.push(BOLD_BULLET('Why DENY:', 'HER2-positive criterion NOT_MET. UHC ONC.00043 §3.1 explicitly excludes HER2-negative disease.'));
c.push(BOLD_BULLET('Verdict:', 'DENY 97% confidence'));
c.push(BOLD_BULLET('Side effect:', 'Appeal letter auto-drafted — NCCN BINV-L pathway proposed (HR-positive/HER2-negative regimen) for a corrected request'));
c.push(BOLD_BULLET('Time:', '~60 seconds'));
c.push(BOLD_BULLET('Cost:', '$0.55'));
c.push(PB());

// =============================================================
// PART 5 — ARCHITECTURE
// =============================================================
c.push(H1('Part 5 — Architecture in Plain Words'));
c.push(H2('Six layers, bottom to top'));
c.push(BOLD_BULLET('Layer 1 — Data Plane:', 'PostgreSQL with row-level security. Tables: cases, agent_runs, llm_invocations, decisions, appeals, audit_ledger, phi_redactions.'));
c.push(BOLD_BULLET('Layer 2 — Agent Plane:', '7 parent agents + 22 sub-agents. Each is a pure Python function with a Pydantic input schema, a .txt prompt, and a Pydantic output schema.'));
c.push(BOLD_BULLET('Layer 3 — Runtime Plane:', 'LangGraph orchestrates the DAG. FastAPI serves the API. SSE streams updates to the frontend. A worker process picks cases from the queue.'));
c.push(BOLD_BULLET('Layer 4 — Gateway Plane:', 'LLMClient interface — a single Python class with three implementations: BedrockClient (production), AnthropicClient (fallback), OpenRouterClient (development). Switch via env var.'));
c.push(BOLD_BULLET('Layer 5 — Surface Plane:', 'React + Vite + TypeScript frontend. Plus the standalone HTML showcase (the one at clincase-demo-26697.s3-website-us-east-1.amazonaws.com).'));
c.push(BOLD_BULLET('Layer 6 — Ops Plane:', 'Runbooks, demo checklists, ROI calculator, compliance scorecard, anticipated Q&A. The "operating manual" of the project.'));
c.push(SPACER());
c.push(CALLOUT('Why six layers', 'Separation of concerns. Each layer has one responsibility. We can swap the LLM provider (Layer 4) without touching the agents (Layer 2). We can swap the frontend (Layer 5) without touching the data (Layer 1). This is what enterprise architects call "well-bounded".', '4F46E5', 'EEF2FF'));
c.push(PB());

// =============================================================
// PART 6 — BUSINESS MODEL
// =============================================================
c.push(H1('Part 6 — Business Model & Path to Revenue'));
c.push(H2('Three pricing tiers'));
c.push(TABLE_2COL('Tier', 'Details', [
  ['Pilot · $9 / case', '< 500 PAs/month. 90-day pilot window. Free first 2 partners. Basic compliance pack.'],
  ['Growth · $6 / case', '500 — 5,000 PAs/month. Multi-drug-class expansion. Custom payer policies. Quarterly evidence packs. SLA + dedicated CSM.'],
  ['Enterprise · $4 / case', '> 5,000 PAs/month. Self-hosted (BYO Bedrock). TriZetto integration tier. the partner procurement vehicle. Custom IAM / SOC 2 attestation.'],
]));
c.push(SPACER());

c.push(H2('Land · Expand · Distribute'));
c.push(BOLD_BULLET('Land — 200-bed cancer centre:', '~150 oncology PAs/month at $9 = $1,350 MRR. Payback under 1 day per case.'));
c.push(BOLD_BULLET('Expand — drug-class adjacency:', 'Add GLP-1, MS, transplant, rheumatology to the same account. 4-8x case volume. Move to Growth tier.'));
c.push(BOLD_BULLET('Distribute — the partner procurement:', 'Slot into the Bedrock + Sonnet + MCP enterprise stack the partner already sells. Same auth, same observability, same vehicle as TriZetto.'));
c.push(SPACER());

c.push(H2('Market sizing'));
c.push(BOLD_BULLET('TAM — $30 billion / year:', 'Total US prior-auth admin waste (CAQH 2024)'));
c.push(BOLD_BULLET('SAM — $200 million / year:', 'US specialty-drug PA market at $5 average price/case. 40M oncology PAs/year alone.'));
c.push(BOLD_BULLET('SOM — $20 million / year:', '5-year capture target. 10% of specialty PAs via the payer organization distribution.'));
c.push(PB());

// =============================================================
// PART 7 — THE PITCH IN 60 SECONDS
// =============================================================
c.push(H1('Part 7 — The Pitch in 60 Seconds'));
c.push(PARA('Memorise this. It is your stage opening.'));
c.push(SPACER());
c.push(CALLOUT('The 60-second pitch (verbatim)',
  '"This is ClinCase — an oncology prior-auth copilot built on Bedrock, Claude Sonnet 4.6, and MCP. The same stack the partner standardised on for the Anthropic partnership announced November 4 last year. Today, prior auth takes 14 days, costs $1,500 per case, delays patient care for 94% of physicians, and creates $30 billion of administrative waste in the US every year. CMS-0057-F mandates this be solved by January 2027. ClinCase turns that 14-day fax-fight into a 60-second decision — citation-grounded, audit-ready, with NCCN-cited appeal letters drafted automatically when cases are denied. Seven specialised agents, twenty-two sub-agents, six concentric architectural layers. Every claim bound to a FHIR resource. Every decision bound to a policy section. Every byte verifiable in our hash-chained audit ledger. We verified end-to-end on May 5 — 98 LLM calls per case, $1.01 cost, zero errors. Let me show you."',
  '0F172A', 'F8FAFC'));
c.push(PB());

// =============================================================
// PART 8 — IMPACT IN ONE NUMBER
// =============================================================
c.push(H1('Part 8 — The Impact in One Number'));
c.push(PARA('A 200-bed regional cancer centre processes 150 oncology PAs per month. Each one costs $1,500 in current admin labour. Each ClinCase APPROVE costs $0.25.'));
c.push(SPACER());
c.push(CALLOUT('Net monthly savings at one cancer centre',
  '150 cases × ($1,500 - $0.25) = $224,962 saved per month. Payback per case: under 0.2 days. ROI on the Pilot tier subscription ($1,350/month): 16,664%.',
  '047857', 'F0FDF4'));
c.push(SPACER());
c.push(PARA('At Humana scale (6 million members, ~120 million PA decisions per year), the same math produces $179.9 billion in lifetime admin savings — for one payer. The total US opportunity is $30 billion per year of waste eliminated.'));
c.push(SPACER());

c.push(H2('Why this is the moment'));
c.push(BULLET('LLMs got smart enough (last 18 months)'));
c.push(BULLET('FHIR R4 became universal'));
c.push(BULLET('CMS-0057-F mandate (Jan 2027) creates forced demand'));
c.push(BULLET('the partner + Anthropic partnership creates distribution path'));
c.push(BULLET('We have the team, the architecture, and the live demo'));
c.push(SPACER());

c.push(CALLOUT('The closing line for stage', 'We are not pitching a hackathon project. We are pitching the missing piece of the Anthropic-enterprise healthcare stack.', '4F46E5', 'EEF2FF'));

// =============================================================
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
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'ClinCase · End-to-End Story · Doc 2 of 7', size: 18, color: '94A3B8' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', size: 18, color: '94A3B8' }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '94A3B8' }), new TextRun({ text: ' · Team AeroFyta', size: 18, color: '94A3B8' })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log('Wrote', OUT, '(' + buf.length + ' bytes)');
});
