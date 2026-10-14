# Frontend security and privacy

- The existing backend contract returns a bearer token. The frontend retains it in `sessionStorage` for the active tab only; logout and a 401 clear it. `localStorage` is not used. An HTTP-only, secure, same-site cookie contract would improve token protection but would require coordinated backend and CSRF work.
- Every protected API call includes the token and is fetched with `cache: "no-store"`. No patient data, report content, chat responses, query cache, or document IDs are persisted in browser storage. The frontend has no analytics/service worker or application logging of health data.
- Uploaded/OCR text and AI answers are rendered as React text, never injected with `dangerouslySetInnerHTML`. AI answers are plain text (not rendered as HTML/Markdown). Citations link to the owner-scoped application detail route.
- Secure view/download URLs are requested on demand and not persisted. Preview uses a backend-generated expiring URL and `referrerPolicy="no-referrer"`; the UI never guesses public object URLs.
- Logout clears session state. There is no persistent client query cache to leak between accounts. Sign-in removes a prior tab user-cache key defensively.
- Frontend route checks are for user experience only; backend authentication/owner filters authorize every operation. 401 clears the session; 403 shows an access error without exposing server detail.

Known limitation: bearer tokens are accessible to same-origin JavaScript while present in sessionStorage. Coordinate a cookie-based migration with the backend before production if the security model requires protection from script access.
