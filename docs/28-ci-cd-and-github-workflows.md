# CI/CD and GitHub workflows

`.github/workflows/backend.yml` runs on pushes and pull requests targeting `main`, grants `contents: read`, sets Python from `.python-version`, installs `requirements-dev.txt` with hash checking, runs Ruff and `pip-audit` against both locks, compiles `app`/`tests`, and runs pytest. Tests use their own SQLite fixture and do not require cloud credentials in a clean GitHub checkout. Separate jobs build API and worker image targets, and apply Alembic migrations to a disposable PostgreSQL 16 service before checking revision, key tables/indexes, and forced tenant RLS.

`.github/workflows/frontend.yml` runs on the same events with Node from `frontend/.nvmrc` and `npm ci`, then audits production dependencies, runs lint, TypeScript `--noEmit`, production build, and builds the frontend container. It is a validation workflow, not deployment. It does not publish artifacts or connect to cloud services. `contents: read` is the declared permission; no repository secrets are required for normal CI.

## Main branch protection

In GitHub repository settings, protect `main` and require both `Backend CI / test` and `Frontend CI / validate` status checks before merging pull requests. The workflow files declare the checks but do not enable branch protection; verify the repository settings separately.

## Delivery boundary and remaining gaps

No image registry publishing, provenance/SBOM attestation, staging deployment, smoke/E2E journey, protected production environment, approval gate, or automated rollback workflow is present. CI has no production database URL or cloud credentials. Configure delivery only after selecting the hosting platform and least-privilege identities; require manual production approval and deploy the exact digest validated in staging. Confirm branch protection and environment approvals in GitHub settings; workflow YAML cannot prove that settings exist. Account-wide erasure and backup restore remain release blockers as documented in `31-backup-recovery-and-deletion.md`.
