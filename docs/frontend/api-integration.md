# Frontend API integration

## Configuration

Set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI origin, such as `http://localhost:8000`. It is public frontend configuration, never a secret. Cloud credentials, database URLs, JWT signing secrets, and model keys belong only in the backend environment.

## Verified backend endpoints used

| Endpoint | Use |
|---|---|
| `POST /api/v1/users/register` | Create account |
| `POST /api/v1/users/login` | Receive bearer token |
| `GET /api/v1/users/me` | Verify authenticated session |
| `GET /api/v1/documents` | User-scoped list, summary, search/type/date/sort/paging |
| `POST /api/v1/documents/upload` | Single file upload with document type |
| `GET /api/v1/documents/{id}` | Owner-scoped document and current processing state |
| `GET /api/v1/documents/{id}/view-url`, `download-url` | Short-lived secure document access |
| `DELETE /api/v1/documents/{id}` | Owner-scoped deletion |
| `POST /api/v1/documents/{id}/reprocess` | Authorized reprocessing |
| `POST /api/v1/documents/{id}/review/complete` | Guarded review completion |
| `GET /api/v1/health/history` | Authenticated user chat history |
| `POST /api/v1/health/ask` | Ask question; returns answer, citations, evidence |
| `GET /api/v1/health/documents/{id}` | Owner-scoped document metadata (available as API client method) |

The frontend types include status, citation, and evidence contracts. Requests are bearer-authenticated; private fetch responses use `cache: no-store`. Multipart requests let the browser set their own boundary. Backend failures are never replaced by local success data.

## Missing backend contracts

No extracted entity/lab/table read endpoint, confidence schema, processing event/history endpoint, review queue/details/edit/accept/reject endpoint, status-filtered listing, or chat streaming endpoint exists. The UI surfaces these gaps and does not simulate them. Backend auth currently returns a bearer token rather than an HTTP-only session cookie.
