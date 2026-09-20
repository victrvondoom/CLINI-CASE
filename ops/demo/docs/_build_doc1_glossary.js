/* ============================================================
   DOC 1 — ClinCase Tech Glossary (simple-words definitions)
   ============================================================ */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber, TabStopType, TabStopPosition,
} = require('docx');

const OUT = path.join(__dirname, 'ClinCase_01_Tech_Glossary.docx');
const PAGE = { width: 11906, height: 16838 };  // A4
const MARGIN = { top: 1440, right: 1200, bottom: 1440, left: 1200 };
const CONTENT_W = 9506;
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

// ---------- helpers ----------
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 100, ...opts.spacing },
  alignment: opts.alignment,
  children: [new TextRun({ text, bold: opts.bold, size: opts.size || 22, color: opts.color, italics: opts.italics })],
  ...(opts.heading ? { heading: opts.heading } : {}),
  ...(opts.numbering ? { numbering: opts.numbering } : {}),
});
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 }, children: [new TextRun({ text, bold: true, size: 32, color: '0F172A' })] });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text, bold: true, size: 26, color: '1E293B' })] });
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 80 }, children: [new TextRun({ text, bold: true, size: 22, color: '4F46E5' })] });
const BULLET = (text) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text, size: 22 })] });
const PARA = (text, opts = {}) => new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text, size: 22, ...opts })] });
const SPACER = () => new Paragraph({ spacing: { after: 100 }, children: [new TextRun('')] });

const CALLOUT = (label, body, color = 'EEF2FF') => new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: [CONTENT_W],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: { style: BorderStyle.SINGLE, size: 12, color: '4F46E5' }, bottom: BORDER, left: BORDER, right: BORDER },
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill: color, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 200, right: 200 },
      children: [
        new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: label, bold: true, color: '4F46E5', size: 20 })] }),
        new Paragraph({ children: [new TextRun({ text: body, size: 22 })] }),
      ],
    })],
  })],
});

const TERM = (term, simple, analogy, clincaseUse) => [
  new Paragraph({
    spacing: { before: 220, after: 60 },
    children: [
      new TextRun({ text: term, bold: true, size: 26, color: '0F172A' }),
    ],
  }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'In simple words: ', bold: true, color: '4F46E5', size: 21 }), new TextRun({ text: simple, size: 22 })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'Think of it like: ', bold: true, color: '0891B2', size: 21 }), new TextRun({ text: analogy, italics: true, size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'In ClinCase: ', bold: true, color: '047857', size: 21 }), new TextRun({ text: clincaseUse, size: 22 })] }),
];

// ---------- content ----------
const children = [];

// Title page
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: 'CLINCASE', bold: true, size: 56, color: '4F46E5' })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'Technical Glossary — Every Word, In Simple English', size: 28, color: '475569' })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Document 1 of 7', size: 22, color: '64748B' })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'the 2026 hackathon', size: 22, color: '64748B' })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Team AeroFyta', size: 22, color: '64748B' })] }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// Intro
children.push(H1('How to use this glossary'));
children.push(PARA('Every term is explained three ways:'));
children.push(BULLET('In simple words — what it actually means, no jargon'));
children.push(BULLET('Think of it like — an everyday analogy you can repeat to a non-technical judge'));
children.push(BULLET('In ClinCase — exactly how we use this in our project'));
children.push(SPACER());
children.push(CALLOUT('How to memorise these', 'You do not need to memorise definitions word-for-word. Memorise the analogies. The analogy is what you say when a judge asks "what is X?" The simple definition is your fallback if they push for precision.'));
children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION A — AI / AGENT TERMS
// =============================================================
children.push(H1('Section A — AI and Agent Terms'));

children.push(...TERM('LLM (Large Language Model)',
  'A type of AI that reads text and writes text back. Trained on huge amounts of writing from the internet, books, and code.',
  'A very smart intern who has read every medical textbook, every payer policy, and every clinical guideline. You ask a question, it gives an answer.',
  'ClinCase uses Claude Sonnet 4.6 (a powerful LLM) to read FHIR data + payer policy + NCCN guidelines and decide whether a treatment should be approved.'));

children.push(...TERM('Claude Sonnet 4.6',
  'The specific LLM (made by Anthropic) that ClinCase uses for most reasoning tasks. It is balanced — smart enough for medical reasoning, fast enough for real-time decisions.',
  'The "senior doctor" model in our system. It reads everything carefully and gives the verdict.',
  'All 7 of our parent agents call Sonnet 4.6 through AWS Bedrock. We chose it because the partner standardised on this model in their November 2024 partnership with Anthropic.'));

children.push(...TERM('Claude Haiku 4.5',
  'A smaller, cheaper, faster LLM (also from Anthropic). Used for simple tasks where you do not need full reasoning power.',
  'The "junior nurse" model. Quick simple tasks — sorting, checking, light tagging.',
  'ClinCase uses Haiku for the Grader (which scores other agents\' outputs), the citation_linker, and any quick filtering. Haiku costs 5x less than Sonnet, so we use it where we can.'));

children.push(...TERM('Agent (in AI)',
  'A program that uses an LLM to do a specific job — like one employee with one role. It has a prompt (instructions), tools (things it can do), and outputs.',
  'A specialist employee. The "Clinical Extractor" agent only reads FHIR data. The "Appeals Drafter" only writes appeal letters. Each agent has one job.',
  'ClinCase has 7 parent agents and 22 sub-agents. Each agent does ONE thing well. This is called "bounded responsibility" — same idea as how the partner\'s Neuro-SAN AAOSA pattern works.'));

children.push(...TERM('Sub-agent',
  'An agent that works inside a parent agent. The parent agent splits its job into smaller steps; each sub-agent handles one step.',
  'A doctor (parent agent) might use a lab technician (sub-agent) to run blood tests, then a radiologist (sub-agent) to read X-rays. The doctor combines all results into the diagnosis.',
  'Our Necessity Reasoner (parent) has 3 sub-agents: criterion_splitter (breaks policy into checkable items), evidence_matcher (checks each item against the patient), confidence_calibrator (scores how sure we are).'));

children.push(...TERM('LangGraph',
  'A Python library for connecting multiple agents together as a graph (nodes connected by edges). Each node is an agent or step; the graph defines the flow.',
  'A flowchart engine where each box is an AI agent. The arrows decide what runs next based on the result of the previous step.',
  'ClinCase uses LangGraph to wire up the 7 agents into one pipeline. When a case enters, LangGraph automatically calls Clinical Extractor → Policy Retriever → Necessity Reasoner → Decision Composer in sequence.'));

children.push(...TERM('DAG (Directed Acyclic Graph)',
  'A chart with arrows where arrows only go forward (never loop back to where you came from). "Acyclic" means no cycles.',
  'A relay race. Runner 1 hands the baton to Runner 2, who hands it to Runner 3. Nobody passes back to Runner 1.',
  'Our 7-agent system is a DAG. Cases flow Clinical Extractor → … → Patient Communicator. There are branches (Appeals Drafter only fires on DENY) but no loops back.'));

children.push(...TERM('Prompt',
  'The instruction text given to an LLM telling it what to do. Like a job description for the AI.',
  'A recipe. Same ingredients, different recipes give different dishes. Same LLM, different prompts give different specialised behaviours.',
  'Each ClinCase agent has its own prompt stored as a .txt file in app/prompts/. The Necessity Reasoner prompt teaches the LLM how to check criteria one by one. The Appeals Drafter prompt teaches it to write NCCN-cited letters.'));

children.push(...TERM('System prompt',
  'A specific kind of prompt that defines the AI\'s identity and rules ("you are a clinical reasoner that always cites your sources..."). It applies to the whole conversation.',
  'The job interview where you tell a new employee: "Your title is X. Your rules are Y. Always do Z." After that, every task they do follows these rules.',
  'Every ClinCase agent has a system prompt. For example, the appeals_drafter system prompt says "You never invent clinical facts. You always cite NCCN section numbers."'));

children.push(...TERM('Token',
  'The smallest piece of text an LLM reads or writes. Roughly 1 token = 0.75 words in English.',
  'A LEGO brick. Words and sentences are made of tokens, like models are made of bricks. "Hello world" is 2 tokens. "Trastuzumab" is 4 tokens.',
  'ClinCase pays per token to AWS Bedrock — both for input (what we send) and output (what the LLM writes back). One full ClinCase case costs about $1.01 across 98 LLM calls.'));

children.push(...TERM('Context window',
  'The maximum amount of text an LLM can read at once. Sonnet 4.6 can read up to 200,000 tokens (roughly 150,000 words) in one request.',
  'How much you can stuff into one envelope before mailing it. Bigger envelope = LLM remembers more. Smaller envelope = LLM forgets earlier parts.',
  'ClinCase usually uses 5,000–10,000 tokens per call (well under the limit). The biggest calls — the appeal letter writer — use up to 8,000 tokens output.'));

children.push(...TERM('RAG (Retrieval-Augmented Generation)',
  'A pattern where, instead of asking an LLM directly, you first FETCH relevant documents from a database, THEN give those documents to the LLM with the question.',
  'Open-book exam vs closed-book exam. Closed-book = LLM answers from memory (often wrong). Open-book = LLM answers based on the right page in the textbook in front of it (much more accurate).',
  'ClinCase\'s Policy Retriever agent does RAG. It finds the relevant Aetna / UHC / NCCN policy sections first, then gives them to the Necessity Reasoner. The reasoner does not need to "remember" every policy — it reads them fresh each time.'));

children.push(...TERM('Embedding',
  'A way to turn text into a list of numbers that captures meaning. Two pieces of text with similar meaning have similar number lists.',
  'A "fingerprint" for text. The fingerprint of "heart attack" looks similar to the fingerprint of "myocardial infarction". The fingerprint of "shoe sale" looks completely different.',
  'ClinCase creates embeddings for every payer policy and clinical guideline. When a new case comes in, we make an embedding of the case and find the closest policy embeddings — that is "semantic search".'));

children.push(...TERM('MCP (Model Context Protocol)',
  'A standard way for LLMs to talk to external tools (APIs, databases, files). Created by Anthropic and adopted by the partner.',
  'USB-C for AI. Before MCP, every AI tool had its own connector. Now all tools speak the same language.',
  'ClinCase uses MCP to let our agents call payer APIs, FHIR servers, and the audit ledger in a standard way. It is also part of the "the partner + Anthropic November 2024 partnership stack."'));

children.push(...TERM('Reflection (in agents)',
  'A loop where an agent checks its own output, finds problems, and tries again. Like reading what you wrote and editing it before sending.',
  'A first-draft / second-draft writing process. The agent writes a first draft, a Grader scores it, and if the score is low, the agent retries with the feedback.',
  'ClinCase has reflection on the high-stakes agents — Necessity Reasoner and Appeals Drafter. They self-check before producing the final output.'));

children.push(...TERM('Grader',
  'A small AI that scores another AI\'s output. Used inside reflection loops.',
  'A teacher who marks essays. The student writes, the teacher grades, the student revises if the grade is low.',
  'ClinCase has a Haiku-based Grader that scores every agent output on 4 dimensions: schema correctness, clinical faithfulness, citation completeness, and an overall score. Below 0.80 = retry.'));

children.push(...TERM('Hallucination',
  'When an LLM makes up something that is not true but sounds confident. The single biggest danger of using AI in healthcare.',
  'A confident colleague who gives a wrong answer with a straight face. Sounds right. Is wrong.',
  'ClinCase is built so hallucinations cannot survive. Every clinical claim must cite a FHIR resource ID. Every policy claim must cite a section number. The Grader rejects anything fabricated.'));

children.push(...TERM('Citation',
  'A pointer back to where a fact came from. Lets you verify the claim by going to the source.',
  'A footnote in a school essay. Without it, the teacher cannot check your facts.',
  'ClinCase attaches a citation to every claim. "HER2-positive (Observation/obs-901)" means this fact came from the FHIR resource with ID obs-901. Auditors can pull that resource and verify.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION B — HEALTHCARE TERMS
// =============================================================
children.push(H1('Section B — Healthcare Terms'));

children.push(...TERM('Prior Authorisation (PA)',
  'A process where a doctor must ask the insurance company for permission BEFORE giving expensive treatment. Insurance can approve, deny, or refer for review.',
  'Asking your boss before booking a flight on company credit card. The boss can say yes, no, or "let me check with HR".',
  'ClinCase automates the prior-auth decision in 60 seconds (vs the current 14-day average). This is the entire problem we solve.'));

children.push(...TERM('FHIR (Fast Healthcare Interoperability Resources)',
  'A standard format for medical data. Every patient record, lab result, prescription, etc. has a defined shape so different hospital systems can share data.',
  'JSON for healthcare. Like how all email systems agreed on SMTP, all hospitals are agreeing on FHIR R4.',
  'ClinCase reads FHIR R4 bundles as input. Every claim we make ("HER2-positive", "LVEF 62%") points to a specific FHIR resource ID — that is how we are auditable.'));

children.push(...TERM('FHIR R4',
  'The 4th version of FHIR (released 2019). The version everyone has standardised on. CMS-0057-F mandates FHIR R4.',
  'Like how PDF version matters — most professional tools require PDF/A-2 or higher. FHIR R4 is the equivalent baseline for healthcare data.',
  'ClinCase ingests FHIR R4 only. Older FHIR versions are rejected at the gate by the fhir_resource_validator sub-agent.'));

children.push(...TERM('USCDI (United States Core Data for Interoperability)',
  'A list of the minimum data fields every US hospital must support. Specifies which FHIR resources are mandatory.',
  'The "must-have features" list every smartphone has to ship with — camera, wifi, Bluetooth, etc. USCDI is the same idea for hospital data.',
  'ClinCase supports USCDI v3. Every demo case is USCDI v3 compliant — that is one of our trust badges.'));

children.push(...TERM('NCCN (National Comprehensive Cancer Network)',
  'An organisation that publishes the gold-standard cancer treatment guidelines used worldwide. NCCN guidelines are updated several times a year.',
  'The "official rulebook" for cancer treatment. Every oncologist consults NCCN.',
  'ClinCase cites NCCN guidelines (e.g., "NCCN BINV-N v3.2026") in every appeal letter. That is what makes our appeals defensible.'));

children.push(...TERM('PHI (Protected Health Information)',
  'Any data that can identify a patient — name, date of birth, address, MRN, photos, etc. Protected by HIPAA law in the US.',
  'Like a social security number for medical info. Mishandling it = federal lawsuit.',
  'ClinCase never shows PHI to the LLM. Our PHI Sanitizer strips name/DOB/MRN before any AI call. Only initials propagate.'));

children.push(...TERM('HIPAA',
  'A US federal law that protects patient health information. Every healthcare AI must be HIPAA-compliant.',
  'Like GDPR for European personal data, but specifically for US healthcare data.',
  'ClinCase is HIPAA-compliant by design — PHI never enters LLM prompts, redaction is logged, all access uses BAAs.'));

children.push(...TERM('CMS-0057-F',
  'A US federal rule that takes effect January 2027. Requires payers and providers to support automated, auditable, interoperable prior authorisation.',
  'A new traffic law. Right now, ignoring lane-discipline is a fine. After January 2027, it becomes a felony. Same idea — manual PA is not illegal yet, but the rule changes everything in 2027.',
  'ClinCase maps to all 8 § IV clauses of CMS-0057-F. We are pre-compliant — providers buying us are buying a 2027 mandate solution.'));

children.push(...TERM('LVEF (Left Ventricular Ejection Fraction)',
  'A measure of how well your heart pumps blood. Normal range is 50-70%. Below 50% = weakened heart.',
  'How much blood your heart pumps per heartbeat, as a percentage. Like a car\'s fuel pump efficiency.',
  'In our HER2-positive demo case, LVEF must be ≥50% before trastuzumab (a heart-toxic drug) can be approved. We cite the patient\'s LVEF reading.'));

children.push(...TERM('HER2',
  'A protein on breast cancer cells. Some cancers are HER2-positive (lots of HER2) — these respond to trastuzumab. HER2-negative cancers do not.',
  'A "lock" on cancer cells. The drug trastuzumab is the "key". If the cell has the lock, the key works. If not, the key is useless and dangerous.',
  'Our 3 demo fixtures are all HER2-related: APPROVE (HER2+ all met), REFER (HER2+ but missing LVEF), DENY (HER2- mismatch).'));

children.push(...TERM('Trastuzumab',
  'A targeted cancer drug for HER2-positive breast cancer. Brand name: Herceptin. Code: J9355.',
  'The most expensive drug we discuss. ~$1,500/month. Only works on HER2-positive cancer. That is why prior auth is strict.',
  'All ClinCase demo cases revolve around trastuzumab approval decisions — it is the most-prior-auth\'d cancer drug in the US.'));

children.push(...TERM('IHC / FISH (HER2 testing methods)',
  'Two lab tests that determine if a cancer is HER2-positive. IHC measures protein. FISH counts the gene copies.',
  'Two ways of asking the same question. IHC is "how loud is the speaker?" FISH is "how many speakers are there?"',
  'Our APPROVE case has IHC 3+ (highest score) AND FISH amplified (ratio 4.8) — definitively HER2-positive. The DENY case has IHC 0 + FISH ratio 1.1 — definitively HER2-negative.'));

children.push(...TERM('Payer',
  'The insurance company that pays for healthcare. In the US: Aetna, UnitedHealthcare, Humana, etc. They decide whether to cover treatments.',
  'The bank for medical bills. The doctor delivers the service; the payer pays the bill (or refuses).',
  'ClinCase predicts payer behaviour BEFORE submission. Our Denial Forecaster agent estimates: "Aetna will probably approve this with 75% confidence."'));

children.push(...TERM('Provider',
  'The doctor, hospital, or clinic that treats patients. ClinCase is provider-side software — we work for the doctor.',
  'The doctor\'s tool, not the insurance company\'s tool. Big distinction.',
  'ClinCase is provider-side. Most "AI for prior auth" startups (Notable, Cohere Health) are payer-side. That is our positioning differentiator.'));

children.push(...TERM('TriZetto',
  'A widely-used software platform that payers use to process prior auth requests. Owned by the partner.',
  'The "post office" between providers and payers. ClinCase submits decisions; TriZetto routes them to the payer.',
  'ClinCase sends structured decisions to TriZetto. the partner owns TriZetto, so this is a natural integration.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION C — INFRASTRUCTURE / AWS / CODE TERMS
// =============================================================
children.push(H1('Section C — Infrastructure, AWS, and Code Terms'));

children.push(...TERM('AWS Bedrock',
  'Amazon\'s AI service that hosts foundation models (like Claude). You pay per API call. No need to host your own GPUs.',
  'Like Spotify for AI models. Subscribe, call the API, pay per use. No need to buy your own Marshall stack.',
  'ClinCase calls Claude Sonnet 4.6 via Bedrock. Region: ap-south-1 (Mumbai) — closest to Pune for low latency.'));

children.push(...TERM('AWS Q Business',
  'Amazon\'s enterprise search + RAG service. Indexes documents and answers questions with citations.',
  'Like Google Search but for one company\'s internal documents. With "answer this question" instead of "find these pages".',
  'ClinCase uses Q Business to index payer policies (Aetna, UHC, NCCN) and retrieve the relevant section when a case comes in.'));

children.push(...TERM('ECS Fargate',
  'Amazon\'s container hosting service. You write a Docker container, Fargate runs it, no servers to manage.',
  'Like AirBnB for code. You bring the container (your suitcase), Amazon hosts it (the apartment), no need to own the building.',
  'ClinCase\'s FastAPI backend runs on ECS Fargate. Auto-scales with traffic.'));

children.push(...TERM('RDS Postgres',
  'Amazon-managed PostgreSQL database. Backups, replication, security all handled by AWS.',
  'A "managed restaurant" — same recipes (Postgres), but Amazon handles maintenance, ingredients, repairs.',
  'ClinCase stores cases, decisions, agent runs, audit ledger, and PHI redactions in RDS Postgres with row-level security.'));

children.push(...TERM('KMS (Key Management Service)',
  'Amazon service that creates and manages encryption keys. You never see the actual key — AWS uses it on your behalf.',
  'A safety deposit box for your house keys. The bank never gives you the key — they unlock the box for you when you ask.',
  'ClinCase uses KMS to encrypt all stored data. Audit ledger entries are signed using KMS keys.'));

children.push(...TERM('CloudWatch',
  'Amazon\'s monitoring and logging service. Tracks errors, performance, costs.',
  'A car dashboard. Speed, fuel, warning lights. Tells you when something is wrong.',
  'ClinCase sends every agent run trace and LLM cost to CloudWatch. We can see if the system is slow or failing in real-time.'));

children.push(...TERM('IAM (Identity and Access Management)',
  'Amazon\'s permissions system. Controls who/what can access what.',
  'Like the keycards in an office. Some keycards open all doors, some only one floor. IAM defines all the keycards.',
  'ClinCase uses IAM roles for its ECS workers (only the agents can call Bedrock; only the audit service can write the ledger).'));

children.push(...TERM('VPC (Virtual Private Cloud)',
  'A private network on AWS. Like having your own data centre, but virtual.',
  'A gated community inside AWS. Your stuff is inside, the public internet is outside, gates control traffic.',
  'ClinCase runs entirely inside a VPC. Only the API gateway is exposed to the internet — Bedrock calls go through VPC endpoints (private).'));

children.push(...TERM('FastAPI',
  'A Python web framework for building APIs. Modern, fast, automatic documentation.',
  'Like Express.js for Node, but for Python. The standard for building REST APIs in Python.',
  'ClinCase backend is built on FastAPI. Endpoints like POST /cases/run-async and GET /cases/{id}/stream are FastAPI routes.'));

children.push(...TERM('Pydantic',
  'A Python library for defining data shapes (schemas) with type hints. Validates data automatically.',
  'A bouncer at a club. "You must be over 21 (must be int), wear a shirt (must be string), have ID (must not be null)". If anything fails, you do not get in.',
  'Every ClinCase agent has Pydantic input/output schemas. Bad data is rejected at the door — never reaches the LLM.'));

children.push(...TERM('Pydantic v2',
  'The 2023+ rewrite of Pydantic. Faster (Rust-backed), stricter, more features.',
  'Pydantic 1 = a sedan. Pydantic 2 = the same car but with a turbo engine.',
  'ClinCase uses Pydantic v2 throughout. It is fast enough that schema validation does not slow us down.'));

children.push(...TERM('SSE (Server-Sent Events)',
  'A way for a server to push live updates to a browser. Like a one-way live broadcast.',
  'A radio station. The station broadcasts; you listen. You cannot talk back through the same channel.',
  'ClinCase streams agent updates over SSE. When you click "Run ClinCase", the browser sees each agent fire in real-time.'));

children.push(...TERM('JWT (JSON Web Token)',
  'A signed string that proves who a user is. Sent with every API request after login.',
  'Like a wristband at a music festival. You get it once at the gate; every bar/stage just checks the wristband.',
  'ClinCase login returns a JWT. Every subsequent API call includes that JWT to prove you are logged in.'));

children.push(...TERM('Row-Level Security (RLS)',
  'A database feature where users can only see rows that belong to them — enforced at the database level, not in app code.',
  'A library where every book has a "members can read" sticker, but some only have "Member 47 can read". The library shelves enforce who reads what.',
  'ClinCase uses Postgres RLS. Tenant A\'s queries cannot see Tenant B\'s cases — the database refuses, even if app code has bugs.'));

children.push(...TERM('Hash chain (audit ledger)',
  'A chain of records where each record contains the cryptographic hash of the previous one. Editing any past record breaks the chain — detectable.',
  'A chain of envelopes where each envelope has the wax seal from the previous one inside. Open and re-seal any past envelope = the chain shows it.',
  'ClinCase\'s audit_ledger table is hash-chained. Auditors can verify the entire chain in <1 second with a SQL function.'));

children.push(...TERM('SHA-256',
  'A specific hash function. Takes any input, outputs a 64-character "fingerprint". Used in our hash chain.',
  'A super-detailed fingerprint scanner. Slightly different inputs produce completely different outputs. No two inputs ever produce the same output.',
  'ClinCase uses SHA-256 for the audit ledger chain. Bitcoin uses the same algorithm for its blockchain.'));

children.push(...TERM('Docker / container',
  'A way to package code with all its dependencies into one shippable unit. Runs identically on dev laptop and AWS.',
  'A shipping container. Same metal box whether on a ship, train, or truck. The contents (code + libraries) ship together as one.',
  'ClinCase backend ships as a Docker container. We push it to AWS ECS Fargate, and the same container runs in production.'));

children.push(...TERM('CI/CD (Continuous Integration / Continuous Deployment)',
  'An automated pipeline: code is pushed to git → tests run → if green, deploy to production.',
  'A factory assembly line. Code goes in one end; production-ready system comes out the other. No human in between.',
  'ClinCase uses GitHub Actions for CI/CD. Every commit runs tests; passing commits to main deploy to staging.'));

children.push(...TERM('Async / await',
  'A Python pattern for code that can wait for slow operations (network calls, database queries) without blocking the whole program.',
  'In a coffee shop, the cashier takes your order, then takes the next person\'s order while the barista makes drinks. They do not wait for you to receive your latte.',
  'ClinCase backend is async-throughout. Multiple agents can be waiting for LLM responses at the same time without slowing each other down.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION D — FRONTEND TERMS
// =============================================================
children.push(H1('Section D — Frontend Terms'));

children.push(...TERM('React',
  'A JavaScript library for building user interfaces. Most modern web apps are built with React.',
  'Like LEGO for websites. You build small components (buttons, cards) and combine them into big screens.',
  'ClinCase frontend is built with React 18. Each page (Dashboard, Case Detail, Architecture) is a React component.'));

children.push(...TERM('TypeScript',
  'JavaScript with types. Catches errors at write-time instead of run-time.',
  'JavaScript with the spell-checker turned on. Mistyped a variable name? TypeScript tells you before you ship.',
  'ClinCase frontend is TypeScript-strict. No "any" types allowed. Every API call has typed inputs and outputs.'));

children.push(...TERM('Vite',
  'A modern web app build tool. Replaces older tools like webpack. Much faster.',
  'Like upgrading from a flip phone to a smartphone. Same job, much better experience.',
  'ClinCase uses Vite to build the React app. Hot reload in <100ms during development.'));

children.push(...TERM('Tailwind CSS',
  'A CSS framework where you style elements with utility class names instead of writing custom CSS.',
  'Building with pre-cut LEGO pieces (e.g., "padding-large", "rounded-corner") instead of carving custom wood.',
  'All ClinCase UI is styled with Tailwind. The standalone HTML demo and the React app use the same tokens (colors, fonts, spacing).'));

children.push(...TERM('Component (in React)',
  'A reusable UI element with its own logic. Examples: a button, a card, a modal.',
  'A custom widget you make once and use 100 times. Like a "favourite quote" template you reuse across docs.',
  'ClinCase has 36 components in src/components/ — AppShell, AgentCard, CitationChip, DecisionBadge, etc.'));

children.push(...TERM('Hash routing',
  'A way to handle URLs like #/cases/abc — the part after the # changes the page without reloading.',
  'Bookmarks within one document, vs going to a different document. Faster, no server round-trip.',
  'The standalone ClinCase.html uses hash routing. URL like clincase-demo-26697.s3-website-us-east-1.amazonaws.com/#/agents goes to the agents page without a full reload.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION E — PARTNER-SPECIFIC TERMS
// =============================================================
children.push(H1('Section E — Partner-Specific Terms'));

children.push(...TERM('Neuro-SAN AAOSA',
  'the partner\'s naming for their preferred multi-agent design pattern. Stands for "Adaptive Agentic Orchestration Software Architecture".',
  'A design philosophy: bounded responsibility, stateful continuity, per-tenant adaptation, observable everything. the partner tells clients: "build agents this way".',
  'ClinCase\'s 7-agent DAG follows Neuro-SAN AAOSA principles exactly. We name-drop this in our architecture poster — it tells judges we read the partner\'s playbook.'));

children.push(...TERM('the Agent Foundry',
  'the partner\'s platform for building, evaluating, and deploying AI agents. Includes manifests, model cards, observability.',
  'An "agent factory" — the same way a car factory has a standard production line, the Foundry has a standard agent production line.',
  'ClinCase is Foundry-compatible. Our manifest, evaluation harness, and observability all match the Foundry expectations.'));

children.push(...TERM('the payer organization',
  'The healthcare-vertical division of the partner. They serve 47 of the top 50 US payers and 200+ providers.',
  'The healthcare team inside the partner. ClinCase\'s natural distribution channel.',
  'Our go-to-market is "via the payer organization". They already sell to all our target customers.'));

children.push(...TERM('Anthropic-enterprise partnership (November 4, 2024)',
  'the partner officially partnered with Anthropic in November 2024 to standardise on Claude + Bedrock + MCP for enterprise AI.',
  'the partner\'s "official AI stack" announcement. If you build on this stack, you are pushing on an unlocked door.',
  'ClinCase is built on EXACTLY this stack: Bedrock + Claude Sonnet 4.6 + MCP. We are not asking the partner to adopt new tech — we already use theirs.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// =============================================================
// SECTION F — JUDGE-FACING ANALOGIES (memorise these!)
// =============================================================
children.push(H1('Section F — Killer Analogies (memorise these for Q&A)'));
children.push(PARA('When a judge asks "explain X", these analogies are your one-liner answers. They are tuned for both technical and non-technical judges.', { italics: true }));
children.push(SPACER());

const ANALOGY = (q, a) => [
  new Paragraph({ spacing: { before: 160, after: 60 }, children: [new TextRun({ text: 'Q: ' + q, bold: true, color: '0F172A', size: 23 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'A: ' + a, size: 22, color: '1E293B' })] }),
];

children.push(...ANALOGY('What is ClinCase?',
  'A doctor\'s assistant powered by 7 specialised AI agents. It reads patient data + insurance policy and decides whether the treatment will be approved — in 60 seconds, with citations, fully audit-ready.'));

children.push(...ANALOGY('Why 7 agents instead of 1?',
  'Same reason a hospital has separate doctors, radiologists, pharmacists, and billing — each role needs different training. One mega-LLM trying to do everything makes mistakes; 7 specialised agents each do one thing well.'));

children.push(...ANALOGY('How is this different from ChatGPT-style AI?',
  'ChatGPT can hallucinate facts. ClinCase cannot — every claim is bound to a FHIR resource ID or an NCCN section number. If we cannot cite it, we do not say it.'));

children.push(...ANALOGY('What happens if the AI is wrong?',
  'Three layers of defense. (1) The Grader scores every output and rejects below-threshold ones. (2) Low-confidence cases get REFER, which routes to a human reviewer. (3) Every claim has a citation — if the citation does not match the data, the human reviewer sees it instantly.'));

children.push(...ANALOGY('Why prior auth specifically?',
  'It is the perfect target — universally hated, $30B in admin waste, mandated to be solved by January 2027 (CMS-0057-F), and structurally simple (rule + evidence = decision). Cancer-specific because oncology has the most complex policies and the highest stakes.'));

children.push(...ANALOGY('Who pays for this?',
  'Hospital systems and oncology practices. Per-case fee, $9 in pilot tier dropping to $4 in enterprise tier. A 200-bed cancer center saves $225,000/month — payback under 1 day per case.'));

children.push(...ANALOGY('How does this fit the partner?',
  'We are built on the EXACT stack the partner standardised on in November 2024 — Bedrock + Claude Sonnet + MCP. the payer organization sells to 47 of the top 50 US payers — they have a natural distribution path. We are not asking them to adopt new tech; we use theirs.'));

children.push(...ANALOGY('Is this real or just slides?',
  'Real. Run the QR code on the brochure — that is our live interactive demo running on clincase-demo-26697.s3-website-us-east-1.amazonaws.com. We have an audit log of 98 LLM calls per case proving the pipeline runs end-to-end.'));

children.push(...ANALOGY('What about HIPAA / patient privacy?',
  'PHI never enters the LLM prompt. Our PHI Sanitizer runs BEFORE the first LLM call — name, DOB, MRN are stripped. Only patient initials propagate. The architecture makes leaks structurally impossible, not policy-prevented.'));

children.push(...ANALOGY('Why won\'t this be replaced by GPT-5 or whatever comes next?',
  'ClinCase is not an LLM. ClinCase is an architecture — the citation system, the audit ledger, the FHIR ingestion, the policy retrieval. The LLM is a swappable component. When Sonnet 5 ships, we update one config line and inherit the improvement.'));

// =============================================================
// FOOTER MESSAGE
// =============================================================
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1('That\'s it. You know every term ClinCase uses.'));
children.push(PARA('Memorise the analogies in Section F first. Then skim Sections A-E once. By demo day, you will be able to define every term in 10 seconds.'));
children.push(SPACER());
children.push(CALLOUT('One last tip', 'When a judge asks a tough technical question, START with the analogy from Section F. Then the simple definition. Then the ClinCase-specific use. Three layers, 30 seconds, complete answer.'));

// ---------- assemble ----------
const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, font: 'Calibri', color: '0F172A' }, paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, font: 'Calibri', color: '1E293B' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, font: 'Calibri', color: '4F46E5' }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: PAGE, margin: MARGIN } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'ClinCase · Tech Glossary · Doc 1 of 7', size: 18, color: '94A3B8' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', size: 18, color: '94A3B8' }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '94A3B8' }), new TextRun({ text: ' · Team AeroFyta · the 2026 hackathon', size: 18, color: '94A3B8' })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log('Wrote', OUT, '(' + buf.length + ' bytes)');
});
