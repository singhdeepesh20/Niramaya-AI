# Testing and verification strategy

## Existing tests

`tests/conftest.py` creates a temporary SQLite database per API test, uses `Base.metadata.create_all()` only in that temporary fixture, overrides the DB dependency, and builds a FastAPI `TestClient`. Test files cover:

- `test_auth_api.py`: account validation, duplicate handling, password hashing, token claims/validation, generic errors, request IDs and DB failures.
- `test_config.py`: JWT strength/algorithm/expiry, CORS origins and service URL constraints.
- `test_documents_api.py`: fake S3, ownership, signatures/content types, listing, URLs, deletion and failure cleanup.
- `test_document_extraction.py`, `test_image_document_processing.py`: synthetic PDF/image fixtures, parsing, OCR-unavailable handling, classification and normalization.
- `test_document_processing.py`: outbox/worker transitions, stage ledger, retries, stale leases and owner isolation.
- `test_health_isolation.py`: two-user keyword/vector/metadata/document/history isolation, forged inputs, prompt-injection handling, citations, rate limit/provider behavior.
- `test_rag_indexing.py`: chunk determinism, fake embeddings/Qdrant, dimension checks, idempotence and keyword fallback after index failure.

Fakes are not live integration verification. SQLite does not verify PostgreSQL RLS, `tsvector`, `SKIP LOCKED`, role grants, migration drift or production transaction behavior. Frontend CI checks ESLint, TypeScript and `next build`; there is no browser/component test suite. Cloud integration tests are not run by ordinary CI.

## Commands

From repository root:

```sh
python -m compileall -q app tests
python -m pytest -q
```

From `frontend/`:

```sh
npm ci
npm run lint
npx tsc --noEmit --incremental false
npm run build
```

`tests/conftest.py` blanks Qdrant, LLM and AWS environment settings before application settings are imported, so pytest does not inherit root `.env` cloud endpoints or credentials. Tests that need provider behavior monkeypatch clients. Never point tests at production DB, S3 bucket or Qdrant collection.

## Verification performed for this manual

On 2026-10-15, Python compileall passed; pytest passed **79 tests** with cloud variables blanked; frontend ESLint, TypeScript and production build passed; Markdown-link/source/config/API inventories are being checked. This does not verify live PostgreSQL migrations, AWS, Qdrant, Groq, OCR binary availability or deployment behavior. See [verification matrix](reference/verification-matrix.md).
