# Repository and module guide

| Path | Responsibility and key entry points |
| --- | --- |
| `app/main.py` | FastAPI factory, middleware, exception mapping, routers, DB-only `/health` |
| `app/core/config.py` | Pydantic settings, URL/origin/secret validation |
| `app/core/security.py` | Argon2 password hash/verify and HS256 token creation |
| `app/core/rate_limit.py` | In-process sliding-window limiter |
| `app/database.py` | Async engine/session factory and request-scoped session dependency |
| `app/user/` | Registration/login/current-user resolution, DTOs and User model |
| `app/documents/router.py` | Upload, list/detail, result/status/history, URL, reprocess/reindex/review/delete APIs |
| `app/documents/extraction.py` | PDF/OCR, table and deterministic medical rule extraction |
| `app/documents/pipeline.py` | Download to temporary directory and invoke extraction |
| `app/documents/processing.py` | State transitions, stage ledger, outbox, retry schedule |
| `app/documents/worker.py` | Claim/lease process, index and delete jobs; persist outcomes/recovery |
| `app/documents/cleanup.py` | Owner/document-scoped S3 and Qdrant cleanup |
| `app/health/` | Document/chunk/chat models; chunking; local embeddings; Qdrant; authorization-aware retrieval and answer generation |
| `app/storage/s3.py` | Boto3 client, categorized errors, private object operations and read-only bucket check |
| `alembic/versions/` | Seven ordered migration revisions; source of deployed DDL |
| `tests/` | API, extraction, processing, auth, RAG authorization and indexing tests; mostly SQLite/fakes |
| `frontend/app/` | Next.js App Router pages for auth, dashboard, documents, review, reports and assistant |
| `frontend/lib/api.ts` | Typed browser API client, timeout/error mapping and upload progress |
| `frontend/lib/session.ts` | `sessionStorage` token read/clear and 401 handling |
| `docs/` | Architecture, security, AI, data-processing, operations and verification references |
| `Dockerfile.api`, `frontend/Dockerfile`, `compose.yaml` | Separate API/worker targets, frontend production container, local-only integration stack |
| `.github/workflows/` | CI, disposable PostgreSQL migration validation, and image builds; no deploy job |
| `scripts/verify_migration_schema.py` | Read-only check of migrated tables, indexes, forced tenant RLS, and expected head |

The configured runtimes are Python 3.12 and Node 24.21.0, Next.js 15, React 19 and TypeScript. Runtime dependency ranges are in `requirements.in` with universal hashed pins in `requirements.txt`; development tools have a separate `requirements-dev.txt` hash lock. JavaScript dependency versions are recorded in `frontend/package-lock.json`.
