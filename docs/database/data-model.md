# Processing data model

- `medical_documents`: uploaded object metadata, owner, state, generation, and safe processing summary.
- `medical_entities`: deterministic extracted findings with original/normalized values, source excerpt, page, rule, warnings, and generation.
- `medical_document_pages`: extracted page text and OCR status per owner/document/generation.
- `medical_document_tables`: extracted table cells with page/index and generation.
- `document_processing_events`: transition audit with safe reason codes.
- `document_stage_runs`: per-generation stage outcome ledger.
- `document_processing_jobs`: durable transactional outbox and worker lease.

Migration `0005_deterministic_results` adds extraction provenance fields, pages/tables, owner/document foreign keys, indexes, and forced row-level security policies. App queries also filter by both authenticated `user_id` and document ID; database RLS provides defense in depth. Apply migrations using the migration owner: `alembic upgrade head`. The runtime role needs appropriate table/sequence grants but must not own the protected tables or bypass RLS.
