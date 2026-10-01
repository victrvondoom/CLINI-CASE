# Extending one evidence-aware gateway

The demo remains arsenic. Other analytes are not accepted by the current LabSample contract.

Extension sequence: new analyte → authoritative terminology verification → profile/resource mapping → typed validation contract → source adapter → receiver contract → deterministic fixtures/adversarial tests → human review and pilot evaluation.

`app.interop.adapters` defines SourceAdapter, ReceiverAdapter, FHIRAdapter and TerminologyAdapter protocols. SyntheticLabAdapter uses the existing JSON/CSV discovery service; SyntheticClinicalReceiver uses explicit HTTP; OAHFHIRAdapter calls the existing exporter; LocalArsenicTerminology transparently resolves local codes only. Future EHR/environment/research/laboratory implementations can implement these contracts without replacing the clinical engine.

Tenant-scoped PostgreSQL CAS transactions keep artifacts and revision manifests together. Scaling requires indexed job lookup, retention policy, bounded asynchronous transfer workers, idempotent receipts, managed receiver credentials, signature/anchor services and consent notification retries. The current single-record import and synchronous HTTP adapter deliberately favor a reliable demonstration over an unfinished generic integration platform.

Future pilot, **not an existing deployment**: a district health office and accredited laboratory could agree a consent policy and a sample/terminology contract, recruit a small consented household cohort, collect paired environmental/lab reports, and measure missing fields, mapping-review workload, rejection causes and retest completion. Clinical conclusions would remain human-led. No recruited partner, user validation, clinical effectiveness or disease-model accuracy is claimed.
