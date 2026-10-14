# Document processing tests

Run backend tests with `.venv/bin/python -m pytest -q` from the repository root. The integration fixtures create synthetic PDFs locally and use SQLite plus fake private storage; no real patient data, S3 access, OCR executable, or LLM credentials are required. Tests cover deterministic parsing, provenance, result endpoints, worker state changes, retry behavior, and cross-user 404 isolation.

For manual local verification, configure PostgreSQL and private S3, apply migrations, start API and worker, then upload a synthetic or de-identified PDF. Check `/api/v1/documents/{id}/status`, `/extractions`, `/tables`, `/pages`, and `/history` using the same owner's bearer token. Confirm another account receives 404 for each endpoint. Never use an actual patient's report as a test fixture.
