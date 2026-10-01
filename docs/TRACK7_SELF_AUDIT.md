# Track 7 self-audit

The official criteria are Impact 30%, Innovation 20%, Technical execution 20%, UX 15%, Scalability 15% ([rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules)). A development team cannot assign itself a credible guaranteed 8/10 or 9/10 judge score. The following evidence addresses the identified weaknesses.

| Criterion | Implemented evidence | Remaining gap |
|---|---|---|
| Impact | Named synthetic household story; lab-to-review-to-retest loop; explicit consent withdrawal | No real pilot or measured health outcome |
| Innovation | Evidence Passport, computed epistemic ceiling, six evidence gates preserved across exchange | Hash chain has no external signature/anchor |
| Technical execution | Persistent PostgreSQL/CAS records; independent HTTP receiver; bidirectional exchange; actual rejection; restart/tamper/tenant tests | Live provider credential rejected; full draft IG validation incomplete |
| UX | OneHealth front door; simple/expert gateway; real acknowledgements, failures and metrics | Judge usability study not conducted |
| Scalability | Narrow source/receiver/FHIR/terminology adapter interfaces; tenant isolation | One arsenic-focused integration, no production load or multi-site deployment claim |

**Scope:** one evidence-aware One Health product with retained platform capabilities. AquaHealth supplies observations, OneHealth controls evidence, the gateway exchanges it, OncoTwin/CardioTwin show consented context, and ClinCase links explicitly attested cases. Environmental observations never change disease-model inputs or clinical authorization conclusions.

**Originality:** the build-scope document distinguishes reused code from this phase and exposes Oct 1 additions. History is preserved.

**Hygiene:** tracked duplicate frontends, backup assets and machine-specific scripts were moved into an archive, not deleted. No public default password is seeded by default. The license remains unchanged and AI assistance is disclosed.

**Standards:** local PASS is separate from official validator WARNING and terminology NOT_TESTED. Synthetic model AUROC is not the submission headline.

WHO estimates roughly 140 million people in at least 70 countries have consumed drinking water above its provisional arsenic guideline; this establishes problem relevance, not this prototype's impact ([WHO arsenic fact sheet](https://www.who.int/news-room/fact-sheets/detail/arsenic)).
