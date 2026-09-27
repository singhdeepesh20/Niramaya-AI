# Niramaya-AI asynchronous PostgreSQL backend

A small teaching project showing how a FastAPI request reaches PostgreSQL through SQLAlchemy 2.0's async API and the asyncpg driver. The example stores users; it is a foundation, not a complete authentication system.

## Architecture in plain language

```text
Client → FastAPI → API Router → Dependency Injection → AsyncSession
       → SQLAlchemy → asyncpg → PostgreSQL
```

- **FastAPI** receives HTTP requests, validates inputs using declared types/schemas, calls Python functions, and turns their return values into HTTP responses. Its type-driven validation and generated API docs make it a useful API framework.
- **Router** groups related endpoints. `app/api/users.py` owns user routes; `main.py` assembles routers and app-wide behavior. As the API grows, this keeps the entry point from becoming one long file.
- **Dependency injection** is FastAPI's way to call and provide shared resources to an endpoint. `Depends(get_db)` tells FastAPI to run `get_db` and pass its yielded session as the endpoint's `db` argument. The endpoint does not create or manage the connection itself.
- **AsyncSession** is SQLAlchemy's asynchronous unit of work. It tracks objects and pending changes, issues queries, and coordinates transactions using an async database connection. A session is not itself a permanent database connection; it checks out a connection from the engine pool when needed.
- **SQLAlchemy** is the Python database toolkit and ORM (object-relational mapper). It maps Python classes and objects to relational tables and rows, and provides a query/transaction API. For example, a Python `User(name="Deepesh", ...)` is tracked by SQLAlchemy; SQLAlchemy compiles an INSERT statement; the database executes it. The mapping does not mean PostgreSQL stores Python objects: PostgreSQL stores rows and values.
- **asyncpg** is the PostgreSQL-specific asynchronous driver. SQLAlchemy's PostgreSQL dialect uses it to encode parameters, send protocol messages, and receive results over the network. The URL's `+asyncpg` selects this driver.
- **PostgreSQL** is the database server. It persists tables and indexes, enforces constraints such as unique email, runs SQL and transactions, and returns results. It is the final authority for stored data.

A compact mental model: Python describes the desired work; SQLAlchemy translates and coordinates it; asyncpg carries database protocol traffic; PostgreSQL performs and persists the work.

## Why this folder structure?

```text
niramaya-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/       # Environment-backed application settings
│   ├── db/         # Engine, session dependency, ORM models, local table setup
│   ├── api/        # HTTP route handlers grouped by feature
│   └── schemas/    # Pydantic request/response shapes
├── frontend/
│   ├── index.html  # Browser page
│   ├── app.js      # Calls the same-origin API
│   └── styles.css  # Layout and visual styling
├── .env            # Local secrets and settings; ignored by Git
├── .env.example    # Safe template to copy
├── .gitignore
├── requirements.txt
└── README.md
```

Each part has one clear job: configuration is not mixed into routes, database mappings are not confused with HTTP validation, and routes can depend on a reusable session provider. The empty `__init__.py` files mark Python packages so imports such as `app.db.database` work consistently. `main.py` is the composition point: it creates the FastAPI app, includes the router, and serves the frontend from `/` and `/static`.

### Configuration: `app/core/config.py`

`Settings(BaseSettings)` uses Pydantic Settings to read typed values from environment variables (and from `.env` here). `DATABASE_URL: str` declares a required setting; if it is missing, startup reports a configuration error instead of silently using an accidental default. `SettingsConfigDict(env_file=".env")` tells it where local development values live. `get_settings` is cached so the settings object is built once. Keeping deployment-specific configuration outside Python lets local, staging, and production environments use different URLs without code edits or committed secrets.

### Database engine and sessions: `app/db/database.py`

The **engine** is SQLAlchemy's long-lived database access hub. It knows the URL and owns a **connection pool**. A pool keeps a limited number of connections available for reuse, rather than establishing a new TCP/database connection for every HTTP request:

```text
Engine → Connection Pool → reusable connections → PostgreSQL
                  Connection 1
                  Connection 2
                  Connection 3 ...
```

This development setup allows 5 pooled connections and up to 10 temporary overflow connections under load. `pool_pre_ping=True` checks a pooled connection before handing it out and replaces stale connections when possible. Pool values should be tuned to the database's connection limit and the number of app workers in a real deployment.

`async_sessionmaker` is a factory for sessions. `AsyncSessionLocal` configures each new session with the engine and async behavior. The engine/pool is process-wide; a session is a short-lived unit of work, normally one request:

```text
Engine → owns pool → supplies a connection when needed
Session → tracks this request's reads, changes, and transaction
```

`get_db` uses `async with` to create a session, `yield` makes it available to FastAPI while the endpoint runs, and leaving the context closes it even if the endpoint raises. Closing releases any checked-out connection back to the pool. `yield` here is a generator dependency with setup before and cleanup after the request.

### SQLAlchemy models: `app/db/models.py`

`Base(DeclarativeBase)` is the SQLAlchemy 2.0 base; subclasses register table descriptions in `Base.metadata`. `User(Base)` is a mapped class and `__tablename__ = "users"` chooses the PostgreSQL table name. `Mapped[int]` and `Mapped[str]` declare the Python type of mapped attributes. `mapped_column()` describes the corresponding column. The id is a primary key; name and email are required; email is unique and indexed for fast lookup; `created_at` gets its value from PostgreSQL's `now()` default.

Conceptually:

```text
Python class User (attributes)
        ↓ Declarative mapping
SQLAlchemy table/column metadata
        ↓ create_all for local setup; migrations later
PostgreSQL table users(id, name, email, created_at)
```

Defining a model alone does not create a table. Run the explicit initialization command below for local development. Production schema changes should use Alembic migrations, which record and apply controlled, reviewable schema revisions; `create_all()` creates missing tables but does not safely evolve existing schemas.

### Pydantic schemas: `app/schemas/user.py`

A **SQLAlchemy model** describes persisted database rows and relationships. A **Pydantic schema** describes the shape of data accepted from or returned to an API client. `UserCreate` validates a nonempty bounded name and email address before the endpoint runs. `UserResponse` declares the safe response fields. Its `from_attributes=True` setting lets Pydantic read those values from a SQLAlchemy object's attributes. Separating them avoids treating every database column as public API input/output.

### User routes and request handling: `app/api/users.py`

The router declares a `POST /users/` creation endpoint and `GET /users/{user_id}` lookup. FastAPI validates the POST JSON into `UserCreate` and obtains `db` through `Depends(get_db)`. Creation first checks for an existing email and returns 409 if found. It then makes a `User`, and `db.add(user)` marks it for insertion in this session; it does not immediately send SQL. `await db.commit()` asks SQLAlchemy to flush pending changes and commit the transaction; through asyncpg PostgreSQL executes the INSERT and enforces constraints. `await db.refresh(user)` queries server-generated values (the id and timestamp) back onto the Python object. The response schema turns it into JSON.

The pre-check gives a friendly common error, while the unique index is still essential: simultaneous requests can both pass the pre-check. An `IntegrityError` from that unique index is rolled back and returned as 409. Other SQLAlchemy database failures are rolled back and mapped to a generic 500 message. Internal SQL, connection strings, and stack traces remain in server logs rather than client responses. A missing user returns 404.

For GET, `select(User).where(...)` constructs a typed SQLAlchemy query. `await db.execute(...)` runs it asynchronously; the SQLAlchemy PostgreSQL dialect sends it through asyncpg to PostgreSQL. `result.scalar_one_or_none()` extracts the one matching ORM object, or `None` when there is no row.

### App assembly and health check: `app/main.py`

`main.py` creates the FastAPI application and includes the users router. `GET /health` runs a tiny `SELECT 1` connectivity probe and returns the requested status JSON when PostgreSQL responds. A health check lets operators and deployment systems detect an unavailable dependency. A production service often separates process liveness from readiness; this endpoint is a simple database-aware readiness-style check. The lifespan hook disposes of the process-wide engine pool when the app shuts down.

The health probe is a simple connectivity check and the one raw SQL statement in this example; normal CRUD uses SQLAlchemy expressions. No schema creation runs on HTTP requests.

## PostgreSQL, environment, and Git

This project assumes PostgreSQL is installed and running locally on port 5432 with a role named `postgres`. Create the database from a terminal:

```bash
createdb -h localhost -p 5432 -U postgres niramaya
```

Or in `psql`, run `CREATE DATABASE niramaya;` while connected as a role allowed to create databases. If your local server requires a password, enter it at the prompt; do not put it in a shell command or commit it.

The URL format is:

```text
postgresql+asyncpg://username:password@host:port/database
postgresql + asyncpg + postgres + YOUR_PASSWORD + localhost + 5432 + niramaya
```

`postgresql` selects the database dialect, `+asyncpg` selects the async driver, the credentials authenticate the role, host and port locate the server, and the last path component selects the database. In this project, `.env` has a placeholder only:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/niramaya
```

Replace `YOUR_PASSWORD` locally with your PostgreSQL password. `.env.example` is the safe template for other developers. `.gitignore` excludes `.env`, virtual environments, and Python cache files. Real credentials should not enter Git history: anyone with repository access could use them, and deleting them later does not erase old commits. If a real secret was ever committed, rotate it.

## Install and run

From the project root, using Python 3.12 or newer:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and replace YOUR_PASSWORD with your local PostgreSQL password.
createdb -h localhost -p 5432 -U postgres niramaya
python -m app.db.init_db
uvicorn app.main:app --reload
```

If the database already exists, skip `createdb`. The initialization command creates the mapped tables once for local development; it is intentionally separate from app startup and request handling. Later, replace this workflow with Alembic migration commands.

## API examples

Health check:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","database":"connected"}
```

Create a user (successful response is 201):

```bash
curl -X POST http://127.0.0.1:8000/users/ \\
  -H 'Content-Type: application/json' \\
  -d '{"name":"Deepesh","email":"deepesh@example.com"}'
```

Fetch the returned id, for example:

```bash
curl http://127.0.0.1:8000/users/1
```

Repeating a create with the same email returns 409. A missing id returns 404. The interactive docs are at `http://127.0.0.1:8000/docs`.

The browser interface is at `http://127.0.0.1:8000/`. It checks database health, submits the create-user form to `POST /users/`, and looks up a user through `GET /users/{user_id}`. The frontend is plain HTML, CSS, and JavaScript served by FastAPI, so it calls same-origin URLs and does not need a separate frontend server or CORS configuration.

## Complete POST request lifecycle

1. **Client sends HTTP request** with JSON body containing name and email.
2. **FastAPI receives request** and selects the registered app.
3. **Router matches `/users/`** to `create_user` for POST.
4. **Pydantic validates JSON** against `UserCreate`; invalid names/emails get a 422 response before database work.
5. **`Depends(get_db)` executes** because the endpoint declares a database dependency.
6. **An `AsyncSession` is created** by `AsyncSessionLocal`; it will check out a pooled connection as needed.
7. **SQLAlchemy creates database operations** from `select(User)` and the new mapped `User` instance.
8. **asyncpg communicates with PostgreSQL** using the PostgreSQL protocol, asynchronously.
9. **PostgreSQL executes the SELECT/INSERT** and enforces the unique email index. The existence check's SELECT happens before the INSERT.
10. **SQLAlchemy commits the transaction** after `db.add`; the INSERT is flushed and committed by `await db.commit()`.
11. **The object is refreshed** so generated id and timestamp are present in Python.
12. **Pydantic creates the response** using `UserResponse` and the ORM object's attributes.
13. **FastAPI sends JSON** with HTTP 201 to the client.
14. **The database session closes** as FastAPI finishes the yielded dependency; the connection returns to the pool.

If a step fails, FastAPI returns a validation/client error or the route's safe HTTP error. The dependency still closes its session.

## What to learn next

1. Alembic migrations
2. Password hashing
3. Authentication
4. JWT
5. User → Patient relationships
6. PostgreSQL transactions
7. Indexes
8. Repository/service architecture
9. Redis
10. S3/MinIO
11. Background jobs
12. Document upload pipeline
