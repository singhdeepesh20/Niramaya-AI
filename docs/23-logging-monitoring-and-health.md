# Logging, monitoring and health

The application configures loggers for API, documents, worker and RAG subsystems; it does not configure a production log aggregation or metrics exporter. Use deployment infrastructure to collect stdout/stderr with access controls and retention policy.

## Safe events

API requests carry `X-Request-ID` (validated caller ID or generated UUID), echoed to responses and included in database/unhandled error logs. Worker completion logs contain document/job identifiers, page/entity/table counts, duration and state; failure logs contain error type or bounded safe reason code. Document IDs and counts are still sensitive metadata; restrict log access and retention. Never add report text, excerpts, prompts, tokens, presigned URLs, object keys or provider response bodies.

## Health meaning

`GET /health` executes `SELECT 1` and returns status/database connectivity. It does not verify Alembic revision, S3, Qdrant, embedding model availability, Groq, worker liveness, queue depth or actual end-to-end processing. `/api/v1/documents/storage/check` is an authenticated read-only S3/bucket-privacy check; limited IAM may leave checks unverified. Indexing status and processing history endpoints are per-document user views, not global operator metrics.

## Operational signals to add

Recommended (not currently implemented as metrics): API latency/error rates; DB pool/connection saturation; pending/oldest job and retry counts; worker lease recoveries; processing stage duration and review/failure ratios; S3 error categories; indexing backlog/model failure/dimension mismatch; Qdrant latency; LLM timeout/429/503 rates; deletion-pending age. Keep labels free of user IDs, filenames, questions and health values.
