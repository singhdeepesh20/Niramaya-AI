# Authentication and authorization

## Registration and login

`RegistrationRequest` rejects unknown fields, normalizes username/email to lowercase, checks username/email shape and length, and requires a 12–128 character password. `register_user` pre-checks collisions and relies on database unique indexes for races; it hashes with `pwdlib.PasswordHash.recommended()` (Argon2id in the tested configuration) and returns `UserPublic`, never the hash. Login runs a dummy hash verification when the username does not exist to reduce timing distinction, then returns a generic credential error. Inactive accounts receive 403.

## JWT validation

`create_access_token` signs HS256 tokens with `sub` UUID, `iat`, `exp`, and optional issuer/audience. Expiry defaults to 30 minutes and is bounded to 1–1440. `get_current_user` pins the allowed algorithm to HS256, requires `sub/iat/exp`, conditionally requires configured issuer/audience, parses UUID and resolves the user row. Missing/deleted/invalid token is 401; inactive account is 403. There is no refresh-token or revocation list; changing the signing key invalidates outstanding tokens.

## Ownership enforcement

Every document endpoint obtains the subject through `get_current_user`. Queries bind both document ID and `user.id`; children additionally bind owner, document and current extraction generation. RAG schemas use `extra="forbid"`, and `user_id` is not an accepted input. The backend constructs Qdrant filters and independently resolves returned chunk IDs through SQL. PostgreSQL tenant context is transaction-local via `set_config`; explicit owner predicates remain required. Composite owner/document foreign keys and cascade constraints prevent mismatched child rows.

## Browser token storage and operational limitations

The frontend stores its bearer token in `sessionStorage`, not an HttpOnly cookie. A browser XSS can access it; enforce CSP and carefully review injected HTML/dependencies at deployment. Login/assistant throttles are in-memory process-local limiters, so replicas do not share quotas. Put shared throttling at a trusted gateway or replace the limiter before multi-instance high-risk use.

See [security controls](security.md), [access-control notes](security/access-control.md), and [cross-user tests](reference/verification-matrix.md).
