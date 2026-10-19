# Deployment and release checklist

Deployment is environment-specific. CI passing does not prove that PostgreSQL, S3, Qdrant, the embedding model, or Groq is reachable. Keep a dated verification record for each environment and mark any service that was not actually exercised as blocked or unverified.

## Container builds

Build the API and worker as separate targets from the same locked Python runtime. Both targets run as the non-root `app` user; the worker uses the real module entry point and has no API-only HTTP probe:

```bash
docker build --target runtime -f Dockerfile.api -t niramaya-ai-api:local .
docker build --target worker -f Dockerfile.api -t niramaya-ai-worker:local .
docker run --rm --env-file .env -p 8000:8000 niramaya-ai-api:local
docker run --rm --stop-timeout 300 --env-file .env niramaya-ai-worker:local
```

The worker handles `SIGTERM`/`SIGINT`, completes its current queue iteration, and disposes its database engine before exit. Configure the orchestrator's termination grace period to accommodate the longest permitted job. Monitor persisted job age and failures separately; the worker intentionally has no HTTP health check.

Build the Next.js standalone image from `frontend/`. It uses Node 24.21.0 and a non-root runtime user. The API base URL is public browser configuration and is embedded at build time; never pass credentials through build arguments:

```bash
cd frontend
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com -t niramaya-ai-web:local .
docker run --rm -p 3000:3000 niramaya-ai-web:local
```

The Python 3.12 image uses hash-checked dependencies; frontend dependencies use the npm lockfile. Node is pinned to a supported patch release. Base image tags and OS package repositories remain mutable; they are not digest-pinned and builds are not byte-for-byte reproducible. CI builds API, worker, and frontend images, but a successful build does not prove deployment or cloud connectivity. Migrations remain an explicit operator-controlled deployment step and are not run by the API or worker container at startup.

## Local integration stack

`compose.yaml` is for disposable local development only. It starts PostgreSQL, applies Alembic migrations as a one-shot service, then starts API, worker, and frontend. It uses a named local volume and fixed development-only database/JWT credentials, does not load `.env`, and does not configure AWS, Qdrant, or Groq. Use synthetic data only. Never point this Compose file at a production database or reuse these credentials elsewhere.

```bash
docker compose -f compose.yaml config
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail=100 api worker migrate
curl --fail http://localhost:8000/health
docker compose -f compose.yaml down
```

`docker compose down` preserves the local named volume. To erase this disposable local database explicitly, use `docker compose -f compose.yaml down --volumes` only after confirming it contains no data you need. The API waits for successful completion of the local migration service; `/health` checks the database connection, not migration completeness. Compose does not configure or mutate production cloud resources.

## Staging and promotion

Provision staging independently: separate database and credentials, separate S3 bucket (preferred) or tightly isolated prefix and policy, distinct Qdrant collection/instance, separate JWT and provider keys, and synthetic users/documents only. CI receives no production database URL or cloud secrets. The repository has no deployment platform configuration, registry publishing, protected-environment promotion, or production deploy workflow. Configure those controls in the selected hosting platform; require review and an explicit approval gate for production, promote the exact image digest validated in staging, and retain its source commit and digest. Do not infer branch protection or approvals from these workflow files.

## Configuration and secret delivery

- Provide settings from a secret manager or protected process environment. Never bake `.env`, API keys, database passwords, or JWT signing keys into an image, frontend bundle, GitHub Actions artifact, or source repository.
- Set a unique strong `JWT_SECRET_KEY` per environment and configure exact `FRONTEND_ORIGINS` values. Serve the API and frontend over HTTPS in deployed environments.
- Use a PostgreSQL TLS connection where supported. Keep runtime and migration credentials separate; the application should not run as the schema owner, a superuser, or a role with `BYPASSRLS`.
- Prefer an AWS IAM role or short-lived credentials. If static temporary credentials are used, provide the session token as well as the access-key pair.
- Keep Qdrant and LLM keys server-side. The browser receives only API responses and a bearer token; it must never receive provider keys.

## Database release procedure

1. Take and verify a recoverable backup or snapshot using the database's approved process.
2. Inspect the current Alembic revision, table/column differences, constraints, and role permissions with an authorized migration owner. An empty or unreadable revision table does not imply an empty database.
3. CI applies the complete migration chain to a disposable PostgreSQL 16 service and checks the expected head, key schema objects, and forced tenant RLS. Rehearse target-specific migrations against an isolated database matching the target's PostgreSQL version and schema baseline as well.
4. Inject the migration-owner DSN as `DATABASE_URL` only for the Alembic process through the approved secret manager; `alembic/env.py` reads that setting. Keep the API's runtime DSN restricted to application data operations.
5. Apply the reviewed migration with `alembic upgrade head`, then verify the resulting schema and application behavior.

Do not use `Base.metadata.create_all()`, `alembic stamp head`, destructive reset commands, or broad runtime grants to bypass schema drift. Prefer a reviewed forward migration for production. Do not run a downgrade without a data-retention and recovery review.

## Storage and retrieval services

### Amazon S3

- Confirm the configured region and bucket using the intended deployment identity. Verify private access settings before uploading any sensitive file.
- Keep Block Public Access enabled and do not grant public ACL or policy access. Restrict object actions to the required bucket and server-generated user object-key prefix.
- Permit `s3:ListBucket` on the bucket for the connectivity check; scope `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` to the application's object prefix. The read-only privacy check also needs `s3:GetBucketPublicAccessBlock`, `s3:GetBucketPolicyStatus`, and `s3:GetBucketAcl`. Add KMS access only when the bucket's encryption configuration requires it.
- Use a synthetic object for an approved integration test. Confirm upload/download integrity, then remove only the unique object created by that test.

### Qdrant and embeddings

- Use HTTPS and a project-scoped API key. Confirm the configured collection exists before indexing production documents.
- The default model configuration expects 384-dimensional vectors and collection creation uses cosine distance. Confirm the actual model's vector length and the existing collection's size/distance before indexing; never recreate a populated collection to mask a mismatch.
- Point payloads must carry server-generated user/document identifiers, chunk ID, extraction generation, and model metadata. Retrieval must apply server-controlled owner filters and revalidate every candidate in PostgreSQL.
- Confirm the exact configured model can load in the deployed image or local cache. A configured model name alone is not evidence that embeddings can be produced.

### Groq or another configured LLM

- Verify the configured model with a minimal synthetic request before enabling generation.
- Confirm provider data-handling terms and organizational approval before sending any health information. The API should send only authorized evidence and must have timeouts and safe provider-error handling.
- Keep evidence-only answers available if generation is disabled or the provider is unavailable. Do not describe generated output as a diagnosis.

## Runtime topology and health

- Run the FastAPI service and durable document worker as separate monitored processes. Restart both after secret or configuration changes.
- Configure the API's exact frontend CORS origin; terminate TLS at a trusted proxy and preserve request IDs.
- `/health` verifies database connectivity only. Add deployment-level monitoring for worker progress and explicitly approved S3, Qdrant, and model checks; do not report those services healthy based only on `/health`.
- Replace process-local login and question rate limits with shared enforcement when running multiple API processes.
- Use encrypted backups, restore exercises, access reviews, alerting, and restricted retention for medical data and logs.

## Rollback and limitations

- Keep a previous application artifact available for application rollback. Coordinate schema compatibility before reverting application code after a migration; restore from the verified backup or use a reviewed forward fix rather than blindly downgrading.
- Prefer expand-and-contract migrations. A database migration is not rolled back by reverting an image. Do not automate downgrades in production; if a migration is destructive or partially applied, stop promotion and follow the reviewed backup/forward-repair plan.
- CI uses synthetic fixtures and does not hold personal cloud credentials. Live integration results must be verified in the target environment and recorded separately.
- The frontend stores bearer tokens in tab-scoped `sessionStorage`; this increases exposure to injected JavaScript. A production cookie design requires `HttpOnly`, `Secure`, `SameSite`, and CSRF protections.
- This repository does not implement account recovery, MFA, email verification, token revocation, or a complete clinical audit workflow. No regulatory compliance is asserted.
