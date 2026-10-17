# Requirements and scope

This page records requirements that can be inferred from the implemented contracts. It does not assert a product specification or regulatory assessment absent from the repository.

## Implemented functional scope

- Normalize usernames/emails and create active accounts; hash passwords and issue expiring bearer tokens.
- Store supported document originals in configured S3 and metadata/jobs in PostgreSQL.
- Limit upload type to PDF/JPEG/PNG, verify signature and request size, and reject unsupported media.
- Extract page text and tables from PDF; use local OCR for low-text pages when enabled and available; run explicit classification and extraction rules.
- Preserve provenance, page, generation, parser warnings and review state.
- Serve owner-scoped document metadata, results, status, history, presigned viewing/download, reprocess/reindex, review completion and deletion.
- Retrieve lexical and optional vector candidates using server-derived ownership; produce evidence/citations and optionally call an LLM.

## Non-functional/security requirements visible in code

- DB access is asynchronous; PostgreSQL connection attempts have a five-second connect timeout.
- Startup does not run schema DDL; Alembic owns schema changes.
- JWT signing material is required and validated as a high-entropy value length of at least 32 bytes.
- Cross-origin browser access uses explicit configured origins; credentials are not enabled on CORS.
- Sensitive provider exceptions are reduced to error categories/types in logs and public errors are generic.
- Source S3 keys are opaque/server generated and bucket privacy settings are never changed by the app.
- RAG retrieval requires a JWT-derived owner filter in Qdrant and independent owner checks in PostgreSQL.

## Scope limits and open product questions

- The parser's alias and section catalogue is explicit and finite; unsupported formats and labels need review/extension.
- No diagnosis, treatment recommendation, clinical reference-range interpretation, or medical validation is implemented.
- No account deletion endpoint, self-service password reset, email verification, refresh token, or admin workflow is present in registered routes.
- Recovery/retention periods, user consent language, data residency, encryption-key ownership and audit retention are deployment/product decisions not established by code.
- User deletion and full cross-service erasure are not exposed as a workflow.
- No checked-in production deployment, backup, restore or monitoring automation exists.
- Regulatory compliance is not established by this code or documentation.
