# CI/CD and GitHub workflows

`.github/workflows/backend.yml` runs on pushes and pull requests targeting `main`, grants `contents: read`, sets Python from `.python-version`, installs `requirements-dev.txt` with hash checking, runs Ruff and `pip-audit` against both locks, compiles `app`/`tests`, and runs pytest. Tests use their own SQLite fixture and do not require cloud credentials in a clean GitHub checkout.

`.github/workflows/frontend.yml` runs on the same events with Node from `frontend/.nvmrc` and `npm ci`, then audits production dependencies, runs `npm run lint`, TypeScript `--noEmit`, and `npm run build`. The full audit is not a CI gate because the dev dependency tree currently has a high-severity advisory with no patched upstream release; it is documented and should be reevaluated after updates. It is a validation workflow, not deployment. It does not publish artifacts or connect to cloud services. `contents: read` is the declared permission; no repository secrets are required for normal CI.

## Main branch protection

In GitHub repository settings, protect `main` and require both `Backend CI / test` and `Frontend CI / validate` status checks before merging pull requests. The workflow files declare the checks but do not enable branch protection; verify the repository settings separately.

## Gaps

No dependency vulnerability/SBOM scan, secret scanning configuration, migration-vs-PostgreSQL service job, browser E2E, coverage gate or deploy/release workflow is present. Add these in separately scoped changes after choosing tools and service versions; integration CI must use isolated disposable resources and synthetic data.
