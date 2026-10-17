# Chunking and embeddings

`app/health/indexing.py` combines each current-generation page's extracted text with serialized table rows and entity label/value/unit/range/source excerpts. `chunk_pages` in `app/health/chunking.py` never merges page boundaries. It normalizes horizontal whitespace, removes NULs, recognizes selected standalone section headings, splits around paragraphs/sentences when possible, enforces `CHUNK_SIZE_CHARS`, and overlaps adjacent parts by `CHUNK_OVERLAP_CHARS` (defaults: 1200 and 160 characters).

Chunk UUIDv5 identity is derived from document UUID, extraction generation, chunk order and SHA-256 content hash. That makes retries idempotent for unchanged source; a new generation creates distinct IDs. PostgreSQL stores full chunk text, provenance and hash.

`app/health/embeddings.py` lazily loads `sentence-transformers/all-MiniLM-L6-v2` by default, configured revision/path/device and batch size. It normalizes vectors and checks expected 384-dimensional output. Local weights must already exist unless `EMBEDDING_ALLOW_DOWNLOAD=true`; production should pin a reviewed model revision and provision an offline cache deliberately. Query and indexing code must use the same model/revision/dimension.

Model load, output dimension and embedding failures record safe indexing errors. PostgreSQL chunk persistence is retained on embedding/Qdrant failure, allowing lexical search; semantic recall is unavailable until reindex succeeds. Model changes need compatible collection/vector settings and a controlled reindex plan; do not repurpose incompatible vectors. See [model configuration](ai/embedding-models.md).
