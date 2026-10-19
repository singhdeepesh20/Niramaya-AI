# Known limitations and roadmap

## Confirmed limitations

- Deterministic extraction supports a finite explicit alias/rule set; it is not comprehensive, clinically adjudicated, or diagnosis-capable.
- OCR relies on locally installed Tesseract binary and language data; tests mock or simulate unavailable cases rather than verify a production OCR host.
- Extracted tables depend on PyMuPDF's available table detection and may be incomplete.
- RAG retrieval uses lexical ranking plus Qdrant vector candidates with reciprocal-rank fusion; no separate learned reranker exists.
- LLM evidence grounding is prompt/output constrained, not proof of entailment or medical correctness.
- Frontend token is stored in `sessionStorage`; UI routes are client-side and API authorization is authoritative.
- In-process rate limiting is not shared across API replicas.
- `/health` verifies only the database query; worker/external service readiness is not included.
- Unit tests are SQLite/fake driven; CI separately validates Alembic migrations and RLS schema on disposable PostgreSQL. Neither proves the production PostgreSQL role behavior, AWS, Qdrant or Groq connectivity.
- Production-target API/worker/frontend containers, a local-only Compose environment, and CI migration/image builds are present. No image publishing, hosting IaC, staging deployment, protected-environment promotion, or production release workflow is present.
- No account deletion or full cross-service erase is implemented; this is a production-readiness blocker.
- Backup/restore automation, provider backup configuration verification, and a successful restore drill are absent; recoverability is unverified.
- No frontend component/browser E2E suite is configured.
- No compliance certification or independent security/clinical validation is established.

## Unresolved product/operator questions

- Which report formats, languages, labs and clinical domains must be officially supported, and who validates new extraction rules?
- What human-review process is required before extracted values are treated as trusted by the user?
- Which provider/region/retention terms are acceptable for sending user questions and evidence to an external LLM?
- What are the required retention, consent, export, account deletion, and backup erasure policies?
- Which production PostgreSQL roles/policies and dedicated S3/Qdrant resources are approved, and who owns their live verification?
- Is semantic indexing mandatory for any release, or should lexical-only operation remain a supported degraded mode?
- What are the production availability, RPO/RTO, queue throughput and rate-limit requirements? No measured targets are checked in.

## Recommended work (not implemented)

1. Resolve historic secret candidate and rotate every credential exposed outside the secret manager.
2. Add PostgreSQL RLS integration tests using a least-privilege non-owner runtime role.
3. Add end-to-end tests against disposable S3/Qdrant resources using synthetic data and explicit opt-in.
4. Add distributed rate limiting, CSP/security headers and evaluate HttpOnly-cookie session architecture.
5. Add browser workflow/accessibility tests and an API contract check.
6. Add account deletion/retention and orphan cleanup with documented backup semantics.
7. Add metrics, alerting and rehearsed recovery procedures.
8. Pin production embedding revision and maintain an explicit model/collection migration process.
9. Add image provenance/SBOM, secret scanning, and controlled staging/production workflows only after choosing platform, permissions and approvers.
