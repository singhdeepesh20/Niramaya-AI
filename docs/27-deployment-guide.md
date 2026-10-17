# Deployment guide

This repository supplies application code and CI checks, not a deployment platform. No Docker, Terraform, Kubernetes or cloud release workflow is checked in. The operator must provide TLS termination, process supervision, network security, secret injection, database/S3/Qdrant provisioning, backups, monitoring and rollback.

## Release sequence

1. Review `main` and CI status; build frontend and install pinned/approved dependencies from lock/manifests.
2. Provision PostgreSQL with a schema migration owner and a separate least-privilege runtime role (`NOSUPERUSER`, no `BYPASSRLS`, not owner of RLS-protected tables). Verify connection/network/TLS policy.
3. Inspect Alembic revision/schema, backup, rehearse reviewed migrations on isolated restored data, then run `alembic upgrade head` with migration credentials.
4. Provision private S3 and least-privilege IAM. Verify bucket region, encryption, public-access block, bucket policy and ACL read-only; grant object access only for intended bucket/prefix. Do not let app change bucket security settings.
5. Provision/verify Qdrant collection with configured model dimension and cosine distance. Current indexing code creates a missing collection; use a dedicated collection and permission policy to control that first-write behavior. Pin/preload the embedding model.
6. Configure LLM provider/model only after privacy, contract, retention and data transfer review. It receives user question and retrieved evidence when generation is enabled.
7. Inject secrets from an approved secret manager/role, start API and worker as separate managed processes, configure explicit HTTPS frontend origins and frontend public API URL.
8. Check DB-only `/health`; separately inspect worker job health, S3 read-only check, indexing status and provider connectivity using synthetic data. Confirm logging redaction and backups.
9. Roll back application artifacts only with schema compatibility plan; migration downgrade may lose data and is not an automatic rollback strategy.

Consult [deployment runbook](deployment.md), [migration procedure](11-database-migrations.md), [S3](12-file-storage-and-s3.md), and [operational runbooks](36-operational-runbooks.md). Live service operation is environment-specific and must be evidenced independently.
