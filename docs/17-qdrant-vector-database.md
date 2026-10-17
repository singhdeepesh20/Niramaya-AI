# Qdrant vector database

The `QdrantStore` class in `app/health/vector_store.py` calls the Qdrant HTTP API. On indexing, it GETs the collection and checks vector size. If the collection is missing, current code creates it using configured dimension and Cosine distance; it does not recreate an existing incompatible collection. This means the worker may perform a cloud collection-creation write on first indexing—provision a disposable/approved collection and permissions intentionally in managed environments.

Point IDs are deterministic chunk UUIDs. Payload includes server-created `user_id`, document/chunk IDs, type/date epoch, page, section, content hash, extraction generation and embedding model; report excerpt text is stored in PostgreSQL, not Qdrant payload. Upsert is followed by scoped obsolete-point deletion (`user_id` AND `document_id`, excluding current IDs). Delete cleanup uses the same owner/document conjunction.

Query filters are built by `qdrant_filter` from authenticated `user.id`, optionally intersecting document types, IDs and dates, plus the model-version condition. The query asks only for chunk IDs. PostgreSQL resolves those IDs under explicit owner, ready/deletion-state and generation constraints before any chunk content is given to the model. A forged or cross-user Qdrant point is therefore not an authorization result.

Live Qdrant auth, collection existence, dimension, latency and point correctness require explicit live checks; mocks do not establish them. Do not use the production collection for tests or initialize it accidentally. See [operations notes](ai/qdrant-operations.md), [threat model](35-threat-model.md), and [indexing recovery](operations/reindexing-and-recovery.md).
