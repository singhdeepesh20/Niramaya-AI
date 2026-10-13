# Niramaya-AI Health Records API

This repository contains a modular FastAPI service for Niramaya-AI. It provides account authentication, user-scoped medical-record retrieval, citations, and a protected LLM question-answer endpoint.

> This is a software foundation, not a clinical product or healthcare compliance certification. Review data handling and clinical safety before using real patient information.

## Architecture

```mermaid
flowchart LR
    Client[API client or browser] -->|JSON and Bearer token| API[FastAPI<br/>app/main.py]
    API --> Router[User routes<br/>app/user/router.py]
    Router --> Controller[Auth and user logic<br/>app/user/controller.py]
    Controller --> DTO[Pydantic contracts<br/>app/user/dtos.py]
    Controller --> Hash[Argon2id password hashing]
    Controller --> JWT[HS256 JWT signing and verification]
    Controller --> Session[Async SQLAlchemy session<br/>app/database.py]
    Session --> Model[User ORM model<br/>app/user/models.py]
    Model --> Postgres[(PostgreSQL)]
    Settings[Validated environment settings<br/>app/core/config.py] --> API
    Settings --> Session
    Migrations[Alembic migrations] --> Postgres
    Health[Protected health Q&A] --> Retrieval[Owner-filtered retrieval]
    Retrieval --> Postgres
    Retrieval --> Qdrant[(Qdrant<br/>required user_id filter)]
    Retrieval --> Verify[PostgreSQL owner recheck]
    Verify --> LLM[Configured LLM<br/>authorized evidence only]
    LLM --> Health
```

Registration validates and normalizes identifiers, hashes the password, and writes the account in a transaction. Login performs Argon2 verification before issuing a token. The `/me` dependency validates the signature and required claims, then resolves the UUID subject against the database and checks account status. Responses use a public DTO that has no password-hash field.

## Project structure

```text
app/
├── main.py                 # App factory, middleware, errors, health endpoint
├── database.py             # Async engine, session factory, Base, request dependency
├── core/
│   ├── config.py            # Validated environment settings
│   ├── errors.py            # Safe application error type
│   ├── rate_limit.py        # Login rate-limiter integration
│   └── security.py          # Argon2 and JWT helpers
├── user/
    ├── controller.py        # Registration, login, current-user resolution
    ├── dtos.py              # Validated request and safe response schemas
    ├── models.py            # SQLAlchemy User model
    └── router.py            # Versioned HTTP endpoints
└── health/
    ├── assistant.py         # OpenAI-compatible LLM and filtered Qdrant client
    ├── dtos.py              # Question, citation, evidence, history contracts
    ├── models.py            # Documents, chunks, entities, scoped chat history
    ├── repository.py        # PostgreSQL owner filters, RLS identity, hybrid search
    └── router.py            # Protected ask/history/document routes
alembic/                     # Versioned database schema changes
tests/                       # Isolated API tests using temporary SQLite databases
frontend/                    # Next.js App Router authentication UI
├── app/login/page.tsx        # Login route
├── app/register/page.tsx     # Registration route
├── components/               # Shared auth layout and controls
└── lib/api.ts                # Typed FastAPI client
```

The database module is at `app/database.py` as requested. The app factory does not create or alter tables at startup; use Alembic for schema changes.

## Requirements

- Python 3.12 or newer.
- PostgreSQL for development/deployment.
- A PostgreSQL database and a role allowed to create and update the schema.

## Install and configure

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`. Set `DATABASE_URL` to the PostgreSQL async driver URL and generate a unique JWT key:

```bash
openssl rand -hex 32
```

Use the generated value for `JWT_SECRET_KEY`. Do not commit `.env`. The example file intentionally contains a placeholder and will fail the strong-secret validation until replaced.

Example configuration:

```env
DATABASE_URL=postgresql+psycopg://niramaya_app:YOUR_PASSWORD@localhost:5432/niramayaai
JWT_SECRET_KEY=YOUR_GENERATED_64_CHARACTER_HEX_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_ISSUER=https://api.example.com
JWT_AUDIENCE=niramaya-clients
FRONTEND_ORIGINS=["https://app.example.com"]
```

Issuer and audience may be left blank for local development. When configured, they are included in issued tokens and checked during verification. `FRONTEND_ORIGINS` is a JSON array of explicit origins; an empty array disables cross-origin browser access.

Configure the following optional settings to enable semantic retrieval and answer generation:

```env
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=YOUR_PROVIDER_SECRET
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
LLM_TIMEOUT_SECONDS=20
QDRANT_URL=https://your-qdrant-host
QDRANT_API_KEY=YOUR_QDRANT_SECRET
QDRANT_COLLECTION=niramaya_medical_chunks
HEALTH_RETRIEVAL_LIMIT=8
HEALTH_CANDIDATE_LIMIT=30
```

Qdrant is optional; PostgreSQL full-text search remains available if it is not configured or is temporarily unavailable. LLM generation requires `LLM_API_KEY`. The configured provider receives the question and only authorized excerpts selected by the backend. Review the provider's data-handling terms and deployment before sending sensitive records.

## Database migration and run

Create the local database if needed, then apply the schema:

```bash
createdb -h localhost -p 5432 -U postgres niramayaai
alembic upgrade head
uvicorn app.main:app --reload
```

Migrations create the account and user-scoped medical record tables. The application never runs `create_all()` or migration DDL on startup. Migration `0002_user_scoped_health` enables and forces PostgreSQL Row-Level Security on health documents, entities, chunks, and chat history. Each query also includes an explicit owner filter and sets transaction-local `app.current_user_id` from the verified JWT. Use a dedicated runtime database role with `NOSUPERUSER NOBYPASSRLS`; do not run the API as PostgreSQL's `postgres` superuser. Apply migrations with a separate schema-owner role, then grant the runtime role only the required table permissions. PostgreSQL superusers can bypass RLS.

Open <http://127.0.0.1:8000/docs> to inspect the API in Swagger UI. Health is available at <http://127.0.0.1:8000/health>.

## Authentication frontend

The Next.js frontend lives in `frontend/` so its App Router `app/` does not collide with the Python backend package. Start it separately after starting the API:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000/login> or <http://localhost:3000/register>. Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` when the API is not at `http://localhost:8000`. The API's `FRONTEND_ORIGINS` must include the exact frontend origin for browser requests.

The UI follows the API's actual request schemas: registration accepts username, email, and password; login accepts username and password. The UI does not collect full name, phone number, or role because the current backend does not store or validate those fields. After login the bearer token is kept in `sessionStorage` for the current browser tab and `/api/v1/users/me` verifies the profile. This has more exposure to injected JavaScript than a backend-managed `HttpOnly` cookie; the API currently does not implement that cookie flow. Google sign-in is visibly disabled, and the Terms and Privacy routes state that the documents are not published yet.

## API

All authentication routes are under `/api/v1/users`.

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/users/register` | Public | Register an account |
| `POST` | `/api/v1/users/login` | Public | Verify credentials and issue a JWT |
| `GET` | `/api/v1/users/me` | Bearer JWT | Return the authenticated user's safe profile |
| `GET` | `/health` | Public | Check database availability |
| `POST` | `/api/v1/health/ask` | Bearer JWT | Retrieve authorized records and answer a question |
| `GET` | `/api/v1/health/history` | Bearer JWT | List the signed-in user's Q&A history |
| `GET` | `/api/v1/health/documents/{document_id}` | Bearer JWT | Read authorized document metadata |

![Niramaya-AI secure health question workflow](docs/health-qa-workflow.svg)

### Ask about health records

```bash
curl -i http://127.0.0.1:8000/api/v1/health/ask \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What was my latest hemoglobin level?","document_types":["lab_report"],"date_from":"2024-01-01"}'
```

The request accepts `question` and optional `document_types`, `date_from`, `date_to`, and `document_ids`. Extra fields such as `user_id` are rejected. The user identity comes only from the verified JWT. PostgreSQL performs lexical full-text ranking (tests on SQLite use token matching). Semantic retrieval uses Qdrant with a server-generated mandatory `user_id` filter. Qdrant results are untrusted chunk IDs: PostgreSQL re-fetches each chunk joined to its document under explicit owner and metadata filters before any text reaches the LLM. Reciprocal rank fusion combines semantic and lexical results.

Qdrant points should use the medical chunk UUID as point ID (or include it as payload `chunk_id`) and carry `user_id`, `document_id`, `document_type`, and `document_date_epoch` (UTC Unix seconds). The implementation sends a filtered Qdrant query using its [query-points API](https://api.qdrant.tech/api-reference/search/query-points/). Original files are represented by `object_key`; an upload/object-storage ingestion pipeline is outside this feature.

Responses include the answer, server-built citations (document ID, name, and page), and relevant evidence excerpts. Empty retrieval returns a clear no-record answer without calling the LLM. Report text is treated as untrusted data; the prompt tells the model to ignore embedded instructions, no tools are exposed, and it is told not to invent facts or values. Q&A history is stored under the owning user and the history route filters on that verified user.

Qdrant outages fall back to PostgreSQL search. Database failures return safe `503` errors; LLM timeouts return `504`, and other provider failures return generic `503`. Provider logs contain exception types only, never questions, excerpts, credentials, or model responses. The ask rate limiter is process-local; use shared rate limiting for multiple workers.

### Register

```bash
curl -i http://127.0.0.1:8000/api/v1/users/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"deepesh","email":"deepesh@example.com","password":"StrongExamplePassword123!"}'
```

Success returns `201` and public fields only: `id`, `username`, `email`, `is_active`, `created_at`, and `updated_at`. It never returns `hashed_password` or the submitted password.

### Login

```bash
curl -i http://127.0.0.1:8000/api/v1/users/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"deepesh","password":"StrongExamplePassword123!"}'
```

Success returns `200` with `access_token`, `token_type`, and `expires_in` in seconds. The browser UI keeps this bearer token in tab-scoped `sessionStorage`; this is a deliberate compatibility choice for the current bearer-token API, not an XSS-resistant token vault.

### Current user

```bash
curl -i http://127.0.0.1:8000/api/v1/users/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

The authenticated identity comes exclusively from the verified JWT subject. The endpoint does not accept a caller-supplied user ID.

## Validation and error responses

- Usernames are trimmed, lowercased, 3–30 characters, and limited to ASCII letters, digits, and underscores.
- Emails are trimmed, validated, and lowercased before storage.
- Passwords are 12–128 characters; they are not trimmed or silently changed.
- Duplicate username/email: `409`.
- Incorrect username/password: generic `401`.
- Missing, invalid, tampered, or expired token: `401` with `WWW-Authenticate: Bearer`.
- Inactive account: `403`.
- Invalid request: `422`.
- Database connection failure: `503`.
- Unexpected failures return a generic `500` response with a request ID.

Errors use a structured body such as `{"error":{"code":"invalid_credentials","message":"Incorrect username or password.","request_id":"..."}}`. Validation responses omit submitted values, so passwords are not echoed. Database URLs, SQL messages, and secrets are not returned or logged.

## Security notes and deployment boundary

- `pwdlib`'s recommended hasher uses Argon2id. JWT uses an explicitly allowed HS256 algorithm and requires `sub`, `iat`, and `exp`. Issuer and audience are verified when configured.
- A process-local sliding-window limiter allows 10 login attempts per client IP per 60 seconds. For multiple workers or hosts, replace it with a shared Redis or gateway-backed limiter before deployment.
- Configure HTTPS, strong environment-managed secrets, restricted database access, monitoring, backups, and security logging before public deployment.
- CORS only allows configured origins and does not enable credentials. The API uses bearer headers, not cookies. Secure `HttpOnly`, `SameSite` cookies reduce JavaScript token exposure but require CSRF defenses; bearer tokens are easier for API clients but must not be persisted in browser storage.
- Authentication answers who the caller is; authorization determines what they can access. This implementation only exposes the caller's own profile. It does not implement roles, medical-document permissions, account recovery, email verification, refresh/revocation tokens, MFA, or audit trails.
- Health retrieval currently allows owner-only document access; it does not implement document sharing or delegated access. Composite foreign keys ensure a chunk/entity owner matches its document owner. RLS is additional defense, while application filters remain mandatory.
- Request IDs are returned in `X-Request-ID` and safe error bodies. Logs include request ID and exception type only, never request bodies, tokens, passwords, SQL text, or database URLs.

This code is an educational authentication module, not a certification of production readiness for a healthcare environment. Obtain an application-specific security and privacy review before handling sensitive information.

## Tests

Tests use a temporary SQLite database per test and never connect to the configured PostgreSQL database:

```bash
python -m pytest
```

Coverage includes authentication, registration validation, password handling, JWT verification, and health retrieval isolation with two users. The isolation tests cover keyword and vector results, metadata filters, direct document access, chat history, forged request `user_id`, and hostile vector results. Tests use a temporary SQLite database; PostgreSQL RLS and live provider integrations require separate environment-level verification.

## Swagger verification checklist

1. Start the API and open `/docs`.
2. Register a valid username, email, and password at `POST /api/v1/users/register`; confirm status `201` and no password hash in the response.
3. Register the same normalized username or email again; confirm status `409`.
4. Sign in at `POST /api/v1/users/login`; confirm status `200` and an expiry value.
5. Click **Authorize**, enter `Bearer <access_token>`, and call `GET /api/v1/users/me`.
6. Clear authorization or use an expired token; confirm status `401`.
7. Stop PostgreSQL and call `/health`; confirm a safe `503` response.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
