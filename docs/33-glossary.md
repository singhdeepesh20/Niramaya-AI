# Glossary

| Term | Meaning here |
| --- | --- |
| API | HTTP interface provided by FastAPI. |
| Bearer token | Access token presented in the Authorization header; possession grants its claims' API access until expiry. |
| Chunk | Page-local bounded passage of extracted content used for lexical/vector retrieval. |
| Citation | Backend-built document identity/name and optional source page for returned evidence. |
| Embedding | Numeric vector representation produced locally from query or chunk text. |
| Generation | Extraction version for one document; prevents mixing stale reprocess results. |
| Hybrid retrieval | Combination of semantic vector candidates and lexical PostgreSQL candidates. |
| Idempotency key | Unique job key preventing duplicate durable work insertion for a logical operation. |
| OCR | Optical character recognition, via local Tesseract in this repository. |
| Outbox | Database row committed with business data so a worker can later execute durable work. |
| RAG | Retrieval-augmented generation: retrieve authorized evidence, then optionally ask a language model to answer from it. |
| RLS | PostgreSQL Row-Level Security policies, defense in depth beyond application-level owner filters. |
| Tenant context | Transaction-local `app.current_user_id` consumed by PostgreSQL RLS policy. |
| TTL | Time-to-live; configured expiration for presigned URLs or tokens. |
| UUID | Universally unique identifier used for user/document/chunk identities. |
