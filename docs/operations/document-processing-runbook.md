# Document processing runbook

1. Install backend requirements and configure the existing `.env` for PostgreSQL and private S3. Keep secrets out of source control.
2. Apply schema changes with `alembic upgrade head` using the migration owner.
3. Start the API: `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Start a separate worker: `python -m app.documents.worker`. It polls the durable outbox and recovers expired leases.
5. Upload a PDF. The API response means storage and queueing succeeded; it does not mean extraction is complete. Poll the owner-authenticated document status endpoint.
6. Inspect `/status`, `/extractions`, `/tables`, `/pages`, and `/history` using the owning account. A review state includes warnings/reasons where available. Retryable S3 failures are bounded; reprocess is owner-only.

The stock processor uses PyMuPDF and deterministic rules only. OCR requires local Tesseract plus the configured language data; when unavailable, scan-only pages produce a review reason. Image-only JPEG/PNG uploads are currently not parsed by this worker. No LLM or vector index is configured. Operational logs provide counts and safe error codes, never report content or credentials.
