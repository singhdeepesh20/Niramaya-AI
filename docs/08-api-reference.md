# API reference

Canonical route definitions are in `app/user/router.py`, `app/documents/router.py`, and `app/health/router.py`; request/response DTOs live beside those modules. OpenAPI is served by FastAPI at `/docs` when the app is running. All document/health routes below require `Authorization: Bearer <access_token>` unless noted.

## Accounts

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| POST | `/api/v1/users/register` | No | Create account; returns public profile (201). Username 3–30 ASCII letters/digits/underscore, normalized lowercase; email validated/lowercased; password 12–128 chars. Extra fields forbidden. |
| POST | `/api/v1/users/login` | No | Verify password and return bearer JWT; process-local IP rate limit. Generic 401 for unknown user/wrong password. |
| GET | `/api/v1/users/me` | Yes | Resolve JWT subject to active account and return public profile. |

## Documents

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/documents/storage/check` | Authenticated read-only S3 connectivity/privacy configuration check. |
| POST | `/api/v1/documents/upload` | Multipart upload (`file`, `document_type`, optional `document_date`); PDF/JPEG/PNG signature, type and size validation; S3 object + DB metadata/outbox. |
| GET | `/api/v1/documents` | Owner-only filtered/paginated list (`q`, `document_type`, `date_from`, `date_to`, `sort`, `limit`, `offset`) plus summary counts. |
| GET | `/api/v1/documents/{id}` | Owner's ready document metadata. |
| GET | `/api/v1/documents/{id}/status` | Current generation/state and stage outcomes. |
| GET | `/api/v1/documents/{id}/indexing-status` | Vector index state, model/dimension, attempts and safe error code. |
| POST | `/api/v1/documents/{id}/reindex` | Enqueue index-only job (202); extraction must be completed or review-required. |
| GET | `/api/v1/documents/{id}/extractions` | Current-generation deterministic entities. |
| GET | `/api/v1/documents/{id}/tables` | Current-generation detected tables. |
| GET | `/api/v1/documents/{id}/pages` | Current-generation extracted page text with pagination. |
| GET | `/api/v1/documents/{id}/history` | Owner-only transitions, stages, job and safe failure code. |
| GET | `/api/v1/documents/{id}/view-url` | Short-lived presigned inline GET. |
| GET | `/api/v1/documents/{id}/download-url` | Short-lived presigned attachment GET. |
| POST | `/api/v1/documents/{id}/reprocess` | Owner-only new extraction generation, 202. |
| POST | `/api/v1/documents/{id}/review/complete` | Complete only when review conditions allow; otherwise conflict. |
| DELETE | `/api/v1/documents/{id}` | Start owner-only deletion; external cleanup may be retried asynchronously. |

Supported document type form values: `cbc`, `blood_test`, `mri`, `prescription`, `discharge_summary`, `x_ray`, `other`. Classification can later refine type to additional internal values.

## Health Q&A

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/api/v1/health/ask` | Protected question (1–1000 chars), optional type/date/document-ID filters; returns answer, citations, evidence, `generation_status`. User identity is never supplied by client. |
| GET | `/api/v1/health/history` | Authenticated user's last 50 chat rows. |
| GET | `/api/v1/health/documents/{id}` | Owner-scoped document metadata for assistant source display. |

Example request (document ID is a synthetic UUID, not an actual account record):

```json
{
  "question": "What does my latest blood test report say about hemoglobin?",
  "document_types": ["blood_test"],
  "date_from": "2025-01-01",
  "date_to": "2025-12-31"
}
```

The response shape contains a natural-language answer, citations and evidence excerpts; `generation_status` is `generated`, `evidence_only` or `insufficient_evidence`. Values are sourced from the report, not generated from this example. Example citation shape:

```json
{
  "document_id": "00000000-0000-4000-8000-000000000001",
  "document_name": "synthetic-report.pdf",
  "page_number": 1
}
```

## Common responses

Validation failures return 422 with sanitized field locations/types; auth failures return 401/403; another user's document returns 404; database availability failures return 503; assistant timeout returns 504; rate limiting returns 429 with retry information. `X-Request-ID` is returned. Exact error envelopes are in `app/main.py` and route-specific `APIError` calls.
