# Niramaya-AI

**A Python backend foundation for a healthcare-oriented AI project.**

Niramaya-AI is a learning-stage application built with FastAPI, asynchronous SQLAlchemy, and PostgreSQL. It includes a small authenticated user-profile workflow and a same-origin browser interface.

> **Current scope:** authentication, profile data, and database health checks are implemented. AI/ML inference, patient records, and clinical workflows are not. Do not enter real patient information or use this project to make clinical decisions.

## Contents

- [Project status](#project-status)
- [Features](#features)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [API reference](#api-reference)
- [Browser interface](#browser-interface)
- [Security and limitations](#security-and-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)


## Project status

This repository is a developer prototype. It demonstrates how a browser can call an asynchronous API, how the API can store users in PostgreSQL, and how bearer-token authentication can protect account data.

The project does not include an AI model, clinical decision support, patient data storage, or production operations. Its authentication is a foundation for learning and local development, not a complete identity platform.


## Features

- FastAPI application serves the API and the browser interface from one origin.
- Async database access uses SQLAlchemy's `AsyncSession` and the `asyncpg` PostgreSQL driver.
- Registration creates accounts with unique usernames and emails.
- Passwords are stored as Argon2 hashes.
- Login exchanges a username and password for a signed, expiring JWT access token.
- Protected endpoints resolve the token to a database user and limit profile reads to that user.
- Alembic tracks schema changes, including password hashes and usernames.
- A health endpoint checks whether PostgreSQL can be reached.


## Architecture

The application keeps its main responsibilities in separate layers:

```mermaid
flowchart LR
    Browser[Browser UI<br/>frontend/] -->|same-origin HTTP| FastAPI[FastAPI app<br/>app/main.py]
    FastAPI --> Auth[Authentication router<br/>app/api/auth.py]
    FastAPI --> Users[User router<br/>app/api/users.py]
    Auth --> Schemas[Pydantic schemas<br/>app/schemas/]
    Users --> Schemas
    Auth --> Security[Password and JWT helpers<br/>app/core/security.py]
    Auth --> Identity[Current-user dependency<br/>app/api/dependencies.py]
    Users --> Identity
    Identity --> Sessions[Async database session<br/>app/db/database.py]
    Auth --> Sessions
    Sessions --> Models[SQLAlchemy models<br/>app/db/models.py]
    Models --> Driver[asyncpg]
    Driver --> PostgreSQL[(PostgreSQL)]
    Settings[Environment settings<br/>app/core/config.py] --> Sessions
    Alembic[Alembic migrations<br/>alembic/] --> PostgreSQL
```


### Authentication flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser UI
    participant API as FastAPI
    participant Hash as Password hasher
    participant DB as PostgreSQL
    User->>UI: Register username, email, password
    UI->>API: POST /auth/register
    API->>Hash: Hash password with Argon2
    API->>DB: Store profile and password hash
    User->>UI: Sign in
    UI->>API: POST /auth/token (username, password)
    API->>DB: Find account by normalized username
    API->>Hash: Verify submitted password
    API-->>UI: Signed JWT access token
    UI->>API: Protected request with Bearer token
    API->>API: Validate signature and expiration
    API->>DB: Load user identified by token subject
    API-->>UI: Return authorized profile
```


### Request and data flow

The browser sends JSON or form-encoded requests to FastAPI. Pydantic validates request bodies, and route handlers call narrowly scoped security and database helpers. The current-user dependency validates bearer tokens using a fixed HS256 algorithm, reads the user ID from the token subject, and loads that account through a request-scoped async session.

SQLAlchemy maps the user model to PostgreSQL. The asyncpg driver handles database communication. Alembic applies versioned schema changes; the application does not run migrations automatically at startup.


## Technology stack

| Area | Technology |
| --- | --- |
| Runtime | Python 3.12+ |
| HTTP API | FastAPI, Uvicorn |
| Validation and configuration | Pydantic v2, pydantic-settings |
| Authentication | PyJWT, OAuth2 bearer tokens |
| Password hashing | pwdlib with Argon2 |
| ORM and sessions | SQLAlchemy 2.x async API |
| PostgreSQL driver | asyncpg |
| Schema migrations | Alembic |
| Browser interface | HTML, CSS, vanilla JavaScript |


## Repository layout

```text
app/
├── main.py                   # FastAPI app, routers, static UI, health endpoint
├── api/
│   ├── auth.py               # Registration, token, and current-user routes
│   ├── dependencies.py       # Bearer token validation and user resolution
│   └── users.py              # Authenticated profile route
├── core/
│   ├── config.py             # Environment-backed settings
│   ├── identifiers.py        # Username normalization
│   └── security.py           # Argon2 password and JWT helpers
├── db/
│   ├── database.py           # Async engine, session factory, request dependency
│   ├── init_db.py            # Local create_all helper
│   └── models.py             # SQLAlchemy user model
└── schemas/                  # Pydantic request and response contracts
alembic/
├── env.py                    # Migration environment using async settings
└── versions/                 # Versioned database changes
frontend/
├── index.html
├── styles.css
├── app.js
└── favicon.svg
.env.example                  # Safe local configuration template
requirements.txt
```


## Quick start

### Prerequisites

- Python 3.12 or newer.
- PostgreSQL running locally.
- A PostgreSQL role with permission to create and modify the application schema.
- Git and a terminal.

The commands below assume a local database named `niramaya` and a PostgreSQL role named `postgres`. Adjust them for your environment.


### Create a development database

If the database does not already exist, create it with:

```bash
createdb -h localhost -p 5432 -U postgres niramaya
```

You can also create the database using your preferred PostgreSQL administration tool. The application expects the database to be available before you apply migrations.


### Install dependencies

From the repository root, create and activate a virtual environment, then install the pinned dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.


### Configure environment variables

Create a local environment file:

```bash
cp .env.example .env
```

Set the database URL and JWT settings in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/niramaya
JWT_SECRET_KEY=PASTE_A_RANDOM_SECRET_HERE
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Replace the database credentials locally. Generate a unique signing key with `openssl rand -hex 32`. Keep `.env` private; it is ignored by Git.


The application requires `DATABASE_URL` and `JWT_SECRET_KEY`. Token lifetime defaults to 30 minutes and can be configured from 1 to 1,440 minutes with `ACCESS_TOKEN_EXPIRE_MINUTES`.

Use a different, randomly generated JWT key in each environment. Do not reuse the database password, put secrets in source code, or commit real `.env` files. For hosted deployments, provide secrets through the platform's secret manager.


### Apply database migrations

Run Alembic from the repository root:

```bash
alembic upgrade head
```

The migrations can create the users table on a fresh database, add the nullable password-hash column, and add/backfill usernames. Existing rows receive a unique username based on their email and row ID. Rows without a password hash still cannot sign in; account recovery is not implemented.

Use Alembic when evolving an existing database. The optional `python -m app.db.init_db` helper calls SQLAlchemy `create_all()` for local development and does not alter an existing table to match newer model fields.


### Run the application

Start the development server:

```bash
uvicorn app.main:app --reload
```

Open:

- <http://127.0.0.1:8000/> for the browser interface.
- <http://127.0.0.1:8000/docs> for interactive Swagger documentation.
- <http://127.0.0.1:8000/health> for the database connectivity check.

The UI and API share an origin, so a separate frontend server and CORS setup are not needed for local development.


## API reference

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Check PostgreSQL connectivity |
| `POST` | `/auth/register` | Public | Create an account |
| `POST` | `/auth/token` | Public | Exchange username/password for a JWT |
| `GET` | `/auth/me` | Bearer token | Read the signed-in account |
| `GET` | `/users/{user_id}` | Bearer token | Read the signed-in user's own profile |

Successful profile responses contain `id`, `name`, `username`, `email`, and `created_at`. Password hashes are never included in API responses.


### Register an account

Send a JSON request to `POST /auth/register`:

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Example User","username":"example_user","email":"user@example.com","password":"Example-passphrase-123"}'
```

Usernames must be 3–32 characters and may contain letters, numbers, dots, underscores, and hyphens. Matching ignores case. Passwords must be 12–128 characters. Duplicate usernames or emails return `409 Conflict`.


### Sign in and receive an access token

The token endpoint accepts OAuth2 form fields named `username` and `password`:

```bash
curl -X POST http://127.0.0.1:8000/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=example_user' \
  --data-urlencode 'password=Example-passphrase-123'
```

The response contains `access_token` and `token_type`. Send the token in the `Authorization: Bearer <access_token>` header when calling a protected endpoint.


### Access the signed-in profile

Use the issued token to request the current account:

```bash
curl http://127.0.0.1:8000/auth/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

The `/users/{user_id}` endpoint has the same authentication requirement and returns a profile only when the requested ID belongs to the signed-in user. Requests for another user's ID return `404`.

