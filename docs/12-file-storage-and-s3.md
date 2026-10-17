# File storage and S3

The `S3Storage` class in `app/storage/s3.py` configures a regional Boto3 S3 client lazily. It uses explicit AWS key/secret/session-token settings only when provided; otherwise Boto3's credential provider chain applies (profile, environment, role, etc.). `credential_source()` reports only provider method, never a key. Bucket configuration comes from `AWS_REGION` and `S3_BUCKET_NAME`.

## Upload path

The authenticated upload route checks filename suffix, claimed MIME type, size and leading signature. It creates `users/{verified_user_uuid}/documents/{random_uuid}`, rolls back the open DB transaction, uploads the file privately with content type/disposition metadata, then persists the metadata and process outbox job in PostgreSQL. If the SQL transaction fails after S3 upload, it attempts object cleanup and logs only error categories. Because S3 and PostgreSQL are not atomic, a cleanup failure can leave an orphan that needs operational reconciliation.

## Access and privacy

The application never sets public ACLs or changes bucket policy. It returns time-limited `GetObject` URLs only after owner lookup; default expiry is five minutes (60–900 seconds). Anyone possessing a presigned URL can use it until expiry, so treat it as a bearer secret. Storage check is read-only: HeadBucket and checks for public access block, bucket policy status and ACL. Lack of permission may leave a privacy check `unverified`; it is not a pass.

## Deletion

Owner deletion marks the document `deletion_pending` and creates a delete job. Worker cleanup deletes the S3 key and, if configured, Qdrant points filtered by both authenticated job owner and document ID; only after external cleanup succeeds does it delete PostgreSQL document data and cascade children. Failure is retried with bounded job attempts; a failed cleanup can retain external bytes/vectors and the row remains available for retry. This is not proof of backups/replicas being erased.

## Verification and setup

The storage check does **not** call AWS STS and does not report the caller's AWS account identity. It performs S3 bucket requests (HeadBucket plus read-only privacy configuration checks) only; it does not perform a synthetic upload and therefore does not prove `PutObject`/`DeleteObject` access. Live AWS status requires a successful check under the intended IAM principal and a separately approved synthetic write/delete if write permissions need verification. Unit tests replace the service with `FakeStorage`; they do not verify bucket, IAM, region or public-access settings. Use the least-privilege guidance in [deployment](deployment.md) and inspect bucket settings manually before real medical data is uploaded. See [error categories](22-error-handling-and-retries.md).
