# Endpoint inventory

Full descriptions and validation are in [API reference](../08-api-reference.md). Routes below are registered by the included routers.

| Method | Path | Authentication |
| --- | --- | --- |
| GET | `/health` | No bearer; DB query only |
| POST | `/api/v1/users/register` | Public |
| POST | `/api/v1/users/login` | Public; rate-limited |
| GET | `/api/v1/users/me` | Bearer |
| GET | `/api/v1/documents/storage/check` | Bearer |
| POST | `/api/v1/documents/upload` | Bearer |
| GET | `/api/v1/documents` | Bearer |
| GET | `/api/v1/documents/{document_id}` | Bearer |
| GET | `/api/v1/documents/{document_id}/indexing-status` | Bearer |
| POST | `/api/v1/documents/{document_id}/reindex` | Bearer |
| GET | `/api/v1/documents/{document_id}/status` | Bearer |
| GET | `/api/v1/documents/{document_id}/extractions` | Bearer |
| GET | `/api/v1/documents/{document_id}/tables` | Bearer |
| GET | `/api/v1/documents/{document_id}/pages` | Bearer |
| GET | `/api/v1/documents/{document_id}/history` | Bearer |
| GET | `/api/v1/documents/{document_id}/view-url` | Bearer |
| GET | `/api/v1/documents/{document_id}/download-url` | Bearer |
| DELETE | `/api/v1/documents/{document_id}` | Bearer |
| POST | `/api/v1/documents/{document_id}/reprocess` | Bearer |
| POST | `/api/v1/documents/{document_id}/review/complete` | Bearer |
| POST | `/api/v1/health/ask` | Bearer; rate-limited |
| GET | `/api/v1/health/history` | Bearer |
| GET | `/api/v1/health/documents/{document_id}` | Bearer |

FastAPI's generated OpenAPI document is the running schema contract; verify it after adding/removing routes.
