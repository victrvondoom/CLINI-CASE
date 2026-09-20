# CLINCASE — PITCH SCRIPT
### Team AeroFyta | 10 Minutes
**Live App:** http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com  
**Backend API:** http://clincase-alb-729293716.us-east-1.elb.amazonaws.com  
**Login:** admin@aerofyta.health / clincase2026

---

## DDR HANDOUT DISTRIBUTION PLAN

*Before Danish begins speaking, Sanjay and Gayathri distribute DDR packets to judges. Cue:*  
*"While Danish opens the presentation, please take a moment to glance at the architecture poster and brochure in your hands."*

| Person | Hands out |
|---|---|
| **Sanjay** | `architecture-poster.pdf` + `ClinCase-AeroFyta_Brochure.pdf` |
| **Gayathri** | `compliance-&-trust-one-pager.pdf` + `roi-tam-bm.pdf` + `sample-artifacts-booklet.pdf` |

---

## SEGMENT 1 — PROBLEM STATEMENT
### Speaker: DANISH · 3 minutes · 30% of pitch

**[Emotion: Gravely serious. Slow. Let the numbers land. Make eye contact with each judge. This is the weight of the problem — feel it.]**

Good morning, / and thank you for being here today.

I want to start / not with technology, / but with a patient.

Her name, for privacy, / we'll call her Meera. / She is forty-six years old. / She has Stage III, HER2-positive breast cancer. / Her oncologist, the very same week as her diagnosis, / identifies that she needs Trastuzumab — / a treatment that the NCCN Compendium designates Category One evidence, / meaning the strongest possible clinical mandate that medicine can offer. / Her doctor files for prior authorization on Monday morning.

She waits. / She waits seven days. / Then fourteen days. / Then twenty-one days.

The average treatment delay for oncology prior authorization denials / in the United States / is twenty-seven days — / per a 2023 study published in the Journal of Clinical Oncology. / Twenty-seven days / in which a HER2-positive tumor / does not wait.

This is not a hypothetical. / This is the daily reality / for oncology practices across the country.

Let me give you the scale of this crisis, / because the data is staggering.

The American Medical Association's 2024 Prior Authorization Survey — / a study of over one thousand practicing physicians — / found that each physician spends an average of thirteen hours per week / just on prior authorization paperwork. / That is equivalent to one full working day, every week, / that a trained physician / is not spending with patients.

Thirty-nine prior authorization requests / per physician, / per week. / Ninety-three percent of physicians report that prior authorization causes delays in patient care. / And twenty-nine percent — nearly one in three — / report that PA delays have led to serious adverse events.

*[Pause. Let that sink in.]*

Twenty-nine percent. / A patient harmed / not by their disease, / but by an administrative process.

And yet, / the healthcare industry is spending thirty-five billion dollars annually / on prior authorization administration alone — / that figure is from Sahni et al., published in Health Affairs with McKinsey. / Thirty-five billion dollars / every year / on a process that is slower than it should be, / more error-prone than it should be, / and more costly to everyone than it should be.

Here is the most painful irony. / When denied prior authorizations are appealed, / eighty point seven percent of them are overturned — / per CMS Medicare Advantage data. / Eighty percent. / Which means the original denial was wrong. / But only eleven point seven percent of denials are ever appealed, / because the process is so cumbersome / that most physicians and patients simply give up.

And now, / with CMS-0057-F — / the Prior Authorization API Mandate — / effective January first, twenty-twenty-seven, / every Medicare Advantage and Medicaid payer / is legally required to implement FHIR-native prior authorization APIs / with seventy-two-hour expedited / and seven-day standard decision timelines. / The clock is ticking. / The industry is not ready.

This is the problem / that ClinCase is built to solve.

*[Transition — confident, purposeful. Hand off to Preethi.]*

My colleague Preethi / will now walk you through exactly how we solve it.

---

## SEGMENT 2 — SOLUTION + LIVE DEMO (PART 1)
### Speaker: PREETHI · 2.5 minutes · 30% of pitch

**[Emotion: Confident and warm. You are showing them something they have never seen before. Be proud but measured. Let the demo breathe — don't rush it.]**

Thank you, Danish.

*[Open laptop — navigate to http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com — log in with admin@aerofyta.health / clincase2026]*

What you see on screen right now / is ClinCase — / live, deployed on AWS ECS Fargate, / backed by Amazon S3, / and connected to real AWS Bedrock services. / This is not a mockup. / This is not a prototype. / This is a production-grade, FHIR-native, seven-agent prior authorization copilot / running on the cloud / right now.

Let me show you what it does.

*[Click: "Drop a scan" in the sidebar. Upload the demo PDF: `clincase_demo_refer_oncology_packet.pdf`]*

A physician's coordinator / at a community oncology practice / receives a scan of a patient's prior authorization request packet. / They drag and drop it here. / ClinCase reads it — / using our multi-layer extraction pipeline: / pypdf for text-layer documents, / AWS Textract for scanned images, / and a clinical-content validation gate / that rejects non-clinical uploads / using a sixty-term oncology lexicon.

*[Show the classification result: "typed_print · 85% confidence · engines: pypdf_text"]*

Notice: / the system correctly identifies this as a text-layer PDF, / routes it to the fastest, zero-cost extraction path, / reports eighty-five percent confidence — / above our seventy percent dispatch threshold — / and it is ready to create a case.

*[Click "Create case" — navigate to the new case]*

In a production deployment with Amazon RDS Postgres, / this case feeds into our seven-agent LangGraph DAG. / Each agent — / the Clinical Extractor, / the Policy Retriever, / the Necessity Reasoner, / the Decision Composer, / the Denial Forecaster, / the Appeals Drafter, / and the Patient Communicator — / runs in sequence, / each one building on the structured output of the one before it.

The result / is a verdict — APPROVE, DENY, or REFER — / with a full citation chain, / a confidence score, / and if denied, / an automatically generated NCCN-cited appeal letter / ready for payer submission.

The average time to decision / in our demo cohort / is seventy-six point five seconds. / The AMA median / is eighteen minutes. / That is a ninety-eight percent reduction in administrative cycle time.

*[Navigate to /onco — hand off to Gayathri]*  
*[Sanjay distributes `roi-tam-bm.pdf` to judges at this moment if not yet distributed]*

---

## SEGMENT 3 — UNIQUENESS + ARCHITECTURE + LIVE DEMO (PART 2)
### Speaker: GAYATHRI · 2 minutes · 20% of pitch

**[Emotion: Expert, focused, precise. You are the architect. Speak like you designed every component — because you did. Technical depth but accessible. Judges with 30+ years will appreciate brevity and specificity.]**

*[Screen is on /onco — the Oncology Stack page]*

What makes ClinCase architecturally distinctive / is not that it uses AI — / any system can use AI. / What makes it distinctive / is that it uses AI in a way / that is clinically safe, / legally auditable, / and standards-conformant / from the ground up.

Let me show you two of our ten oncology-specific capabilities.

*[Click USP #1 — OncoGuideline Engine. Type "NSCLC, EGFR L858R, first-line" into the search box. Hit Search.]*

USP one / is our OncoGuideline Engine. / This is a live retrieval-augmented generation query / against our curated NCCN-style guideline corpus. / It has retrieved NSCL-26 — / the NCCN Non-Small Cell Lung Cancer guideline / for EGFR L858R first-line — / Category One evidence, / with the PMID citation to the FLAURA trial. / In production, / this corpus is replaced by the licensed NCCN Compendium feed / indexed through Amazon Bedrock Knowledge Bases / using Amazon Titan Text Embeddings v2.

*[Click USP #10 — Cryptographic Audit Trail]*

USP ten / is our Cryptographic Audit Trail. / Every agent decision / is SHA-256 hashed in a chained structure — / where each record contains the hash of the previous record — / making the audit trail mathematically tamper-evident. / This is the technical implementation of ALCOA-plus-plus — / the FDA and EMA standard for data integrity in GxP-regulated environments — / applied to AI-generated clinical decisions. / When CMS or a state attorney general asks: / "Show me exactly what your AI decided, with what evidence, at what model version, at what timestamp" — / ClinCase produces that record in under two seconds.

At the infrastructure level — / our backend is FastAPI on AWS ECS Fargate — / serverless, autoscaling, zero EC2 instances to manage. / The seven-agent pipeline is orchestrated by LangGraph, / modelled as a directed acyclic graph / with conditional edges — / the Appeals Drafter only runs / if the Decision Composer returns DENY.

Every agent call routes to Claude Sonnet four-point-six / via Amazon Bedrock Converse API — / a provider-agnostic interface / that lets us switch to Claude Opus or Amazon Nova / without changing a single agent prompt.

The FHIR R4 surface exposes Da Vinci PAS version two-point-zero-point-one, / CRD, DTR, / and an X12 278 bridge — / making ClinCase natively conformant to CMS-0057-F / two years before it takes legal effect.

*[Hand off to Sanjay — navigate to /cohorts]*

---

## SEGMENT 4 — BUSINESS IMPACT + SCALABILITY
### Speaker: SANJAY · 2 minutes · 20% of pitch

**[Emotion: Commercially sharp. You are making the business case. Confident but not aggressive. Make the judges see a product they can take to market tomorrow.]**

*[Screen is on /cohorts — Cohort Insights page]*

Thank you, Gayathri.

I want to talk about the market / and why this matters strategically to enterprise healthcare IT providers.

The total addressable market for prior authorization technology / sits at approximately thirty-five billion dollars annually / in administrative spend alone. / But the downstream clinical impact — / the drug revenue unlocked, / the liability avoided, / the Star Rating revenue unlocked by timely authorizations — / takes the serviceable opportunity / well beyond one hundred billion dollars.

*[Point to the Cohorts charts on screen]*

The cohort analytics you see here / represent exactly the kind of data-driven business narrative / that an enterprise payer or provider client needs. / Aetna takes two-point-three times longer than UnitedHealthcare / to approve Stage IIIA breast cancer requests. / ClinCase-drafted appeal letters / achieve an eighty-four percent overturn rate / versus sixty-seven percent for manually drafted appeals. / These are the numbers / that a C-suite payer executive / will immediately recognize / as a cost-reduction opportunity.

For a fifty-physician oncology practice / processing ten thousand prior authorization requests per year, / ClinCase recovers an estimated one-point-nine-five million dollars in denied drug revenue annually / through automated appeal filing — / at a compute cost of under ten cents per case. / That is the kind of ROI / that makes a procurement conversation / very straightforward.

From a scalability standpoint, / ClinCase is built on AWS Fargate — / which scales to zero when idle / and to dozens of concurrent containers during peak authorization windows, / with zero infrastructure management. / Every new payer policy uploaded by a coordinator / automatically re-indexes the RAG corpus / via a Bedrock StartIngestionJob API call / and becomes queryable within minutes.

For payer IT platforms specifically — / the strategic alignment is direct. / The TriZetto product line — / Facets, QNXT, TTAP — / handles claim adjudication downstream of authorization. / ClinCase is not a replacement for TriZetto. / ClinCase is the AI brain / that sits in front of TriZetto — / taking the thirty-nine manual PA requests per physician per week / and reducing them to a supervised-AI workflow / that a coordinator reviews in thirty seconds. / This is a net-new revenue opportunity / for payer-side health-sciences practices, / not a cannibalization risk.

*[Hand off to Danish for Roadmap and Close]*  
*[Gayathri distributes `sample-artifacts-booklet.pdf` to any judge who has not yet received it]*

---

## SEGMENT 5 — ROADMAP + CLOSE
### Speaker: DANISH · 1 minute · back to 30%

**[Emotion: Visionary and warm. This is the close. You are inviting them to join the journey. Calm confidence. Smile as you speak about the future.]**

Thank you, Sanjay.

ClinCase is live today. / The foundation is built. / But we have a clear, phased roadmap for what comes next.

In Phase Two, / we complete the Bedrock Knowledge Base integration / against the licensed NCCN Compendium and ASCO guideline feed, / deploy Amazon RDS Postgres for case persistence, / and run the first real-world pilot / with a community oncology practice.

In Phase Three, / we integrate directly with Epic and Cerner / through SMART on FHIR — / so that the prior authorization workflow is embedded inside the EHR, / invisible to the physician, / seamless for the coordinator.

In Phase Four, / we extend to payer-side deployment — / a white-labeled version of ClinCase's policy reconciliation engine / running inside a payer's own infrastructure, / dramatically accelerating their CMS-0057-F compliance timeline.

The vision / is a future / where no cancer patient / waits twenty-seven days / for a treatment that the NCCN already says she should have.

ClinCase is not just a proof of concept. / It is the beginning of / what we believe can be / the most consequential application of generative AI / in healthcare administration / in this decade.

We are Team AeroFyta. / This is ClinCase. / And we are ready to build it.

*[Pause. Smile. Look at each judge in turn.]*

We welcome your questions.

---

## POST-PITCH: JUDGE Q&A DEMO SUPPORT

**"Show me the full end-to-end flow"**
1. `/intake` → upload clinical PDF → show OCR classification + ClinicalSnapshot → click Create Case
2. `/cases` → click the new case row → show case detail panel → click Run ClinCase
3. `/agents` → View Prompt on Clinical Extractor → Run Contract Test (6/6 checks pass)
4. `/onco` → USP #2 Genomic Auth Agent → upload synthetic FoundationOne report → show EGFR L858R, BRCA1, MSI-H extracted
5. `/policies` → Upload a policy PDF → watch it land in S3 → Delete → moves to Recycle Bin → Restore
6. `/onco` → USP #10 Audit Trail → show SHA-256 chained records with prev_hash linkage

**"Is this CMS-0057-F compliant?"**  
→ `/onco` → USP #4 Da Vinci PAS Native → click "Submit PAS + invoke CRD/DTR" → show FHIR Bundle + auth number + conformance note.

**"What does it cost to run?"**  
→ ~$0.08–$0.12 per case in LLM compute (8K input + 2K output tokens across all seven agents via Claude Sonnet 4.6 on Bedrock). Fargate infrastructure for a 50-physician practice: under $300/month.

**"What's the difference between this and claim adjudication?"**  
→ ClinCase operates pre-claim, on the provider side. It automates the authorization request *submitted by the physician's office* before the drug is dispensed. Claim adjudication happens post-service, on the payer side (TriZetto domain). ClinCase and TriZetto are complementary — not competitors.

**"How do you handle hallucination risk?"**  
→ Every agent output is grounded in a retrieved policy document or NCCN guideline chunk (RAG, not free-form generation). Agents never fabricate clinical facts — if the supporting evidence is absent, the decision routes to REFER + HITL. The cryptographic audit trail records the exact retrieved context and model version for every decision.

---

## GLOSSARY OF DOMAIN TERMS

| Term | Meaning |
|---|---|
| **ALCOA++** | FDA/EMA data integrity standard: Attributable, Legible, Contemporaneous, Original, Accurate + Complete, Consistent, Enduring, Available. Gold standard for GxP audit trail requirements. |
| **GxP** | Good Practice regulations (GMP, GCP, GLP) from FDA, EMA, and ICH — the regulatory framework governing data, process, and system quality in pharma and clinical settings. |
| **CMS-0057-F** | Centers for Medicare & Medicaid Services final rule (effective Jan 17, 2024) mandating FHIR Prior Authorization APIs for Medicare Advantage, Medicaid, and ACA plans by Jan 1, 2027. |
| **Da Vinci PAS** | HL7 Da Vinci Prior Authorization Support implementation guide (v2.0.1) — the FHIR R4 standard for electronic prior authorization exchange between providers and payers. |
| **CRD / DTR** | Coverage Requirements Discovery / Documentation Templates and Rules — Da Vinci FHIR IGs enabling real-time coverage checks and auto-population of PA forms within the EHR. |
| **FHIR R4** | Fast Healthcare Interoperability Resources Release 4 — the HL7 standard for structuring and exchanging clinical and administrative health data. |
| **X12 278** | HIPAA-mandated EDI transaction set for prior authorization requests and responses — the legacy format that CMS-0057-F mandates be bridged to FHIR by 2027. |
| **NCCN Compendium** | National Comprehensive Cancer Network's structured database of oncology drug regimens, cited as authoritative by CMS, most major payers, and the FDA off-label use policy. |
| **LangGraph DAG** | Directed Acyclic Graph orchestration framework for multi-agent LLM workflows, enabling conditional edges, state propagation, and structured agent handoffs. |
| **SMART on FHIR** | Security framework for OAuth 2.0-based EHR app authorization, enabling ClinCase to launch inside Epic/Cerner workflows with patient context pre-loaded. |
| **Bedrock Converse API** | AWS Bedrock's vendor-neutral chat API — same interface for Claude, Amazon Nova, Llama, Mistral — enabling model-agnostic agent design. |
| **RAG** | Retrieval-Augmented Generation — combining vector search over a knowledge corpus with LLM reasoning to produce evidence-grounded, citation-backed outputs. |
| **HITL** | Human-in-the-Loop — the pattern where AI routes low-confidence or high-risk decisions to a qualified human reviewer, satisfying regulatory and liability requirements. |
| **TriZetto** | A healthcare payer IT platform (Facets, QNXT, TTAP) — handles claim adjudication downstream of prior authorization. ClinCase is the upstream complement. |
| **TAM** | Total Addressable Market — the full revenue opportunity available if ClinCase captured 100% of the PA automation market (~$35B administrative spend alone). |
| **ECOG** | Eastern Cooperative Oncology Group performance-status scale (0–5) — a standard measure of a patient's functional status used by payers as an authorization criterion. |
| **HER2 / EGFR / BRCA1** | Oncology biomarkers that determine eligibility for targeted therapies (Trastuzumab, Osimertinib, Olaparib). ClinCase's Genomic Auth Agent extracts these automatically from NGS reports. |
