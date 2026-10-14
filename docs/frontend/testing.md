# Frontend testing

## Available checks

- `cd frontend && npm run lint` runs ESLint.
- `cd frontend && npm run build` runs the TypeScript validation and optimized Next.js production build.
- The repository currently has no frontend unit/component/E2E test framework. No new testing dependency was added.
- `cd .. && .venv/bin/python -m pytest -q` covers backend contracts and authentication/document isolation, not browser rendering.

## Coverage and gaps

Frontend implementation uses actual FastAPI endpoints and keeps private response data in React memory. The production build verifies TypeScript/routes and lint checks source style, but does not simulate interactions, screen readers, upload interruptions, account switching, or live backend responses. Those require adding a component/E2E test runner and a test API environment. No live S3/Qdrant, PostgreSQL RLS, or LLM provider is exercised by frontend checks.
