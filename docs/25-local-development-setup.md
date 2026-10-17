# Local development setup

Use [development.md](development.md) for complete commands and [configuration reference](reference/configuration-reference.md) for supported settings.

1. Install Python 3.12+ and Node 20; install Tesseract only if OCR development is needed.
2. Create a Python virtual environment and install `requirements.txt`; run `npm ci` in `frontend/`.
3. Create ignored `.env` from `.env.example`; use a disposable PostgreSQL database and a strong unique JWT secret. Keep cloud variables blank unless an isolated service is explicitly intended.
4. Review Alembic history/current and apply migrations to the development database with the migration role: `alembic upgrade head`.
5. Start API (`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`) and a separate worker (`python -m app.documents.worker`). Run frontend with `npm run dev` in `frontend/` and configure only `NEXT_PUBLIC_API_BASE_URL` as needed.
6. Run tests with cloud settings blank, use synthetic documents and test accounts, and verify owner-scoped behavior.

`/health` only tests PostgreSQL. The API process does not start a worker or run schema creation. A 201 upload response means queueing succeeded, not processing completed.
