# Backend architecture

## Request lifecycle

`create_app` in `app/main.py` registers routers, CORS when explicit origins exist, request IDs, safe handlers for validation/HTTP/database/unexpected errors, and a lifespan that disposes the async engine. It does not create tables or run Alembic. `get_db` yields and closes an `AsyncSession`; PostgreSQL connection attempts use a five-second timeout.

Routes validate Pydantic DTOs and depend on `get_current_user` when protected. Domain operations use SQLAlchemy repositories/helpers. Public DTOs exclude password hashes, object keys and raw provider errors. HTTP request-ID values are accepted only if they match a bounded safe character set; otherwise a UUID is generated.

## Async/external work

Boto3 and CPU PDF parsing are synchronous; storage calls run in a thread pool and document processing uses `asyncio.to_thread`. HTTP calls to Qdrant and the LLM use `httpx.AsyncClient` with configured timeouts. The outbox worker is a separately run polling process; API health does not attest to worker health.

## Errors and rate limits

`APIError` returns a safe error code/message and request ID. SQLAlchemy connection/interface failures map to 503; other database errors map to generic 500 and logs include request ID plus exception type only. Login and assistant limits are per-process, per-client-IP (`10/60s`, `30/60s`). They are not shared across replicas and may use an untrusted proxy address unless deployment proxy trust is configured carefully.

See [API reference](08-api-reference.md), [error and retry model](22-error-handling-and-retries.md), and [observability](23-logging-monitoring-and-health.md).
