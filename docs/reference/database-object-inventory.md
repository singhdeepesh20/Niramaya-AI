# Database object inventory

| Object | Definition source | Main columns/role |
| --- | --- | --- |
| `users` | `app/user/models.py`, migration 0001 | UUID identity, normalized login/email, Argon2 hash, active/timestamps. |
| `medical_documents` | `app/health/models.py`, migrations 0002–0006 | Owner, S3 key/metadata, processing + indexing state and generation. |
| `medical_entities` | `app/health/models.py`, migration 0005 | Rule-derived structured findings, provenance and warnings. |
| `medical_document_pages` | same, migration 0005 | Extracted page text/OCR state per generation. |
| `medical_document_tables` | same, migration 0005 | Page-indexed table headers/rows. |
| `medical_document_chunks` | same, migrations 0002/0006 | PostgreSQL canonical chunk text/hash/page/generation/model. |
| `health_chat_messages` | same, migration 0002/0007 | User-scoped question, answer, citations and generation status. |
| `document_processing_events` | `app/documents/models.py`, migration 0004 | Versioned state transition audit rows. |
| `document_stage_runs` | same, migration 0004 | Stage outcome by owner/document/generation. |
| `document_processing_jobs` | same, migration 0004 | Durable process/index/delete outbox jobs and leases. |
| `alembic_version` | Alembic | Applied revision marker; not equivalent to full schema validation. |

RLS policies, indexes, grants, constraints, triggers and exact SQL types must be verified from migrations/catalog on the actual PostgreSQL target. ORM metadata in SQLite tests is not sufficient. See [schema guide](../10-database-schema.md).
