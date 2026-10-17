# Dependency inventory

| Manifest | Dependencies | Purpose / caveats |
| --- | --- | --- |
| `requirements.txt` | FastAPI, Uvicorn, SQLAlchemy async, asyncpg, psycopg, Pydantic/email/settings, dotenv, pwdlib, PyJWT, Alembic, boto3, python-multipart, PyMuPDF, Pillow, pytesseract, sentence-transformers | Backend/API, auth, migrations, storage, PDF/OCR and local embeddings. Version ranges are bounded but not a fully hash-pinned Python lockfile. |
| `requirements.txt` test section | pytest, httpx, aiosqlite | API/unit tests use SQLite and HTTP clients; not production Postgres/cloud dependencies. |
| `frontend/package.json` | Next.js 15, React/React DOM 19, lucide-react | App Router UI/runtime. |
| frontend dev dependencies | TypeScript 5.7+, ESLint 9, eslint-config-next, React/Node type packages | Lint/type/build. Exact dependency graph is locked in `frontend/package-lock.json`. |
| System dependency | Tesseract binary and trained language data | Optional local OCR; Python package alone does not install binary/data. |

CI installs Python ranges from `requirements.txt` and Node packages via `npm ci`. No automated vulnerability/SBOM scan currently runs. Re-run dependency review against current advisories before release; this inventory is not a vulnerability audit.
