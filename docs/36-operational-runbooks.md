# Operational runbooks

These are safe operating sequences, not proof that the external environment is provisioned.

## API and worker startup

1. Inject validated settings; keep credentials out of shell history and output.
2. Check DB connectivity and deployed migration revision. Apply reviewed migrations with the schema owner only after backup/rehearsal.
3. Start API under process supervision and start `python -m app.documents.worker` as a separate process.
4. Check `/health` for database only; inspect worker logs/queue age separately.

## Stuck document

1. Ask owner to inspect `status` and `history`; use `request_id` for API-side failures.
2. Check safe stage and job reason codes, attempts and lease timestamps without logging source text.
3. For process failure, determine whether failure is retryable or source is invalid; owner-only reprocess creates a new generation.
4. For index failure, inspect model path/dimension and collection compatibility; use owner-only reindex (does not rerun OCR). Ensure the configured collection is the intended isolated environment because code may create a missing collection.

## Stuck deletion

1. Confirm document is `deletion_pending`; do not manually delete its DB row first.
2. Inspect delete-job attempt/status and safe category. Check scoped S3 and Qdrant permissions for that owner/document.
3. Restore required credentials/permissions and let bounded retry run; if exhausted, use an approved, logged operator cleanup procedure and then reconcile DB state.
4. Verify object/vector cleanup and DB cascade without printing source content or keys.

## Suspected credential exposure

Revoke/rotate key first; update secret manager; restart services; invalidate JWTs if signing secret; inspect service audit logs; scan Git history/artifacts. Do not paste rotated values into chat or add them to a ticket. History rewrite requires explicit coordination/approval.

Database and S3 detail: [migration guide](11-database-migrations.md), [S3 operations](12-file-storage-and-s3.md), [document runbook](operations/document-processing-runbook.md), [index recovery](operations/reindexing-and-recovery.md).
