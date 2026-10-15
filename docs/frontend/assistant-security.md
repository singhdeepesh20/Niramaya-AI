# Assistant frontend security and privacy

- Bearer authentication uses the shared session helper and tab-scoped `sessionStorage` convention already used by the application. The frontend never sends a user ID as authorization proof.
- Health requests use the centralized API client with `cache: no-store`. Questions and medical data are not added to URLs, local storage, or application logs.
- Assistant state is component-local and is discarded when the protected page unmounts. Logout clears the existing session through the shared helper.
- Document selection is a narrowing filter only. The backend must still enforce ownership for PostgreSQL, Qdrant retrieval, citations, history, and document access.
- Answer and excerpt text are rendered as ordinary React text nodes, not injected HTML. Markdown is not interpreted.
- Document links use the authenticated detail page, which obtains private viewing URLs from the backend. No Qdrant key, LLM key, bucket URL, or storage object key is exposed in frontend code.
- Loading and retry labels report only observable request state; they do not claim retrieval or generation progress that the API does not expose.

The frontend cannot establish tenant isolation by itself. Cross-user authorization and the provenance of citations must continue to be verified by backend tests.
