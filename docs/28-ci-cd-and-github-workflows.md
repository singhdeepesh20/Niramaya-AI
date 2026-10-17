# CI/CD and GitHub workflows

`.github/workflows/backend.yml` runs on pushes and pull requests targeting `main`, grants `contents: read`, sets Python 3.12, installs `requirements.txt`, compiles `app`/`tests`, and runs pytest. Tests use their own SQLite fixture and do not require cloud credentials in a clean GitHub checkout.

`.github/workflows/frontend.yml` runs on the same events with Node 20 and `npm ci`, then `npm run lint`, TypeScript `--noEmit`, and `npm run build`. It is a validation workflow, not deployment. It does not publish artifacts or connect to cloud services. `contents: read` is the declared permission; no repository secrets are required for normal CI.

## Gaps

No dependency vulnerability/SBOM scan, secret scanning configuration, migration-vs-PostgreSQL service job, browser E2E, coverage gate or deploy/release workflow is present. Add these in separately scoped changes after choosing tools and service versions; integration CI must use isolated disposable resources and synthetic data.
