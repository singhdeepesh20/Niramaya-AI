# Niramaya-AI retrieval pipeline

The document worker first writes deterministic extraction output to PostgreSQL. A separate indexing step reads current-generation extracted pages and structured tables, chunks them, creates local embeddings, upserts points to Qdrant, writes chunk text and provenance to PostgreSQL, and removes obsolete points scoped to the same owner and document. PostgreSQL is canonical; Qdrant is a rebuildable index. No vectors are persisted in PostgreSQL.

Indexing errors update `medical_documents.indexing_status` and a bounded error category. They do not change extraction completion. Reindex jobs use the existing durable `document_processing_jobs` queue (`job_type=index`). A retry reuses deterministic point IDs. If vector cleanup fails after database commit, retrieval still validates against PostgreSQL and a later retry repeats scoped cleanup.

`POST /api/v1/health/ask` performs optional semantic retrieval plus PostgreSQL lexical retrieval. Before evidence reaches generation, every candidate is reloaded through owner, document, upload-state, and extraction-generation constraints. The configured answer provider is Groq's OpenAI-compatible Chat Completions endpoint with model `openai/gpt-oss-120b`; local embeddings remain independent. With `RAG_GENERATION_ENABLED=false` or no `LLM_API_KEY`, the endpoint returns an explicit evidence-only message and citations. Only authorized retrieved evidence and the question are sent to the configured answer provider.

See [chunking](chunking-strategy.md), [embedding setup](embedding-models.md), [Qdrant operations](qdrant-operations.md), [citations](retrieval-and-citations.md), and [user isolation](../security/user-scoped-retrieval.md).
