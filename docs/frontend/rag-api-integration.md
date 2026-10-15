# RAG API integration

The frontend uses the FastAPI contracts currently implemented in the repository.

## Ask

`POST /api/v1/health/ask` (Bearer token, JSON):

```json
{
  "question": "What hemoglobin value is recorded in my latest CBC report?",
  "document_ids": ["optional-authorized-document-uuid"]
}
```

`document_ids` is omitted when searching all records. FastAPI derives the user ID from the verified token and applies ownership filters; a client document filter only narrows that authorized result set.

The response schema is `HealthAnswer`:

```json
{
  "answer": "Backend-generated answer or evidence-only message",
  "citations": [
    { "document_id": "uuid", "document_name": "CBC Report.pdf", "page_number": 1 }
  ],
  "evidence": [
    { "document_id": "uuid", "document_name": "CBC Report.pdf", "page_number": 1, "excerpt": "..." }
  ],
  "generation_status": "generated"
}
```

The three statuses currently returned by the backend are `generated`, `evidence_only`, and `insufficient_evidence`. The frontend does not assume a separate retrieval-unavailable response mode; transport and HTTP errors are handled as errors.

## Other endpoints used

- `GET /api/v1/health/history`: persisted chat messages for the current user.
- `GET /api/v1/documents?limit=50&offset=0&sort=newest`: the user's document page.
- `GET /api/v1/documents/{document_id}/indexing-status`: indexing status used to restrict selectable documents.

No streaming endpoint, conversation-ID API, or structured medical-result response is currently implemented. The frontend uses standard request/response behavior and does not invent these contracts.
