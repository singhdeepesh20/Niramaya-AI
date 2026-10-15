# RAG assistant

## Route and authentication

The assistant lives at `/assistant`. It reads the existing tab-scoped bearer session through `readAccessToken`; unauthenticated users are sent to `/login`, and a `401` clears the session using the shared session helper. Requests use the centralized API client, include `cache: no-store`, and do not send an owner ID. The FastAPI dependency is the authority for user identity and document access.

The page loads persisted messages from `GET /api/v1/health/history`. The backend returns only the authenticated user's chat history. The frontend does not save medical questions, answers, or evidence in local storage or URLs. It keeps the active response in component state until the backend history refresh completes.

## Asking questions

The composer accepts a trimmed question of up to 1,000 characters. Enter submits; Shift+Enter inserts a newline. Duplicate submissions are disabled while the request is in flight. The draft is cleared only after a successful ask response, so a failed request can be retried without retyping.

The optional document filter lists the first 50 account documents and checks the authenticated indexing-status endpoint for completed extraction results. Only reports with completed indexing and at least one indexed chunk can be selected. If the filter data cannot be loaded, the user can still ask across all available records; the interface does not claim that inaccessible or unindexed documents were searched.

## Response states

- `generated`: display the returned answer and returned citations/evidence.
- `evidence_only`: explain that retrieval succeeded but answer generation is unavailable, and show the returned evidence.
- `insufficient_evidence`: display the backend's answer and explain that the indexed records do not provide enough evidence.
- HTTP/network failure: show the API error, preserve the question, and provide a retry path. No fallback answer or citation is fabricated.

History currently stores citations but not excerpts, so previous responses show source links without recreating evidence excerpts that the history API does not return. The assistant renders answer and excerpt content as plain text; it does not interpret model output as HTML or Markdown.

## Current backend limits

The API persists a flat user-scoped history, not named conversations. It does not expose streaming, generation-stage progress, structured lab-value results, or citation section/relevance metadata. The frontend does not present those capabilities as available.
