# Architecture decisions (reconstructed)

No original ADR history was found in the repository. The rationales below are reconstructed from current code and are not claims about the original authors' intent.

Individual records are indexed in [`decisions/`](decisions/README.md).

## ADR-001: PostgreSQL is the canonical structured store

- **Context:** accounts, owner-linked documents, extractions, chunk text and histories need transactional queries.
- **Observed decision:** async SQLAlchemy models with Alembic; PostgreSQL RLS and owner filters; a SQLite test adapter.
- **Alternatives:** not recoverable from repository history.
- **Trade-offs:** strong relational constraints and transactions; production must operate migrations, backups and RLS roles correctly. SQLite tests cannot validate PostgreSQL policy behavior.
- **Status:** implemented; live schema correctness depends on deployment migration state.

## ADR-002: S3 stores source bytes, PostgreSQL stores object references

- **Observed decision:** generated `users/{user_id}/documents/{uuid}` keys, private upload/download operations, presigned GET URLs, metadata rows.
- **Trade-offs:** object and relational changes are not one distributed transaction; upload cleanup and delete jobs compensate for partial failures.
- **Status:** implemented; AWS permissions and bucket configuration require live verification.

## ADR-003: Deterministic extraction precedes optional generative Q&A

- **Observed decision:** PyMuPDF/Tesseract/rule-based parsing persists facts and provenance without LLM. Q&A is a distinct optional service.
- **Trade-offs:** predictable local rules and provenance but bounded coverage; new report formats require tested rules.
- **Status:** implemented and synthetic-tested; not clinical validation.

## ADR-004: Qdrant is a rebuildable candidate index

- **Observed decision:** local embeddings are indexed in Qdrant, but chunk content and ownership truth stay in PostgreSQL. Candidate IDs are re-resolved through owner-scoped SQL.
- **Trade-offs:** duplicated vector metadata and cross-service cleanup complexity; safer authorization boundary and lexical fallback.
- **Status:** code and fake-client tests exist; live Qdrant behavior is environment-dependent.

## ADR-005: PostgreSQL outbox and leases coordinate background work

- **Observed decision:** upload metadata and process job commit together; workers claim rows with locking, bounded retry and stale-lease recovery.
- **Trade-offs:** avoids a separate broker but the polling worker and relational DB become queue throughput dependencies.
- **Status:** implemented; horizontal production operation needs load/locking validation.
