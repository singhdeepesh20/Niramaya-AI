# Project overview

Niramaya-AI is a web application for a user to store medical reports, inspect locally extracted text and structured findings, and ask questions against that user's authorized records. The browser is a Next.js App Router application. A FastAPI service authenticates accounts and coordinates PostgreSQL, private S3 storage, a database-backed worker, optional local embeddings/Qdrant retrieval, and optional Groq-compatible answer generation.

## Product boundary

The product organizes records and returns evidence with source-document/page references. Its deterministic parser recognizes a finite set of report labels, values, units, report sections, and document-type indicators. The optional language model phrases answers from retrieved excerpts. Neither path is a validated diagnostic device, clinician, emergency triage service, or guarantee of extraction correctness. Users must review source pages and consult a qualified professional for medical decisions.

## User-visible workflows

1. Register or sign in with username and password; a bearer JWT is held in browser `sessionStorage`.
2. Upload a PDF, JPEG, or PNG; the API validates the file, writes the original to S3, then stores owner-linked metadata and a processing job in PostgreSQL.
3. A separate worker extracts text/OCR, tables and deterministic findings, then records stage/state results. The UI polls/loads status and exposes results, pages, tables and history.
4. An indexing job chunks current extraction output and, when configured, creates local vectors and writes them to Qdrant. PostgreSQL remains canonical; lexical search works when chunks are persisted but vector indexing is absent or unavailable.
5. The protected assistant performs user-scoped hybrid retrieval, validates vector candidates against PostgreSQL, and optionally sends authorized evidence to the configured LLM. It returns answer, evidence, citations and generation status.
6. Owner-only deletion marks work pending, removes S3/Qdrant data through a retryable job, then cascades database records.

## Components and status

| Area | Current implementation | Verification boundary |
| --- | --- | --- |
| Account API | FastAPI, Argon2 password hash, HS256 JWT, current-user lookup | API tests use SQLite |
| Web UI | Next.js 15, React 19, TypeScript, client-side pages | lint/type/build checked locally; no browser E2E suite |
| Structured data | Async SQLAlchemy and PostgreSQL-oriented Alembic schema | schema tests use SQLite; live PostgreSQL needs its own migration/schema audit |
| Source documents | Private S3 API, generated object keys, short-lived presigned GET | fake storage in unit tests; live AWS status must be reported separately |
| Extraction | PyMuPDF, optional local Tesseract, explicit deterministic rules | synthetic PDF/image tests |
| Work queue | PostgreSQL outbox/lease polling worker | test DB and fake storage; single simple polling process is the provided runner |
| Vectors | local Sentence Transformers embeddings and Qdrant REST client | fake vector client tests; live collection/auth are environment-dependent |
| Answer generation | OpenAI-compatible HTTP Chat Completions configured for Groq | mocked provider tests; live provider calls are not implied |

## Deployment reality

Repository workflows provide CI, not an application deployment. There are no checked-in Terraform, Kubernetes, container, or hosted deployment manifests in this repository. Production runtime, network boundaries, backup policy, secret manager, scaling and alerting must be supplied by the deployment owner; see [deployment](deployment.md) and [limitations](32-known-limitations-and-roadmap.md).
