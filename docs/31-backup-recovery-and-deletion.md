# Backup, recovery and deletion

No database backup/restore or S3 retention automation is included in this repository. The deployment owner must define encrypted backups, point-in-time recovery, object versioning/retention, restore tests, RPO/RTO, region and access controls.

## Current deletion behavior

Document deletion is an owner-only API request that initiates deletion state/job. Worker deletes the S3 object, deletes matching Qdrant points with server-controlled owner/document filters if configured, then deletes the PostgreSQL document row; foreign-key cascades remove entities/pages/tables/chunks and related document-owned rows where schema FKs define cascades. Chat rows are user-scoped but are not document children; citations in previous messages are not automatically purged when one document is removed.

If S3 deletion succeeds but Qdrant deletion fails, the job retries and the DB row remains in deletion-pending state; retrieval excludes that state. Exhausted retries can leave external orphan state and requires operator reconciliation. Qdrant is not a backup. Presigned links issued before deletion may remain usable until expiry or object removal.

## User/account erasure gap

No self-service account deletion or coordinated cross-service erasure endpoint is present. User FK cascades in PostgreSQL are not enough to delete S3 objects or Qdrant vectors. A future erasure workflow needs to enumerate owned docs/objects/vector points, cancel/await jobs, clean each service idempotently, delete chat history, record completion safely, and account for backups/retention. Do not claim full erasure until all stores and backups are covered and tested.

## Recovery

Restore PostgreSQL using its operator-managed backup procedure, then verify Alembic revision and RLS policies. S3 originals can be reprocessed if object retention and metadata survive. Chunks/vectors can be regenerated from current-generation extracted pages when code/model/collection compatibility is maintained. Recovery procedures need a disposable rehearsal; none is verified by the unit suite.
