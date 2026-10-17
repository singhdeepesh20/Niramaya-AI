# Threat model

This is a code-oriented threat inventory, not a formal penetration test. Likelihood/severity must be assessed for the deployment's network, users and data.

| Threat / asset | Attack path and impact | Existing mitigation/evidence | Residual risk / action |
| --- | --- | --- | --- |
| Cross-user/IDOR (documents, results, chat) | Guess UUID or alter request to read another patient's data | Verified JWT, owner predicates, RLS, 404; two-user isolation tests | Test PostgreSQL policies with real non-owner role; audit every new query. |
| JWT signing-key compromise | Forge bearer token and impersonate all users | SecretStr, minimum length/strength validation, HS256 pinning | Rotate key, invalidate tokens, audit logs; deploy secrets manager. |
| Password compromise | Credential stuffing/account takeover | Argon2, password length bounds, generic errors, login rate limiter | Limiter is process-local; add shared limits/MFA and secure account recovery. |
| Leaked environment file | DB/cloud/model misuse and health-data exposure | `.env` ignore rules; templates placeholders | Verify all histories/backups/artifacts; rotate any exposed value. |
| Malicious PDF/parser exploit or resource exhaustion | Crafted PDF/image targets libraries or exhausts CPU/memory | Signature/type/byte/page/text/pixel limits, OCR timeout, temporary directory | Keep dependencies patched; isolate worker OS/container, add CPU/memory quotas and malware policy. |
| OCR/extraction error | Misread value or clinical misinterpretation | Provenance, warnings, review states, source excerpt/page | Parser is not clinically validated; require human verification and broader test corpus. |
| Prompt injection in report | Extracted text attempts to reveal prompts or access tools | Context marked untrusted; no tools; server authorization precedes LLM | Prompt is not a security boundary; keep authorization and tool policy outside model. |
| Cross-tenant vector result | Qdrant filter omitted/spoofed or payload corrupted | Mandatory owner filter; PostgreSQL chunk re-resolution; tests | Restrict Qdrant network/key; test malicious payloads and deployed collection. |
| Public S3 or URL disclosure | Misconfigured bucket or leaked presigned URL | App never makes bucket public; read-only privacy check; owner presign | Live config can be unverified; block public access, IAM scope, short URL TTL, audit. |
| Cloud credential theft | Exposed IAM/Qdrant/Groq key permits service misuse/data access | SecretStr/ignored env and categorized logs | Rotate immediately; prefer short-lived scoped role; never commit/paste credentials. |
| Sensitive logging | Exception/body includes patient content or token | Logs restrict to exception types/categories | Review proxies, APM, SDK debug logs, request body capture and retention. |
| LLM provider exposure/inaccuracy | Authorized excerpts leave deployment and output may be wrong | Only retrieved evidence sent; timeout; evidence citations; explicit non-diagnosis | Provider data retention/region and output entailment not guaranteed; contractual review. |
| Migration/RLS misconfiguration | Missing policy/grant or superuser bypass breaks isolation | Alembic migrations, explicit SQL owner filters, deployment guidance | SQLite cannot test RLS; verify deployed role and schema, rehearse migrations/backups. |
| DoS / cost amplification | Large uploads, OCR, embeddings, repeated questions/LLM | Size/page/text limits, timeouts, request limits, local rate limit | Per-process limits, no global quotas/concurrency admission; add shared controls/quotas. |

Related implementation details: [security](21-security-and-privacy.md), [auth](09-authentication-and-authorization.md), [file storage](12-file-storage-and-s3.md), [RAG](18-rag-retrieval-and-generation.md).
