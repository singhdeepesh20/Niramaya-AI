# Citations and evidence

The assistant renders citation and evidence metadata returned by `POST /api/v1/health/ask`. Each source includes its backend document name and ID, plus a page number only when the backend supplied one. Each excerpt is rendered as plain text.

Selecting **Open report** navigates to `/documents/{document_id}`. That protected detail route asks the backend for the authenticated user's document and obtains a short-lived viewing URL through the authorized document API. The assistant does not construct object-storage URLs, expose storage keys, or load a public report link.

The frontend does not treat an LLM-generated citation marker as proof. It only renders citation objects returned separately by FastAPI, which builds them from authorized retrieved chunks. Authorization and citation-to-chunk validation remain backend responsibilities.

The current citation schema has `document_id`, `document_name`, and optional `page_number`. It does not include section headings, page ranges, OCR source type, or relevance scores. Previous chat history stores citations but not evidence excerpts, so excerpt panels are shown only for the immediate response that returned them.
