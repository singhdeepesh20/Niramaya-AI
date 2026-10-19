# Local development

## Prerequisites

- Python 3.12 (see `.python-version`)
- Node.js 20 and npm (see `frontend/.nvmrc`)
- PostgreSQL for a complete local API workflow
- Tesseract and English language data for OCR of scan-only pages (optional for text PDFs)

Use a disposable local database for development. Never point setup commands at a database that contains user or production data.

## Configure the backend

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
```

Create `.env` from `.env.example` only if it does not already exist; otherwise merge the required settings without replacing your local values. Configure `DATABASE_URL` for your local development database and set a unique JWT secret generated with `openssl rand -hex 32`. Keep all credentials in the ignored `.env` file or a secret manager.

`EMBEDDING_ALLOW_DOWNLOAD` is false by default. Make the configured model available in the local cache or set `EMBEDDING_MODEL_PATH` to an approved local model directory. Do not assume a model loads just because its name is configured. A small smoke check should return one vector whose length matches `EMBEDDING_DIMENSION`:

```bash
python - <<'PY'
from app.core.config import settings
from app.health.embeddings import embed_texts

vectors = embed_texts(["Synthetic model readiness check."])
assert len(vectors) == 1
assert len(vectors[0]) == settings.EMBEDDING_DIMENSION
print(f"Embedding ready: dimension={len(vectors[0])}")
PY
```

## Database and migrations

For a new disposable local database, run Alembic using a role authorized to create the development schema:

```bash
alembic upgrade head
```

For a shared or existing database, first inspect the recorded Alembic revision and compare its schema with the migration files. Apply migrations only through the authorized migration-owner workflow after review and backup. Do not use `Base.metadata.create_all()`, `alembic stamp head`, or destructive reset commands to bypass drift. The runtime application role should have only required data permissions and must not bypass RLS.

## Start the services

Run each command from the appropriate directory in a separate terminal:

```bash
# Repository root: API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Repository root: durable document worker
python -m app.documents.worker
```

```bash
# Frontend directory
cd frontend
npm ci
if [ ! -f .env.local ]; then cp .env.example .env.local; fi
npm run dev
```

Open `http://localhost:3000`. The frontend uses `NEXT_PUBLIC_API_BASE_URL` from `frontend/.env.local`; set the API CORS origins in the backend `.env` to the exact frontend origin.

For OCR on macOS, install Tesseract separately with `brew install tesseract`. OCR runs locally. The worker records a review or failure state when a scan cannot be read; the UI should display the persisted state rather than claiming processing succeeded.

## Quality checks

Run from the repository root:

```bash
python -m compileall -q app tests
python -m pytest -q
ruff check app tests
```

Run from `frontend/`:

```bash
npm ci
npm run lint
npx tsc --noEmit --incremental false
npm run build
npm audit --omit=dev
npm audit
```

Backend tests use temporary SQLite databases, synthetic documents, and test doubles. They do not verify live AWS, PostgreSQL RLS, Qdrant, model downloads, or Groq access. Keep cloud credentials out of ordinary tests and CI.

For production-only installs, use `python -m pip install --require-hashes -r requirements.txt`. Development installs include tests, lint and audits with `requirements-dev.txt`. The lockfiles resolve Python 3.12 dependencies across supported platforms. Install `uv` as a lock-generation tool, then update the range inputs in `requirements.in` or `requirements-dev.in` and regenerate the matching lock with `uv pip compile --universal --python-version 3.12 --generate-hashes requirements.in -o requirements.txt` or `uv pip compile --universal --python-version 3.12 --generate-hashes requirements-dev.in -o requirements-dev.txt`. Review the complete lock diff and rerun tests before merging.

The 2026-10-19 dependency audit found an unresolved high-severity advisory for `braces` through the frontend ESLint/Next.js tooling dependency chain. The advisory lists no patched upstream release, and the affected package is development tooling rather than a production dependency. Do not suppress the finding or force a breaking Next.js downgrade; monitor Dependabot and update once upstream publishes a fix. The PostCSS issue in the production dependency graph is constrained to the published patched floor by the npm override.

## Troubleshooting

- **Database unavailable:** confirm the API process loaded the intended local `.env`, PostgreSQL is reachable, and the runtime role can connect and perform required data operations. Restart the API after changing environment settings.
- **Migration permission error:** use the approved migration-owner role on a disposable or reviewed target; do not grant DDL privileges to the runtime role.
- **S3 unavailable:** perform a read-only STS identity check first. Do not try uploads until the credentials and bucket permissions are verified and a synthetic write is explicitly approved.
- **Qdrant unavailable or collection missing:** verify URL/key and the collection's configured vector size/distance. Do not delete or recreate a collection to resolve a mismatch.
- **Embedding unavailable:** verify the local model cache/path, device, package compatibility, and expected vector dimension. Avoid sending real reports to an external model to debug local embeddings.
- **Document remains queued:** confirm the worker is running and inspect the owner-authenticated status/history endpoints for persisted job and stage states.
