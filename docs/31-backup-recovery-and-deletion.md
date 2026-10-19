# Backup, recovery and deletion

## Data inventory

This inventory reflects the checked-in application paths. Retention periods, backup copies, and external provider retention are deployment or policy decisions and are not verified here.

| Data | Canonical/current location | Owner boundary and deletion behavior | Backup/recovery and exposure notes |
| --- | --- | --- | --- |
| Account identity and password hash | PostgreSQL `users` | User row; no account-erasure API exists. Authentication is server-side. | Database backups can retain the row; no password or token values should enter logs. |
| Medical document metadata and object key | PostgreSQL `medical_documents` | `user_id` scoping and PostgreSQL RLS; owner document-delete moves through deletion state/job. | Metadata can identify a health record. Restore reconciliation must check the corresponding source object. |
| Original uploaded PDF/image | Private S3 object referenced by `object_key` | Document delete worker calls S3 delete before removing the PostgreSQL document row. Bucket versioning/object-lock/lifecycle state is not verified. | A delete marker or versioned object may remain recoverable; presigned links may live until expiry. |
| Extracted pages, entities, tables, and chunks | PostgreSQL medical page/entity/table/chunk tables | Document foreign-key cascades remove document-owned rows after successful document deletion. User-level erasure is missing. | Canonical extracted content is sensitive; chunks are the rebuild source for vectors. |
| Vector points | Optional Qdrant collection | Document deletion uses server-derived owner/document filters when configured. User-level cleanup is missing. | Qdrant is an index, not a backup; rebuild only into a separately verified collection. |
| Questions, answers, citations | PostgreSQL `health_chat_messages` | Scoped to `user_id`; citations are not automatically scrubbed on one document deletion. Account deletion is missing. | Questions/answers may contain sensitive information. Provider-side retention must be reviewed separately. |
| Processing jobs, state events, and stage runs | PostgreSQL document-processing tables | Scoped to document/user; job leases are retried/recovered, and document deletion can cancel stale jobs. | Operational reason codes are retained in DB; keep logs free of source text and tokens. |
| Temporary processing files | Worker local temporary directory | `TemporaryDirectory` removes extracted working files when its context exits; container filesystem is ephemeral. | Crashes/host behavior and platform snapshots still require deployment controls. |
| Backups, replicas, logs, provider records | Managed infrastructure/external systems | No repository-wide erasure, backup lifecycle, or provider deletion integration. | Retention, access, region, encryption, expiry and restoration are not verified. |

## Backup and restore status

The repository does not implement database backup/restore jobs or S3 replication/lifecycle automation. The actual PostgreSQL host, S3 bucket versioning/encryption/lifecycle, backup retention, and Qdrant snapshot policy have not been verified in this task. A hosting operator must define encryption, access, retention, region separation, RPO/RTO, and tested restoration. Do not describe the system as recoverable from backups until a restore drill has succeeded in an isolated environment with synthetic data.

## Current deletion behavior

Document deletion is an owner-only API request that initiates deletion state/job. Worker deletes the S3 object, deletes matching Qdrant points with server-controlled owner/document filters if configured, then deletes the PostgreSQL document row; foreign-key cascades remove entities/pages/tables/chunks and related document-owned rows where schema FKs define cascades. Chat rows are user-scoped but are not document children; citations in previous messages are not automatically purged when one document is removed.

If S3 deletion succeeds but Qdrant deletion fails, the job retries and the DB row remains in deletion-pending state; retrieval excludes that state. Exhausted retries can leave external orphan state and requires operator reconciliation. Qdrant is not a backup. Presigned links issued before deletion may remain usable until expiry or object removal.

## User/account erasure gap — release blocker

No self-service account deletion or coordinated cross-service erasure endpoint is present. User FK cascades in PostgreSQL are not enough to delete S3 objects or Qdrant vectors. No account-level deletion operation has been added because the model currently has no deletion-pending lifecycle, the job schema is document-scoped, and backup/retention policies and account status requirements are undefined. A partial endpoint would falsely imply erasure and could race with active workers.

Before implementing account erasure, define policy for authentication cutoff and confirmation, retention/legal holds, backup expiration, provider-held prompts, and status access. Then add a durable account-deletion outbox independent of the user row; prevent new API work and stale workers from recreating data; enumerate owner-scoped objects, vectors, chats and jobs; perform idempotent bounded retries; retain only minimal non-sensitive operation state; and mark complete only after defined cross-service verification. Test S3-success/DB-failure, Qdrant outage, worker crash/retry, stale index workers, duplicate requests, and zero-document accounts with two synthetic tenants. Do not delete a PostgreSQL user before external deletion succeeds.

Logical deletion, primary-store deletion, external object/vector deletion, backup expiry, and provider retention are distinct states. This repository does not guarantee immediate backup or third-party erasure. **Account-wide erasure is a production-readiness blocker.**

## Recovery

Restore PostgreSQL using the host's documented operator-managed procedure into an isolated recovery environment. Verify Alembic revision, expected tables/indexes, and forced RLS policies. Reconcile metadata with S3 originals and inspect bucket version/lifecycle behavior before restoring objects. Rebuild missing vectors from authorized PostgreSQL chunks into a new compatible Qdrant collection; validate dimensions, model revision and owner filters before switching configuration. Recovery procedures need a disposable rehearsal; no backup restore, object restore, or Qdrant rebuild was executed or verified here. Do not run destructive restore actions against production as a test.
