# Qdrant operations

Set `QDRANT_URL`, optional `QDRANT_API_KEY`, and `QDRANT_COLLECTION`. The service creates the collection only when missing, using 384-dimensional cosine vectors by default. Existing collection size is checked before writes; mismatches fail safely. The collection stores deterministic point IDs and payload fields for owner, document, chunk, generation, page, section, and content hash. It does not store report excerpts.

Start a local development instance with `docker run --rm -p 6333:6333 qdrant/qdrant` and set `QDRANT_URL=http://localhost:6333`. Never point tests at a production collection. Point replacement uses upsert. Obsolete point cleanup applies both `user_id` and `document_id` filters and excludes the current point IDs.
