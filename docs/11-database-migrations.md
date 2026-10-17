# Database migration history and procedure

## Revision chain

| Revision | Purpose (from migration source) |
| --- | --- |
| `0001_create_users` | Initial user schema. |
| `0002_user_scoped_health` | Health document/chunk/chat schema, ownership constraints and PostgreSQL tenant RLS. |
| `0003_s3_medical_documents` | Medical document metadata for private object storage. |
| `0004_document_processing` | Durable processing jobs/events/stage state and state fields. |
| `0005_deterministic_document_results` | Deterministic extraction results, page/table provenance and constraints. |
| `0006_rag_indexing` | Chunk/index metadata and indexing status. |
| `0007_chat_generation_status` | Records generated/evidence-only answer status. |

Migration code is authoritative; inspect each revision before deployment and compare target revision/schema. A connection working does not prove that the schema is current.

## Safe procedure

1. Take/verify a recoverable database backup under the deployment's established process.
2. Review `alembic history` and `alembic current` against expected target; inspect actual schema and drift using read-only catalog queries.
3. Test the migration on an isolated database restored from a representative schema/backup.
4. Apply `alembic upgrade head` with the dedicated schema migration owner. Do not use the API runtime principal if it is not the migration owner.
5. Verify Alembic revision and expected objects/policies/indexes after applying; deploy application version compatible with the new schema.
6. Record rollback plan. Alembic downgrade scripts may be destructive; do not assume downgrade restores deleted data.

The repository's Alembic env uses `DATABASE_URL`; isolate migration credentials from runtime by setting the migration process environment deliberately. The app lifespan contains no `create_all` or schema DDL. Never reset a shared DB or blindly stamp a revision to bypass drift.

## RLS and runtime role

Review migration policies before deployment. Runtime must not be a superuser, table owner with RLS bypass, or `BYPASSRLS`; it needs only required table/sequence DML. The application sets transaction-local `app.current_user_id` and also uses explicit owner predicates. `tests/conftest.py` uses SQLite `Base.metadata.create_all()` only for isolated temporary test databases; this is not deployment procedure.
