# User-scoped retrieval

`user_id` is derived only from `get_current_user`. Request schemas reject extra fields. Server-generated filters include that owner for vector search; PostgreSQL retrieval independently filters chunks and documents by the same owner and checks current generation and non-deleted upload state. RLS transaction context is set for PostgreSQL. The vector database is treated as untrusted: even a malicious cross-tenant point result is discarded unless PostgreSQL authorizes its chunk.

Uploaded text is untrusted evidence, not instructions. The optional generation system prompt forbids tool use, permission changes, and unsupported facts. No raw report text, embeddings, credentials, or provider response body is logged. Document deletion removes only points matching both owner and document; retrieval excludes deletion-pending records even if external cleanup is delayed.
