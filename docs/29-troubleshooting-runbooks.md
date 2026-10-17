# Troubleshooting

| Symptom | Check | Likely explanation / next step |
| --- | --- | --- |
| Frontend says API unreachable | API process, `NEXT_PUBLIC_API_BASE_URL`, CORS origin and browser network panel | Start FastAPI; use exact explicit origin in `FRONTEND_ORIGINS`; inspect request ID and safe response. |
| Registration takes too long | `/health`, PostgreSQL availability and connection timeout | Backend connect timeout is five seconds; check DB host/port/role, do not create tables manually. |
| Old account login fails | Correct backend DB URL and account row; username normalization | Accounts are not browser-local. Do not reset production DB; create a new account only if appropriate. |
| Upload fails with storage category | Authenticated `/storage/check`, SDK credential source, bucket/region/IAM | Check exact error category and IAM; don't paste keys; never make bucket public. |
| Upload succeeds but waits | Worker process, pending job age, document status/history | API queues work; separately launch worker and review stage/failure code. |
| `review_required` | Status/history, page OCR warnings, classification and extracted provenance | Unknown labels/empty scan/conflicts require review. Install/configure OCR or improve tested rules; don't treat as diagnosis. |
| Indexing failed | Indexing status/model cache/Qdrant auth, collection dimension | PostgreSQL chunks may still support lexical search. Reindex after correcting isolated collection/model config. |
| Assistant finds no record | Owner account, current generation, ready status, filters and chunk persistence | Empty retrieval is explicit; check extraction/index state and exact document/date/type filters. |
| Assistant 503/504 | Provider availability/key/model and timeout | Client receives generic message; inspect category/type logs, never log request context or credentials. |
| Another user's document appears inaccessible | This is intended 404 behavior | Use the owning account; do not probe IDs as an access pattern. |

For deletion and queue retry, see [operational runbooks](36-operational-runbooks.md). Do not test cloud paths against production data.
