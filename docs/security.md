# Security and privacy controls

This guide describes the controls present in the repository and the operational work still required. It is not a security certification or a claim of regulatory compliance. Do not use real patient data until the deployment, organization, and applicable legal requirements have been reviewed.

## Secrets and exposed credentials

- Keep local values in ignored `.env` files or an approved deployment secret manager. Commit only placeholders from `.env.example`.
- Do not place credentials in frontend variables, screenshots, issue reports, test fixtures, shell history, logs, or documentation.
- Use a distinct, randomly generated JWT signing secret per environment. Rotate it when exposed; rotation invalidates tokens signed with the previous value.
- Prefer IAM roles or short-lived AWS credentials over long-lived access keys. Use separate, least-privilege credentials per environment and revoke exposed keys promptly.
- Limit Qdrant and LLM API keys to the intended project/account and rotate them after exposure.
- Do not rewrite shared Git history or force-push to remove credentials without coordinating with repository collaborators. Rotation is still required even after history cleanup.

## Authentication and authorization

- Passwords are hashed with Argon2id. Login and question endpoints have process-local rate limits; a multi-instance deployment needs a shared limiter or gateway policy.
- Authentication supports backend-managed `HttpOnly`, `SameSite` cookies (`niramaya_access_token`) alongside `Authorization: Bearer` token headers for programmatic API clients. In production, cookies are enforced with `Secure=True`.
- CSRF protection is enforced on all state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) using origin verification and a double-submit cookie pattern (`niramaya_csrf_token` cookie and `X-CSRF-Token` header).
- Standard HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`) are attached to all API responses.
- Every document, extracted result, chunk, and chat-history operation must be scoped to the verified user. Never accept an owner ID from the request body or an LLM response as authorization.
- PostgreSQL queries include explicit owner predicates. RLS adds a second boundary, but the runtime database role must not be a superuser or have `BYPASSRLS`.
- Qdrant filters are constructed by the backend. Re-resolve vector result IDs against PostgreSQL ownership and active document generation before using text as evidence.

## Medical documents and external services

- Upload routes accept supported file types and sizes, generate object keys on the server, and bind document operations to the authenticated owner.
- Keep S3 private. Do not enable public ACLs or public bucket policies. Use short-lived presigned URLs only after checking document ownership.
- Treat uploaded text as untrusted input. The deterministic processing pipeline does not execute document instructions. The RAG prompt marks retrieved text as data, exposes no tools, and the backend authorizes evidence before sending it to an optional LLM.
- An LLM answer is informational support, not a diagnosis. Verify provider data-handling terms before sending any health information to an external service. Evidence and citations do not replace clinical review.

## Logging and API errors

- Do not log passwords, bearer tokens, API keys, database URLs, object keys, report text, extracted values, or LLM prompts/responses.
- Log request IDs and safe error categories. Return generic client errors rather than SQL, cloud-provider, or stack-trace details.
- Review log retention and access controls in each deployment; this repository cannot enforce infrastructure-level retention.

## Incident response for a leaked key

1. Revoke the exposed credential at its provider immediately; do not wait for a code cleanup.
2. Issue a replacement with least-privilege access and update the local secret manager or deployment environment without pasting the value into chat or source control.
3. Restart affected processes so they load the replacement, then verify authentication using a safe, read-only check before any write operation.
4. Review provider audit logs for use during the exposure window and rotate dependent sessions or JWT signing keys as appropriate.
5. Scan the current tree and Git history. Coordinate history cleanup with repository owners if required; never force-push shared history without approval.

## Known limits to address before production

- The process-local rate limiter does not coordinate across API workers (requires distributed Redis token bucket).
- Account-wide deletion, MFA, email verification, and security audit trails are not implemented.
- Automated tests use synthetic data and test doubles; they do not prove that a live AWS, PostgreSQL, Qdrant, or LLM account is correctly configured.
- No healthcare regulatory compliance assessment is included.

See [user-scoped retrieval](security/user-scoped-retrieval.md), [access control](security/access-control.md), and [deployment guidance](deployment.md) for related controls.
