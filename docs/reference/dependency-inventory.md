# Dependency inventory

| Manifest | Dependencies | Purpose / caveats |
| --- | --- | --- |
| `requirements.in` and `requirements.txt` | FastAPI, Uvicorn, SQLAlchemy async, asyncpg, psycopg, Pydantic/email/settings, dotenv, pwdlib, PyJWT, Alembic, boto3, python-multipart, PyMuPDF, Pillow, pytesseract, sentence-transformers | Runtime dependency ranges and universal Python 3.12 hash lock. |
| `requirements-dev.in` and `requirements-dev.txt` | pytest, httpx, aiosqlite, Ruff, pip-audit, plus runtime dependencies | Test, lint and dependency audit tools; isolated tests use SQLite and fakes. `requirements-dev.txt` is the full hash lock. |
| `frontend/package.json` | Next.js 15, React/React DOM 19, lucide-react | App Router UI/runtime. |
| frontend dev dependencies | TypeScript 5.7+, ESLint 9, eslint-config-next, React/Node type packages | Lint/type/build. Exact dependency graph is locked in `frontend/package-lock.json`. |
| System dependency | Tesseract binary and trained language data | Optional local OCR; Python package alone does not install binary/data. |

CI installs Python dependencies from the hash-checked development lock, audits both Python locks and runs `npm audit --omit=dev` for frontend production dependencies. The full npm audit still reports an unpatched high-severity advisory in a development-only transitive `braces` dependency; see [development setup](../development.md). No SBOM generation is configured.
