# Document processing runbook

1. Install backend requirements and configure the ignored local `.env` or secret manager for PostgreSQL and private S3. Keep secrets out of source control.
2. Inspect the target schema and Alembic revision; apply reviewed schema changes with `alembic upgrade head` using the migration owner. Do not stamp or reset an existing database to bypass drift.
3. Start the API: `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Start a separate worker: `python -m app.documents.worker`. It polls the durable outbox and recovers expired leases.
5. Upload a PDF. The API response means storage and queueing succeeded; it does not mean extraction is complete. Poll the owner-authenticated document status endpoint.
6. Inspect `/status`, `/extractions`, `/tables`, `/pages`, and `/history` using the owning account. A review state includes warnings/reasons where available. Retryable S3 failures are bounded; reprocess is owner-only.

The stock processor uses PyMuPDF and deterministic rules only. OCR requires local Tesseract plus configured language data; when unavailable, scan-only pages produce a review reason. JPEG/PNG uploads are converted to a one-page PDF and use the same local OCR path. When Qdrant is configured, the worker chunks persisted pages/entities/tables, runs the configured local embedding model, and attempts vector indexing. If embedding or vector indexing fails, PostgreSQL chunks remain available for owner-scoped keyword search and the indexing state records a safe failure code. Operational logs provide safe counts and error categories, never report content or credentials.
