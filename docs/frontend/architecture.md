# Frontend architecture

## Stack and routes

The frontend is Next.js 15 App Router with React 19 and TypeScript. Styling uses shared CSS files; there is no Tailwind or component library. Current routes are `/login`, `/register`, `/dashboard`, `/documents`, `/documents/upload`, `/documents/[documentId]`, `/documents/[documentId]/review`, `/assistant`, and the pre-existing `/reports` alias. Document listing and upload reuse the reports library component.

## UI and data

`frontend/lib/api.ts` is the typed API boundary. It uses the configured API base, bearer authentication from the existing tab-scoped session, no-store authenticated fetches, safe user-facing errors, and XHR only for upload progress. Page state is held in React memory; no medical document, chat response, or API response is written to browser storage. A document detail page polls its owner-authorized detail endpoint with one scheduled request at a time while the status is `uploaded`, `queued`, `processing`, or `deletion_pending`; requests back off to 30 seconds after errors and stop on review, completed, or failed. A user can refresh manually.

## Responsibilities

The backend owns authentication, user isolation, uploads, state transitions, processing, review validation, secure presigned URLs, retrieval, citations, and chat history. The frontend displays returned states/data and submits explicit actions. It never calculates completion, constructs object-storage URLs, or supplies a user ID for health retrieval. The backend currently has no entity, extraction confidence, processing event, or review-field read APIs; corresponding detail sections say so rather than rendering mock data.
