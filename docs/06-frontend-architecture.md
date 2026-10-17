# Frontend architecture

The frontend is a Next.js App Router application in `frontend/`, using React components and TypeScript. `frontend/app/layout.tsx` supplies the root shell; route folders contain login/register, dashboard, documents, document detail/review, upload, reports, assistant, privacy and terms pages.

## API and session behavior

`frontend/lib/api.ts` reads only `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). It provides JSON and authenticated fetch wrappers with a 15-second default timeout, a 110-second assistant timeout, and a 120-second XMLHttpRequest upload timeout/progress callback. Bearer tokens are attached by the caller. Error payloads are mapped to user-facing messages; the client does not receive AWS, Qdrant or LLM credentials.

`frontend/lib/session.ts` stores `niramaya_access_token` in browser `sessionStorage`, clears it after a 401, and redirects through the router. Since this storage is readable by same-origin JavaScript and there is no server-side session/cookie boundary here, XSS protection remains important. Route pages implement client-side session checks; the API remains the actual access-control boundary.

## User experience behaviors

Pages call typed API functions and surface loading, empty and failure states. Upload progress reflects bytes sent, not processing completion. Document status and indexing status are separate. Assistant responses carry answer, citations, evidence and generation status; UI source display does not authorize a document by itself.

## Tests and gaps

The repository has no frontend unit, component, or browser E2E test runner configured. CI runs ESLint, `tsc --noEmit`, and a production Next build. Those checks validate static/build correctness, not user workflows, token exposure, API compatibility or browser accessibility. See [frontend testing notes](frontend/testing.md).
