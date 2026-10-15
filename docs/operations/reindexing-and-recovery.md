# Reindexing and recovery

Check `GET /api/v1/documents/{id}/indexing-status`; it is separate from extraction status. `POST /api/v1/documents/{id}/reindex` creates a durable indexing-only job and does not repeat PDF extraction. Run the existing worker with `python -m app.documents.worker` (see repository worker entry point/deployment configuration) after the API and database are ready.

Failures are reported using safe categories such as `embedding_model_unavailable`, `qdrant_unavailable`, or `qdrant_dimension_mismatch`. Reindexing safely repeats deterministic upserts. Existing vectors are never deleted to fix a dimension mismatch. Configure a new collection for a new embedding model, then explicitly reindex documents. A failure in obsolete-point cleanup is retryable; PostgreSQL authorization prevents stale or unauthorized points from becoming evidence.
