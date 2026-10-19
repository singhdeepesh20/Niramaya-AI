# Deployment guide

The repository contains production-target API, worker, and frontend containers plus CI validation. It does not contain Terraform/Kubernetes/hosting resources, image publishing, or a cloud release workflow. The operator must provide TLS termination, process supervision, network security, secret injection, database/S3/Qdrant provisioning, backups, monitoring and controlled promotion.

## Release sequence

1. Review the source commit and CI status; retain source commit and built image digests.
2. Provision PostgreSQL with a schema migration owner and a separate least-privilege runtime role (`NOSUPERUSER`, no `BYPASSRLS`, not owner of RLS-protected tables). Verify connection/network/TLS policy.
3. Inspect Alembic revision/schema and backup; CI validates the full chain on disposable PostgreSQL, but rehearse target-specific migrations on isolated restored data, then run `alembic upgrade head` with migration credentials.
4. Provision private S3 and least-privilege IAM. Verify bucket region, encryption, public-access block, bucket policy and ACL read-only; grant object access only for intended bucket/prefix. Do not let app change bucket security settings.
5. Provision/verify Qdrant collection with configured model dimension and cosine distance. Current indexing code creates a missing collection; use a dedicated collection and permission policy to control that first-write behavior. Pin/preload the embedding model.
6. Configure LLM provider/model only after privacy, contract, retention and data transfer review. It receives user question and retrieved evidence when generation is enabled.
7. Inject secrets from an approved secret manager/role, deploy API and worker as separate managed processes, configure explicit HTTPS frontend origins and frontend public API URL.
8. Check DB-only `/health`; separately inspect worker job health, S3 read-only check, indexing status and provider connectivity using synthetic data. Confirm logging redaction and backups.
9. Roll back application artifacts only with schema compatibility plan; migration downgrade may lose data and is not an automatic rollback strategy.

Consult [deployment runbook](deployment.md), [migration procedure](11-database-migrations.md), [S3](12-file-storage-and-s3.md), and [operational runbooks](36-operational-runbooks.md). Live service operation is environment-specific and must be evidenced independently.

Do not promote to production before the account-erasure gap, backup/restore rehearsal, approved staging environment, provider configuration, and hosting-specific rollback procedure are resolved. See [data lifecycle and recovery](31-backup-recovery-and-deletion.md) and the [release checklist](release-checklist.md).
