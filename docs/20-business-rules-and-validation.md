# Business rules and validation catalogue

| Operation | Rule implemented in | Result on violation |
| --- | --- | --- |
| Account registration | `app/user/dtos.py`, `controller.py`, DB unique indexes | 422 field validation; 409 duplicate; no password returned |
| Login | DTO, Argon2 verify, dummy hash, `LoginRateLimiter` | Generic 401 for bad username/password; inactive 403; 429 when over limit |
| Upload | `documents/router.py:_validate_upload` | PDF/JPEG/PNG extension + signature + compatible MIME required; empty rejected; size bounded by `S3_MAX_UPLOAD_BYTES` |
| Document type | `DocumentType` Literal at upload; deterministic classifier may refine persisted type | Unknown/ambiguous content moves to review |
| Document list | Owner predicate, date range, sort enum, limit 1–100, offset <=100000 | Invalid range/parameters rejected; only owner's ready/deleting rows counted |
| Result access | Owner document check + child owner/document/current generation | Another user sees 404; stale generation hidden |
| Reprocess | Owner only; increments generation; safe state transition | 409 if state disallows action |
| Review completion | State/stage rules in route and `transition_document` | 409 until required review/stages are satisfied |
| Reindex | Owner only, extraction must be completed/review-required; duplicate pending job avoided | 409 when extraction is not ready |
| Assistant question | 1–1000 trimmed chars; no extra body fields; date bounds; at most 10 types and 50 IDs | 422; empty IDs intentionally return no matches |
| Retrieval | verified owner, ready doc, current generation, requested metadata | unauthorized candidates excluded before evidence reaches LLM |
| Context | per-excerpt and total context caps; top-k limit | excess evidence truncated/omitted, not sent unbounded |
| Presigned URL | owner ready document; TTL 60–900 seconds | generic categorized storage error; URL is bearer access until expiration |

These rules are code behavior, not a complete product policy. Supported formats/aliases and normalization are finite; see [medical extraction rules](14-medical-data-extraction-rules.md).
