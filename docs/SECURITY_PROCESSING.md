# Authentication and patient-data processing

Database-backed authentication is authoritative. Missing users receive 401; a database outage receives 503. `AUTH_DBLESS_DEMO_ENABLED=true` enables only the fixed demo identities during an actual database failure, only with `ENVIRONMENT=dev`. It never overrides a healthy database password check or a missing/deleted user. Production/staging reject that flag and require a random `MCP_AUTH_TOKEN` of at least 32 characters, in addition to existing JWT/password checks. Do not use dev mode with patient records.

`CLOUD_DOCUMENT_PROCESSING_ENABLED=false` is the default. Both vision-model OCR and AWS Textract (including the PDF fast path) check it before client/network access. Local PDF text extraction, DOCX/text extraction and Tesseract remain available; missing local OCR or unsuccessful extraction routes to human review. Cloud OCR remains available with explicit deployment opt-in after provider agreements, retention, region and access controls have been approved. This opt-in transmits **unredacted pixels**, not verified anonymous documents. EXIF stripping is not pixel redaction.

Intake audit receipts state the processing policy and `pixel_redaction_verified=false`. OCR confidence and a model-reported redaction count do not prove privacy. Patient data may remain in extraction results and application records; access controls and deployment storage protection are still required.

Clinical extraction prompts now minimize structured FHIR identity fields and replace resource IDs with request-local aliases. Citation IDs are restored only locally after the model returns, preserving evidence traceability. Birth date is converted to age in years. Original local records are unchanged. Clinical codings and measurements remain available. Narrative and attachment identity content is omitted from the model prompt. Clinical extensions and free-text fields still require review: regex screening cannot reliably identify every name, indirect identifier, language, or malformed record. Pattern masks are not a HIPAA de-identification certification or a substitute for approved model-provider data handling. Model training/retention and real-patient approval cannot be established by repository changes.

Intake cache keys include organization and processing-policy mode. Unscoped library calls deliberately do not cache patient material. Cached values are copied to prevent mutations leaking between requests. The existing cache regression now supplies an explicit organization.

Browser SSE uses a fetch-based stream so the JWT remains in an Authorization header. Query-parameter authentication is rejected. The endpoint is tenant-scoped, `no-store`, and `no-referrer`.

Offline regression command: `python -m pytest backend/tests/test_security_privacy.py backend/tests/test_intake_runner.py -q`.
