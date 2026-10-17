# Security and privacy

## Sensitive assets

Account identifiers/password hashes, JWTs, source reports, extracted page text/entities, embeddings, chat questions/answers/citations, object keys, cloud credentials and presigned URLs are sensitive. Medical content is not written intentionally to logs. Do not put actual records in fixtures, screenshots, issue reports or docs.

## Existing controls and evidence

| Boundary | Current control | Evidence/limit |
| --- | --- | --- |
| Credentials at rest | Argon2 password hash; signing/provider secrets as `SecretStr`; local `.env` ignored | Auth/config tests; a copied historical credential still needs history review. |
| Authentication | HS256 pinned, expiry/issuer/audience checks, DB-backed active user lookup | `tests/test_auth_api.py`; process-local login throttle. |
| Document authorization | JWT subject used; explicit owner/document/current-generation SQL filters; 404 for non-owner | document and health isolation tests; SQLite does not test RLS. |
| Database defense | tenant transaction setting, RLS migrations, composite owner/document FKs | Verify deployed policies, grants and non-bypass runtime role. |
| Source files | generated keys, private S3 operations, owner check before presign; no public ACL setting | fake storage tests do not verify AWS bucket policy/IAM. |
| Vector isolation | server-owned mandatory user filter; PostgreSQL revalidation before context | fake-client tests; deployed collection payload/permissions remain operational concerns. |
| Prompt injection | evidence treated as untrusted, no tools, instruction in system prompt | prompt is not an authorization boundary; authorization is performed before generation. |
| Error handling/logging | generic client messages, request ID, error type/category logs | review deployment reverse-proxy and SDK logs too. |
| Browser token | sessionStorage and 401 cleanup | XSS can read token; no HttpOnly-cookie design or CSP guarantee is checked into app config. |

## Secret handling / incident response

1. Revoke/rotate any key, password or signing secret pasted into chat, committed or logged; treat it as compromised.
2. Update the secret manager/local ignored `.env`, restart dependent services, and invalidate sessions if JWT signing key changed.
3. Review provider/AWS audit logs for use since exposure; remove unauthorized access and preserve incident evidence safely.
4. Search current files, full Git history, CI artifacts and logs without printing secret values.
5. If the history contains a real credential, coordinate a backup and approved repository history rewrite with all collaborators; rotate first. Do not force-push without explicit authorization.

## Audit note (2026-10-15)

The local root `.env` and frontend `.env.local` were ignored and not tracked at audit time. A history review found a `JWT_SECRET_KEY` assignment with no placeholder wording in `README.md` at commit `790e16cd607f` (line 195); its value is intentionally omitted. This is a **possible secret/sample**, not confirmed as an active signing key. Verify against the key owner and rotate if it was ever used. No AWS access-key, Groq-key, Qdrant-token, or private-key pattern was found in the scanned tracked history; the review is pattern-based and not a proof that every possible credential is absent.

Credentials were also shared in the conversation context during this documentation task. Treat each as exposed and rotate/revoke through its issuer; this manual does not reproduce them.

No compliance certification is claimed. Complete threat assessment, consent/data-processing agreements, retention, data residency, encryption, incident response and independent review before handling real patient records. Related detail: [threat model](35-threat-model.md), [access control](security/access-control.md), [RAG isolation](security/user-scoped-retrieval.md).
