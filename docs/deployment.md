# Deployment and release checklist

Deployment is environment-specific. CI passing does not prove that PostgreSQL, S3, Qdrant, the embedding model, or Groq is reachable. Keep a dated verification record for each environment and mark any service that was not actually exercised as blocked or unverified.

## Container builds

Build the API and worker image from the repository root:

```bash
docker build -f Dockerfile.api -t niramaya-ai-api:local .
docker run --rm --env-file .env -p 8000:8000 niramaya-ai-api:local
```

Run the durable worker as a separate process using the same image. Disable the API-only HTTP health check for this worker command and monitor its persisted job progress through the deployment platform:

```bash
docker run --rm --no-healthcheck --env-file .env niramaya-ai-api:local python -m app.documents.worker
```

Build the Next.js standalone image from `frontend/`. The API base URL is public browser configuration and is embedded at build time; never pass credentials through build arguments:

```bash
cd frontend
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com -t niramaya-ai-web:local .
docker run --rm -p 3000:3000 niramaya-ai-web:local
```

The images use versioned Python 3.12 and Node 20 Bookworm tags, non-root runtime users, hash-checked Python dependencies and npm lockfile installation. Base image tags and OS package repositories remain mutable; builds are not byte-for-byte reproducible. Docker build and container health checks must be run in a Docker-enabled environment before release. Migrations remain an explicit operator-controlled deployment step and are not run by the API container at startup.

## Configuration and secret delivery

- Provide settings from a secret manager or protected process environment. Never bake `.env`, API keys, database passwords, or JWT signing keys into an image, frontend bundle, GitHub Actions artifact, or source repository.
- Set a unique strong `JWT_SECRET_KEY` per environment and configure exact `FRONTEND_ORIGINS` values. Serve the API and frontend over HTTPS in deployed environments.
- Use a PostgreSQL TLS connection where supported. Keep runtime and migration credentials separate; the application should not run as the schema owner, a superuser, or a role with `BYPASSRLS`.
- Prefer an AWS IAM role or short-lived credentials. If static temporary credentials are used, provide the session token as well as the access-key pair.
- Keep Qdrant and LLM keys server-side. The browser receives only API responses and a bearer token; it must never receive provider keys.

## Database release procedure

1. Take and verify a backup or snapshot using the database's approved process.
2. Inspect the current Alembic revision, table/column differences, constraints, and role permissions with an authorized migration owner. An empty or unreadable revision table does not imply an empty database.
3. Test the migration chain against a disposable database that matches the target's PostgreSQL version and schema baseline.
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
- CI uses synthetic fixtures and does not hold personal cloud credentials. Live integration results must be verified in the target environment and recorded separately.
- The frontend stores bearer tokens in tab-scoped `sessionStorage`; this increases exposure to injected JavaScript. A production cookie design requires `HttpOnly`, `Secure`, `SameSite`, and CSRF protections.
- This repository does not implement account recovery, MFA, email verification, token revocation, or a complete clinical audit workflow. No regulatory compliance is asserted.
