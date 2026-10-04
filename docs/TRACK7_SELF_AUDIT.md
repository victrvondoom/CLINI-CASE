# Track 7 self-audit

The criteria recorded in the October 2 rules review are Impact 30%, Innovation 20%, Technical execution 20%, UX 15%, Scalability 15% ([rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules)). A development team cannot assign itself a credible guaranteed 8/10 or 9/10 judge score. The following evidence addresses the identified weaknesses. Implementation status below was refreshed on **2026-10-04**; the historical [October 1 verification report](TRACK7_HARDENING_VERIFICATION.md) remains a dated record.

| Criterion | Implemented evidence | Remaining gap |
|---|---|---|
| Impact | Named synthetic household story; lab-to-review-to-retest loop; explicit consent withdrawal | No real pilot or measured health outcome |
| Innovation | Evidence Passport, computed epistemic ceiling, six evidence gates preserved across exchange; optional Ed25519 demo-system signing with content-tamper and wrong-key rejection | No institutional laboratory signature or externally anchored ledger; signature availability depends on configuration |
| Technical execution | Persistent PostgreSQL/CAS records; independent HTTP receiver; bidirectional exchange; actual rejection; restart/tamper/tenant tests; recorded official validator results; October 4 synthetic NVIDIA connectivity probe passed | One-sample validator evidence is not full conformance; connectivity is not a live seven-agent or clinical-performance evaluation |
| UX | OneHealth front door; simple/expert gateway; real acknowledgements, failures and metrics | Judge usability study not conducted |
| Scalability | Narrow source/receiver/FHIR/terminology adapter interfaces; tenant isolation | One arsenic-focused integration, no production load or multi-site deployment claim |

**Scope:** one evidence-aware One Health product with retained platform capabilities. AquaHealth supplies observations, OneHealth controls evidence, the gateway exchanges it, OncoTwin/CardioTwin show consented context, and ClinCase links explicitly attested cases. Environmental observations never change disease-model inputs or clinical authorization conclusions.

**Originality:** the build-scope document distinguishes reused code from this phase and exposes Oct 1 additions. History is preserved.

**Hygiene:** tracked duplicate frontends, backup assets and machine-specific scripts were moved into an archive, not deleted. No public default password is seeded by default. The license remains unchanged and AI assistance is disclosed.

**Standards:** local PASS is separate from the official validator result (October 2 synthetic sample: 0 errors, warnings reported in full, see [VALIDATION.md](track7/VALIDATION.md)). The October 4 audit confirmed the retained input hash and the fresh exporter structure; it did not rerun the official validator. Synthetic model AUROC is not the submission headline.

**AI provider:** the current OpenAI-compatible client can target NVIDIA through
`OPENROUTER_BASE_URL=https://integrate.api.nvidia.com/v1`. A synthetic connectivity probe on
October 4 succeeded with `nvidia/nemotron-3-super-120b-a12b` (48 input tokens, 6 output tokens).
This supersedes the older rejected-credential status for connectivity only. The deterministic
Track 7 path still calls no model. Governed schema suggestions remain optional, require
PostgreSQL quota/audit support when the gateway is enabled, and cannot approve meaning or
select arsenic speciation. A successful provider probe does not prove all seven clinical
agents completed a live case. No key or patient data is included in this evidence.

**Clinical safety:** every AI-proposed DENY is held for authenticated human review regardless
of confidence. Draft appeal/patient documents remain visible while pending; Vercel review
continuation can execute inline with bounded runtime and fenced retry. See
[upload and review repair evidence](ONCOLOGY_UPLOAD_REVIEW_REPAIR.md).

WHO estimates roughly 140 million people in at least 70 countries have consumed drinking water above its provisional arsenic guideline; this establishes problem relevance, not this prototype's impact ([WHO arsenic fact sheet](https://www.who.int/news-room/fact-sheets/detail/arsenic)).
