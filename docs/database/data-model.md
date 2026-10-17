# Processing data model

- `medical_documents`: uploaded object metadata, owner, state, generation, and safe processing summary.
- `medical_entities`: deterministic extracted findings with original/normalized values, source excerpt, page, rule, warnings, and generation.
- `medical_document_pages`: extracted page text and OCR status per owner/document/generation.
- `medical_document_tables`: extracted table cells with page/index and generation.
- `document_processing_events`: transition audit with safe reason codes.
- `document_stage_runs`: per-generation stage outcome ledger.
- `document_processing_jobs`: durable transactional outbox and worker lease.

Migration `0002_user_scoped_health` creates the initial health tables and forced RLS policies; `0004_document_processing` adds the job/event/stage ledger and owner policies; `0005_deterministic_results` adds extraction provenance, pages/tables and their policies/FKs/indexes. Migration `0006_rag_indexing` adds chunk provenance and document indexing state; `0007_chat_generation_status` records whether a response was generated or evidence-only. The repository migration chain ends at `0007_chat_generation_status`. App queries also filter by authenticated `user_id` and document ID; database RLS provides defense in depth. Inspect the target database's recorded revision and actual schema before applying migrations. Apply reviewed migrations using the migration owner: `alembic upgrade head`. The runtime role needs appropriate table/sequence grants but must not own the protected tables or bypass RLS.
