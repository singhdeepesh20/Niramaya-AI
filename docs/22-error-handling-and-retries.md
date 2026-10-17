# Error handling and retries

| Failure | User/API or stored outcome | Retry/partial-data behavior |
| --- | --- | --- |
| Invalid DTO/upload | Sanitized 422/413/415 | No job; upload validation precedes storage. |
| DB connection/interface | Generic 503 + request ID | Caller may retry; no automatic API write retry. |
| Other SQL failure | Generic 500, log error type | Registration/upload roll back; upload attempts S3 compensation. |
| S3 credentials/permissions/region/network | Categorized 503; no provider payload | Upload fails; source read errors may trigger bounded worker retries. |
| Bad/encrypted/empty/oversized PDF | Safe parser reason, document failed | No extraction content; owner can reprocess after correcting source only by uploading a new file. |
| OCR absent/timeout/empty | Page warnings and review reason | Embedded text still preserved; retrying without new OCR setup repeats limitation. |
| Unknown/conflicting extraction | `review_required`, review warnings | Owner can request new generation; manual review required. |
| Embedding/Qdrant failure | Independent indexing status and safe code | Chunks remain in PostgreSQL; lexical retrieval can work; reindex job retries without OCR. |
| LLM timeout | 504 `assistant_timeout` | User can retry; no answer saved if provider call fails before save. |
| Other LLM/malformed response | Generic 503 `assistant_unavailable` | No raw response details exposed. |
| Delete S3/Qdrant cleanup fails | Document remains deletion-pending; safe job error | Bounded retry; partial external cleanup is possible. |
| Worker lease expires | Job recovered/requeued or failed after attempt limit | Idempotency/generation checks reduce duplicate effects; external stages must remain idempotent. |

`APIError` and global handlers map public errors. Logs should contain request/job IDs, counts, reason codes and exception type only. Avoid exception strings from SDK/HTTP clients because they may include URLs or payload metadata. `retry_delay` is exponential from five seconds, capped at one hour; job max attempts defaults to five. Deletion/reindex and process queues share a table but have separate job types.
