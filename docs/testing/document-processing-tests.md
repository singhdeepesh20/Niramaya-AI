# Document processing tests

Run backend tests with `python -m pytest -q` from the repository root. The test fixture creates synthetic PDFs locally and uses SQLite plus fake private storage. It blanks cloud endpoint/credential environment variables before application settings load, so root `.env` values are not used by the suite. Tests cover deterministic parsing, provenance, result endpoints, worker state changes, retry behavior, and cross-user 404 isolation. OCR executable presence is not required; tests include its unavailable behavior.

For manual local verification, configure PostgreSQL and private S3, apply migrations, start API and worker, then upload a synthetic or de-identified PDF. Check `/api/v1/documents/{id}/status`, `/extractions`, `/tables`, `/pages`, and `/history` using the same owner's bearer token. Confirm another account receives 404 for each endpoint. Never use an actual patient's report as a test fixture.
