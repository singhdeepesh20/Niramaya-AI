# RAG retrieval and generation

## Retrieval sequence

`POST /api/v1/health/ask` requires an active JWT-resolved user. `HealthQuestion` forbids unknown fields, bounds question to 1000 chars, validates date order, normalizes filters, and permits at most 10 types/50 document IDs. The endpoint releases the user-lookup transaction before remote embedding/vector calls.

1. If Qdrant is configured, embed the question locally and query with server-owned owner/type/date/document/model filters; failures are logged by type and degrade to lexical candidates.
2. PostgreSQL applies mandatory authenticated `user_id`, document owner, current extraction generation, ready upload and not-deletion-pending constraints, then requested metadata filters.
3. PostgreSQL full-text ranking is used on PostgreSQL; tests use `ILIKE` token matching on SQLite. A small stopword set is removed. “latest/most recent/newest” prioritizes document date descending.
4. Qdrant IDs are re-resolved against the same PostgreSQL base query. Reciprocal-rank fusion merges authorized vector and lexical candidates; `RAG_TOP_K` bounds selected rows.
5. Backend builds evidence and unique citations from DB records, limits context by `RAG_MAX_CONTEXT_CHARS`, caps per-chunk text and excerpt length, then invokes the answer component.

## Answer and safety behavior

If there are no matching chunks, API returns an explicit insufficient-evidence answer and does not call the LLM. If generation is disabled or no key exists, answer is explicitly evidence-only. Otherwise `HealthAssistant` sends the question and authorized evidence to the configured OpenAI-compatible chat endpoint with temperature 0 and a system prompt that treats report content as untrusted, refuses to follow its instructions, has no tools, distinguishes uncertainty and forbids invented values/citations. Response markers outside the server's `[E#]` evidence set are removed; output is bounded to 8000 chars.

The API response includes `answer`, citations (`document_id`, name, optional page), evidence excerpts and generation status. Chat history is stored by verified owner. LLM output is still probabilistic and not clinically validated; marker filtering does not prove each statement is entailed by evidence.

## Failures and limitations

Vector/embedding errors fall back to lexical retrieval. LLM timeout returns 504; other LLM/provider or malformed-output failures return generic 503. Empty retrieval is handled safely. `RAG_TOP_K`, context chars, candidate limit and retrieval limit are separately configurable. Retrieval/reranking currently uses reciprocal-rank fusion; there is no learned reranker or BM25 library. See [RAG tests](testing/rag-tests.md) and [citation contract](ai/retrieval-and-citations.md).
