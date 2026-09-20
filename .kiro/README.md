# ClinCase — `.kiro/specs/` index

This directory is the Kiro-IDE-compatible specification of every ClinCase
agent. The tree is **generated** from `app.agents.manifest.AGENT_MANIFEST`;
do not edit by hand. Re-run:

```bash
python -m app.integrations.kiro.exporter
# or
curl -XPOST localhost:8000/api/v1/integrations/kiro/export -H "Authorization: Bearer ..."
```

## Structure

```
.kiro/
├── README.md                  ← this file
└── specs/
    ├── <parent>/
    │   ├── requirements.md   ← EARS acceptance criteria + user stories
    │   ├── design.md         ← schemas, lifecycle, guardrails
    │   ├── tasks.md          ← checkable build steps
    │   └── sub_agents/
    │       └── <sub>/
    │           ├── requirements.md
    │           ├── design.md
    │           └── tasks.md
    └── ...
```

## Inventory

- **7 parent agents** (LangGraph nodes)
- **21 sub-agents** (15 LLM-backed · 6 deterministic)
- **3 reflection-enabled** sub-agents (quality_threshold > 0)

- `appeals_drafter` — On DENY: drafts a NCCN-citing formal appeal letter + structured arguments JSON f
  - `appeals_drafter.counter_evidence_finder`
  - `appeals_drafter.nccn_reference_specialist`
  - `appeals_drafter.letter_composer`
- `clinical_extractor` — Parses FHIR R4 bundle + physician note into a strictly-typed ClinicalSnapshot. P
  - `clinical_extractor.fhir_resource_validator`
  - `clinical_extractor.phi_sanitizer`
  - `clinical_extractor.biomarker_specialist`
- `decision_composer` — Deterministic verdict + LLM-written rationale + LLM-validated citation chain.
  - `decision_composer.verdict_synthesizer`
  - `decision_composer.rationale_writer`
  - `decision_composer.citation_linker`
- `denial_forecaster` — Predicts the *payer's* denial probability + top likely reasons + recommended app
  - `denial_forecaster.probability_estimator`
  - `denial_forecaster.reason_predictor`
  - `denial_forecaster.appeal_path_recommender`
- `necessity_reasoner` — Per-criterion MET/NOT_MET/AMBIGUOUS evaluation with calibrated confidence. Paral
  - `necessity_reasoner.criterion_splitter`
  - `necessity_reasoner.evidence_matcher`
  - `necessity_reasoner.confidence_calibrator`
- `patient_communicator` — Produces a 6th-grade-reading-level patient-facing summary + concrete next-step a
  - `patient_communicator.empathy_layer`
  - `patient_communicator.reading_level_tuner`
  - `patient_communicator.action_step_writer`
- `policy_retriever` — Fetches the top-5 payer-specific PA policy sections relevant to this case from t
  - `policy_retriever.keyword_filter`
  - `policy_retriever.llm_reranker`
  - `policy_retriever.citation_resolver`

## How Kiro picks this up

1. Place `.kiro/specs/` at repo root (already done by exporter).
2. Open repo in Kiro IDE.
3. Kiro auto-loads specs and surfaces them in the side panel.
4. Edit a `requirements.md`; the Hook regenerates the corresponding agent
   skeleton in `backend/app/agents/...`.
5. Commit. The CI Hook validates each spec against the live
   `AGENT_MANIFEST` and fails the build if drift is detected.

> Why this matters: Kiro's published healthcare references to date are
> life-sciences (the "3-week drug discovery agent" AWS post). ClinCase
> publishes 28 specs in one repo — the first comprehensive PA-domain
> Kiro reference.
