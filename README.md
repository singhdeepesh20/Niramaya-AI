# Niramaya-AI

## Niramaya AI is an AI-powered platform that transforms scattered medical reports into a searchable, intelligent health record.

**An asynchronous FastAPI and PostgreSQL foundation for a healthcare-oriented AI project.**

Niramaya-AI is a learning-stage backend prototype built with Python 3.12+, FastAPI, SQLAlchemy's async API, asyncpg, and PostgreSQL. It currently demonstrates a small user-profile workflow and a browser interface on top of that API.

> **Project status:** this repository includes basic password and bearer-token authentication, but no AI/ML model, patient records, or clinical functionality. It is not a medical product. Do not submit real patient information or use it to guide clinical decisions.

## What is implemented

- A FastAPI application with a same-origin HTML/CSS/JavaScript frontend.
- Async SQLAlchemy database access using `AsyncSession` and the `asyncpg` driver.
- A `users` table with an integer ID, unique username and email, password hash, and server-generated creation time.
- Account registration and login with Argon2 password hashing and short-lived signed access tokens.
- Current-user identity and self-only profile lookup endpoints.
- Versioned schema migrations for adding password hashes and usernames to existing user tables.
- A database-aware health endpoint and an explicit local table-initialization command.

## Architecture

```mermaid
flowchart TD
    Browser[Browser UI<br/>frontend/] -->|HTTP| App[FastAPI app<br/>app/main.py]
    App --> Auth[Auth router<br/>app/api/auth.py]
    App --> Router[Users router<br/>app/api/users.py]
    Auth --> Security[Argon2 and JWT helpers<br/>app/core/security.py]
    Router --> Schema[Pydantic schemas<br/>app/schemas/user.py]
    Router -->|Depends get_db| Session[AsyncSession]
    Session --> ORM[SQLAlchemy model and queries]
    ORM --> Driver[asyncpg]
    Driver --> DB[(PostgreSQL)]
    Config[.env settings<br/>app/core/config.py] --> Engine[Async engine and pool]
    Engine --> Session
    Init[Local table initializer<br/>app/db/init_db.py] --> ORM
    Migrate[Alembic migration<br/>alembic/] --> ORM
```

The frontend calls the FastAPI routes. FastAPI validates request and response data with Pydantic; dependency injection supplies one async database session for the request. SQLAlchemy maps Python objects and queries to database operations, while asyncpg carries PostgreSQL protocol traffic to the database.

## Technology

| Area | Technology |
| --- | --- |
| Runtime | Python 3.12+ |
| API | FastAPI, Uvicorn |
| Validation and settings | Pydantic v2, pydantic-settings |
| Database layer | SQLAlchemy 2.x async API, `AsyncSession` |
| PostgreSQL driver | asyncpg |
| Database | PostgreSQL |
| Browser interface | HTML, CSS, vanilla JavaScript |

## Repository layout

```text
app/
├── main.py             # FastAPI application, frontend mount, health endpoint
├── core/config.py      # Environment-backed settings
├── db/
│   ├── database.py     # Async engine, pool, session factory, request dependency
│   ├── models.py       # SQLAlchemy declarative models
│   └── init_db.py      # Explicit local table creation
├── api/
│   ├── auth.py         # Registration, token, and current-user endpoints
│   ├── dependencies.py # Bearer-token validation and current-user lookup
│   └── users.py        # Authenticated profile endpoint
├── core/security.py    # Password hashing and JWT creation
└── schemas/            # Pydantic request and response models
alembic/                # Versioned database migrations
frontend/
├── index.html
├── styles.css
├── app.js
└── favicon.svg
.env.example            # Safe local configuration template
requirements.txt
```

## Quick start

### Prerequisites

- Python 3.12 or newer.
- PostgreSQL running locally and a role that can create databases.

Create the development database if it does not already exist:

```bash
createdb -h localhost -p 5432 -U postgres niramaya
```

### Install and configure

Run these commands from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to match your local PostgreSQL credentials:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/niramaya
JWT_SECRET_KEY=replace-with-a-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Replace `YOUR_PASSWORD` locally. Generate a unique token-signing secret with `openssl rand -hex 32`. The URL uses SQLAlchemy's `postgresql` dialect with the async `asyncpg` driver. Never commit `.env`, the signing secret, or database credentials.

### Initialize and run

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/> for the browser interface or <http://127.0.0.1:8000/docs> for interactive API documentation. If the database already exists, skip `createdb`; run the initializer after configuring `.env`.

Alembic applies the versioned schema migration. `python -m app.db.init_db` remains available to create a fresh local schema, but does not upgrade existing tables.

## API reference

| Method | Path | Purpose | Successful response |
| --- | --- | --- | --- |
| `GET` | `/health` | Check PostgreSQL connectivity | `200` with `{"status":"ok","database":"connected"}` |
| `POST` | `/auth/register` | Register with name, username, email, and password | `201` with public profile fields |
| `POST` | `/auth/token` | Exchange username and password for a bearer token | `200` with access token |
| `GET` | `/auth/me` | Read the authenticated account | `200` with public profile fields |
| `GET` | `/users/{user_id}` | Fetch the authenticated user's own profile | `200` with public profile fields |

### Register and sign in

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Deepesh","username":"deepesh_singh","email":"deepesh@example.com","password":"a-long-unique-password"}'
```

Usernames are 3–32 characters and may contain letters, numbers, dots, underscores, and hyphens. Matching ignores case. Passwords must contain 12–128 characters. They are stored as Argon2 hashes, never as plaintext. Duplicate usernames or emails return `409 Conflict`. To sign in, send form fields named `username` and `password` to `/auth/token`; use the returned token as `Authorization: Bearer <access_token>`.

### Fetch a user

The browser UI signs in and keeps the access token in memory for the current tab. API clients can fetch their own profile with:

```bash
curl http://127.0.0.1:8000/auth/me -H 'Authorization: Bearer ACCESS_TOKEN'
```

Protected endpoints return `401 Unauthorized` when the token is absent, invalid, or expired. `/users/{user_id}` only returns the signed-in user's own profile; other IDs return `404`. Invalid request data returns `422`. If PostgreSQL is unavailable, `GET /health` returns `503 Service Unavailable`.

The browser UI at `/` offers health, registration, sign-in, sign-out, and own-profile workflows. It calls same-origin endpoints, so a separate frontend development server and CORS configuration are not required.

## Frontend workspace

The browser workspace is intentionally built with static HTML, CSS, and JavaScript. It includes:

- A service-health panel with checking, connected, and unavailable states plus a manual retry.
- An opt-in 30-second health check that pauses while the browser tab is hidden, resumes when visible, and reports response time.
- Light and dark themes that follow the operating-system preference by default and remember an explicit choice across visits and tabs.
- A registration and sign-in form that uses a username and password and shows the authenticated profile.
- A lookup card that renders profile details safely as text and offers copy-ID, share-link, JSON-download, and clear-result actions.
- Shareable profile URLs using the `?user_id=` query parameter.
- A project-status panel that identifies the current prototype boundaries and links to the API docs and OpenAPI schema.
- Responsive layouts, keyboard skip navigation, visible focus states, reduced-motion support, and live status announcements.

The UI sends same-origin requests to `/health` and `/users/`. Requests time out after ten seconds and display concise, user-facing errors. No browser-side secrets or external font services are required.

## Security and deployment status

This codebase is a local development foundation, not a deployment-ready healthcare service.

- **Authentication is foundational, not deployment complete.** Access tokens are signed with HS256, expire after 30 minutes by default, and are held in browser memory. Signing out clears the browser token; an issued token remains valid until it expires. There are no refresh/revocation tokens, rate limits, email verification, password reset, MFA, or security audit events.
- **Use HTTPS and a strong secret.** Set `JWT_SECRET_KEY` from a secret manager in deployments. Do not reuse the database password or commit the key.
- **The user model is only a demonstration.** It stores a name, username, and email; it is not a patient model and has no consent, access-control, or audit trail.
- **Do not use real patient or other sensitive personal data** with this prototype.
- Keep real credentials in a local or deployment secret store. `.env` is ignored by Git; `.env.example` contains only a placeholder.
- The local `create_all()` helper creates missing tables but does not version schema changes. Adopt Alembic migrations before maintaining production data.
- Configure HTTPS, restricted database access, managed secrets, logging, backups, and operational monitoring before any deployment.

Database exceptions are translated into generic HTTP errors so the API response does not expose connection strings or internal SQL details. Production logging and alerting still need to be configured for operators to diagnose failures safely.

## AI roadmap

The repository name describes the intended direction; AI capabilities are **not implemented yet**. Any future AI work should be added as a separate, reviewable service boundary rather than running model inference inside the HTTP route handlers.

Potential milestones:

1. Add authorization, consent, and audit events before storing sensitive records.
2. Design a data model and document-ingestion workflow with validation, access controls, and retention rules.
3. Add an independently deployable model or inference adapter with explicit input/output schemas and timeouts.
4. Evaluate model quality, privacy, bias, and failure behavior on representative, approved data before release.
5. Add monitoring, versioned prompts/models, human review, and clear user-facing limits for any health-related output.

Any future clinical-facing feature would require appropriate domain, privacy, security, and regulatory review. It must not be presented as a diagnostic or treatment tool without that work.

## Contributing

Keep pull requests focused, describe the behavior being changed, and update this README when setup steps or API behavior change. Never include secrets, real personal data, or unapproved clinical data in commits, logs, or examples.

## License

This project is distributed under the MIT License. See [`LICENSE`](LICENSE).
