# Frontend document workflow

1. **Upload:** `/documents` reuses the reports library. It accepts one PDF/JPEG/PNG up to 15 MB, shows byte progress from XHR, and treats backend validation as authoritative. On success the backend response provides a current state; the UI says uploaded/queued and links to the document status page. Upload success is never shown as processing completion.
2. **List:** the UI uses the authenticated `GET /api/v1/documents` filters the backend supports: filename, type, created-at date range, sort, and page size/offset. There is no status filter or status aggregation endpoint. Status badges use the API state.
3. **Details:** `/documents/{id}` gets the owner-authorized document and polls only active states without overlapping requests. It refreshes status, stops for completed/failed/review-required, and continues checking deletion until the backend confirms the resource is unavailable. The detail page reports that extracted content/timeline APIs are absent.
4. **Secure viewing/deletion:** a short-lived URL is requested from the backend only after the user opens a preview or download. No S3 host/key is constructed by the UI. Deletion requires browser confirmation and reflects the server outcome.
5. **Reprocessing:** the owner can call the real backend reprocessing action in failed, completed, or review-required states; the returned state is rendered.
6. **Review:** the backend exposes only `POST /api/v1/documents/{id}/review/complete`, which validates mandatory server-side processing stages. No review fields, extracted text, edit, accept, or reject API exists. The UI shows this limitation and only reflects the returned document after success.

There is no API for processing event history or detailed stages; the UI does not invent percentages or stage progress.
