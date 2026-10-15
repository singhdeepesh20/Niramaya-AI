# Retrieval and citations

The assistant route combines Qdrant semantic candidates with PostgreSQL full-text (or SQLite lexical fallback) candidates by reciprocal-rank fusion. Top-k is controlled by `RAG_TOP_K`; context is bounded by `RAG_MAX_CONTEXT_CHARS`. Document type, date, and document ID filters are applied in both Qdrant and PostgreSQL. The owner condition always comes from the verified JWT.

Qdrant returns identifiers only. PostgreSQL resolves each chunk and verifies owner, active document, requested metadata, and current extraction generation before evidence is constructed. Citations include the real document ID/name and page number when known; excerpts are drawn from authorized PostgreSQL chunk content. Without a configured generation provider, the API labels the response `evidence_only` and returns the evidence instead of inventing a medical answer.
