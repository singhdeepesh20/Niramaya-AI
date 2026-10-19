# Release validation checklist

Use one copy per release and environment. Record source commit, image digests, approver, time, and evidence in the deployment system. Mark each item `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`; never infer live-service status from CI. Use synthetic identities and documents for staging.

## CI and artifacts

- [ ] Backend unit/security tests and dependency audits pass.
- [ ] Frontend lint, type check, production build, and production dependency audit pass.
- [ ] Alembic upgrades a disposable PostgreSQL instance to the expected head; schema, key indexes, and forced tenant RLS checks pass.
- [ ] API, worker, and frontend container builds pass; runtime users and health checks are reviewed.
- [ ] No `.env`, credentials, medical samples, local databases, or test output is present in the diff or image build context.
- [ ] Record the source commit and immutable image digests; review dependency/security findings and base-image provenance.

## Staging isolation and migration

- [ ] Staging database, schema-migration identity, and runtime identity are separate from production.
- [ ] Staging S3 bucket or isolated prefix and policy, Qdrant collection, JWT key, and LLM configuration are distinct from production.
- [ ] Confirm staging has no access path to production patient records or production credentials.
- [ ] Inspect current revision, tables, constraints, indexes, and RLS on the staging target using read-only queries.
- [ ] Verify a recoverable staging backup, apply reviewed forward migrations with the migration identity, then verify schema and API behavior.
- [ ] Run synthetic-user cross-tenant checks for documents, chat, citations, vectors, and deletion paths.
- [ ] Exercise worker retry, lease recovery, and pending-job compatibility with previous and new application versions.

## Recovery and data lifecycle

- [ ] Restore a staging backup into an isolated environment and record restore duration and data-loss window.
- [ ] Reconcile restored document metadata with private source objects; confirm object versioning/lifecycle and encryption from the provider.
- [ ] Rebuild a missing vector index in an isolated collection from canonical authorized PostgreSQL chunks and verify model/dimension/filter compatibility.
- [ ] Verify account-wide erasure workflow, retries, duplicate requests, worker races, external cleanup, and backup-retention behavior. **Current status: BLOCKED — no account-wide erasure workflow is implemented.**
- [ ] Confirm retention, legal holds, provider-side retention, backup expiration, RPO, and RTO are approved and documented.

## Operational readiness and promotion

- [ ] API readiness, worker progress/age, database, object storage, vector service, model loading, and provider checks are independently monitored.
- [ ] Confirm alerts, redacted logs, on-call ownership, and incident/recovery runbooks.
- [ ] Approve the frontend/API compatibility plan, worker handling of queued jobs, and expand-and-contract migration sequence.
- [ ] Deploy the exact staging-verified image digests. Stop promotion on any failed migration, isolation, recovery, or critical user-journey check.
- [ ] Obtain explicit production environment approval; production deployment is not triggered by CI success alone.
- [ ] Verify readiness and critical synthetic journey after promotion; retain previous artifacts and the approved forward-recovery procedure.

## Current repository assessment

CI definitions include disposable PostgreSQL migration/schema validation and local image builds. This does not prove a live deployment, cloud access, backup restoration, or account erasure. Production readiness remains **BLOCKED** until account-wide erasure, backup/restore drills, hosting-specific staging, provider controls, and production operating procedures are implemented and verified.
