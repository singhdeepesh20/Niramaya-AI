# Niramaya-AI

**An asynchronous FastAPI and PostgreSQL foundation for a healthcare-oriented AI project.**

Niramaya-AI is a learning-stage backend prototype built with Python 3.12+, FastAPI, SQLAlchemy's async API, asyncpg, and PostgreSQL. It currently demonstrates a small user-profile workflow and a browser interface on top of that API.

> **Project status:** this repository does not yet include an AI/ML model, authentication, patient records, or clinical functionality. It is not a medical product. Do not submit real patient information or use it to guide clinical decisions.

## What is implemented

- A FastAPI application with a same-origin HTML/CSS/JavaScript frontend.
- Async SQLAlchemy database access using `AsyncSession` and the `asyncpg` driver.
- A `users` table with an integer ID, name, unique email, and server-generated creation time.
- User creation and lookup endpoints, with duplicate and missing-user responses.
- A database-aware health endpoint and an explicit local table-initialization command.

## Architecture

```mermaid
flowchart TD
    Browser[Browser UI<br/>frontend/] -->|HTTP| App[FastAPI app<br/>app/main.py]
    App --> Router[Users router<br/>app/api/users.py]
    Router --> Schema[Pydantic schemas<br/>app/schemas/user.py]
    Router -->|Depends get_db| Session[AsyncSession]
    Session --> ORM[SQLAlchemy model and queries]
    ORM --> Driver[asyncpg]
    Driver --> DB[(PostgreSQL)]
    Config[.env settings<br/>app/core/config.py] --> Engine[Async engine and pool]
    Engine --> Session
    Init[Local table initializer<br/>app/db/init_db.py] --> ORM
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
├── api/users.py        # User HTTP endpoints
└── schemas/user.py    # Pydantic request and response models
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
```

Replace `YOUR_PASSWORD` locally. The URL uses the SQLAlchemy `postgresql` dialect with the async `asyncpg` driver. Never commit `.env` or place credentials in source code.

### Initialize and run

```bash
python -m app.db.init_db
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/> for the browser interface or <http://127.0.0.1:8000/docs> for interactive API documentation. If the database already exists, skip `createdb`; run the initializer after configuring `.env`.

The initializer uses SQLAlchemy `create_all()` for local development only. It does not run on application startup or per request. Use Alembic migrations to evolve schemas in a deployed environment.

## API reference

| Method | Path | Purpose | Successful response |
| --- | --- | --- | --- |
| `GET` | `/health` | Check PostgreSQL connectivity | `200` with `{"status":"ok","database":"connected"}` |
| `POST` | `/users/` | Create a user | `201` with the created user |
| `GET` | `/users/{user_id}` | Fetch a user by numeric ID | `200` with the user |

### Create a user

```bash
curl -X POST http://127.0.0.1:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{"name":"Deepesh","email":"deepesh@example.com"}'
```

The request body is validated before database work. A successful response includes the generated `id` and `created_at` values. Submitting an email that already exists returns `409 Conflict`.

### Fetch a user

Use the ID returned by the create request:

```bash
curl http://127.0.0.1:8000/users/1
```

An unknown ID returns `404 Not Found`. Invalid request data returns `422 Unprocessable Entity`. Unexpected database failures return a generic error response; internal SQL and credentials are not included in API error messages. If PostgreSQL is unavailable, `GET /health` returns `503 Service Unavailable`.

The browser UI at `/` offers the same health, create, and lookup workflows. It calls these same-origin endpoints, so a separate frontend development server and CORS configuration are not required.

## Frontend workspace

The browser workspace is intentionally built with static HTML, CSS, and JavaScript. It includes:

- A service-health panel with checking, connected, and unavailable states plus a manual retry.
- A user creation form that shows request progress and places a successful profile ID into the lookup field.
- A lookup card that renders profile details safely as text and offers a copy-ID action.
- A project-status panel that identifies the current prototype boundaries and links to the API docs and OpenAPI schema.
- Responsive layouts, keyboard skip navigation, visible focus states, reduced-motion support, and live status announcements.

The UI sends same-origin requests to `/health` and `/users/`. Requests time out after ten seconds and display concise, user-facing errors. No browser-side secrets or external font services are required.

## Security and deployment status

This codebase is a local development foundation, not a deployment-ready healthcare service.

- **Authentication and authorization are not implemented.** The user endpoints are currently public to anyone who can reach the app. Do not expose them to the internet as-is.
- **The user model is only a demonstration.** It stores a name and email; it is not a patient model and has no consent, access-control, or audit trail.
- **Do not use real patient or other sensitive personal data** with this prototype.
- Keep real credentials in a local or deployment secret store. `.env` is ignored by Git; `.env.example` contains only a placeholder.
- The local `create_all()` helper creates missing tables but does not version schema changes. Adopt Alembic migrations before maintaining production data.
- Configure HTTPS, restricted database access, managed secrets, logging, backups, and operational monitoring before any deployment.

Database exceptions are translated into generic HTTP errors so the API response does not expose connection strings or internal SQL details. Production logging and alerting still need to be configured for operators to diagnose failures safely.

## AI roadmap

The repository name describes the intended direction; AI capabilities are **not implemented yet**. Any future AI work should be added as a separate, reviewable service boundary rather than running model inference inside the HTTP route handlers.

Potential milestones:

1. Add authentication, authorization, consent, and audit events before storing sensitive records.
2. Design a data model and document-ingestion workflow with validation, access controls, and retention rules.
3. Add an independently deployable model or inference adapter with explicit input/output schemas and timeouts.
4. Evaluate model quality, privacy, bias, and failure behavior on representative, approved data before release.
5. Add monitoring, versioned prompts/models, human review, and clear user-facing limits for any health-related output.

Any future clinical-facing feature would require appropriate domain, privacy, security, and regulatory review. It must not be presented as a diagnostic or treatment tool without that work.

## Contributing

Keep pull requests focused, describe the behavior being changed, and update this README when setup steps or API behavior change. Never include secrets, real personal data, or unapproved clinical data in commits, logs, or examples.

## License

This project is distributed under the MIT License. See [`LICENSE`](LICENSE).
