# Configuration reference

Source of truth: `app/core/config.py`; frontend reads only `NEXT_PUBLIC_API_BASE_URL`. Backend setting names are case-sensitive. **Secret** values must come from ignored local configuration or a secret manager and must never appear in docs/CI output. Blank optional provider values disable or defer that integration.

| Variable | Required/default | Purpose / validation | Classification / failure |
| --- | --- | --- | --- |
| `DATABASE_URL` | Required | Must use `postgresql+asyncpg`, `postgresql+psycopg`, or `sqlite+aiosqlite` scheme. | Secret; empty/unsupported fails settings construction. |
| `JWT_SECRET_KEY` | Required | At least 32 UTF-8 bytes, enough character diversity; rejects common replacement markers. | Secret; weak value fails startup. |
| `JWT_ALGORITHM` | `HS256` only | Literal setting; decoder pins the configured algorithm. | Security setting; other values fail validation. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30; 1–1440 | Access-token lifetime. | Security setting; out of range fails. |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Optional empty→None | Optional claims; if set, included and required at decode. | Sensitive config; invalid token claim returns 401. |
| `FRONTEND_ORIGINS` | `[]` | Explicit HTTPS origins; localhost HTTP allowed; no wildcard/path/query/userinfo. | Public config; invalid origin fails. |
| `LLM_API_BASE_URL` | Groq-compatible API base | HTTP(S), HTTPS except localhost, no embedded auth/query/fragment. | Public endpoint; malformed value fails. |
| `LLM_API_KEY` | Optional | Bearer credential for chat completion. | Secret; missing means evidence-only; invalid provider key returns safe 503. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Provider model identifier. | Public config; model/provider mismatch fails request. |
| `LLM_TIMEOUT_SECONDS` | 90; >0 and <=120 | HTTP timeout for LLM and reused vector client operations. | Availability config; validation failure. |
| `RAG_GENERATION_ENABLED` | `true` | Enables generation only when key also exists. | Feature flag; false returns evidence-only. |
| `RAG_TOP_K` | 5; 1–20 | Final hybrid candidate count. | Retrieval config. |
| `RAG_MAX_CONTEXT_CHARS` | 12000; 1000–50000 | Total evidence context bound. | Data-minimization config. |
| `HEALTH_RETRIEVAL_LIMIT` | 8; 1–30 | Declared in settings but has no current application call site; changing it has no effect today. | Unused config; candidate for removal or wiring in a reviewed code change. |
| `HEALTH_CANDIDATE_LIMIT` | 30; 1–100 | Qdrant candidate count. | Retrieval config. |
| `HEALTH_VECTOR_INDEX_REQUIRED` | `false` | Controls adapter-mode required vector stage; default deterministic path tracks index separately. | Workflow config. |
| `QDRANT_URL` | Optional | HTTP(S), HTTPS except localhost, no embedded credential/query/fragment. | Endpoint metadata; missing disables semantic indexing/search. |
| `QDRANT_API_KEY` | Optional | Qdrant `api-key` header. | Secret; auth failure safely degrades retrieval / marks indexing failed. |
| `QDRANT_COLLECTION` | `niramaya_medical_chunks` | Collection name. | Resource identifier; indexing may create it when absent. |
| `EMBEDDING_PROVIDER` | `local` only | Provider literal. | Other provider fails validation. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Local model name. | Model identifier; weight/cache availability not checked at settings load. |
| `EMBEDDING_MODEL_REVISION` | `main` | Model revision. | Model identifier; production should pin reviewed commit. |
| `EMBEDDING_MODEL_PATH` | Optional | Existing local model path override. | Filesystem path; missing weights fail inference safely. |
| `EMBEDDING_DEVICE` | `cpu` | Sentence Transformers device. | Runtime config; hardware compatibility unverified. |
| `EMBEDDING_BATCH_SIZE` | 32; 1–128 | Local batch size. | Resource config. |
| `EMBEDDING_DIMENSION` | 384; 1–4096 | Expected output/Qdrant vector size. | Schema compatibility; mismatch marks indexing failure. |
| `EMBEDDING_ALLOW_DOWNLOAD` | `false` | Allows library remote weight fetch if true. | Supply-chain/network setting; keep false and pre-provision reviewed weights in production. |
| `CHUNK_SIZE_CHARS` | 1200; 300–5000 | Page-local chunk cap. | Retrieval config. |
| `CHUNK_OVERLAP_CHARS` | 160; 0–1000 | Overlap, must also be less than chunk size at chunk function. | Retrieval config. |
| `AWS_REGION` | `eu-north-1` | Region passed to Boto3. | Public config; wrong region categorized on live request. |
| `S3_BUCKET_NAME` | Optional | Private source bucket; required for storage operations. | Resource name; absent makes operations unavailable. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Optional pair | Static SDK credentials; Boto3 chain otherwise. | Secrets; partial pair fails safely. Prefer short-lived role credentials. |
| `AWS_SESSION_TOKEN` | Optional | Temporary AWS session credential. | Secret. |
| `S3_PRESIGNED_URL_EXPIRES_SECONDS` | 300; 60–900 | Presigned GET lifetime. | Access setting; URL is a bearer token until expiry. |
| `S3_MAX_UPLOAD_BYTES` | 15,000,000; 1,000,000–100,000,000 | Upload and worker source byte bound. | Resource limit. |
| `DOCUMENT_MAX_PAGES` | 250; 1–2000 | PDF page bound. | Resource limit. |
| `DOCUMENT_MAX_TEXT_CHARS` | 2,000,000; 10,000–20,000,000 | Total extracted text bound. | Resource limit. |
| `OCR_ENABLED` | `true` | Allows local OCR attempt for low-text pages. | Feature config; executable still required. |
| `TESSERACT_CMD` | Optional | Explicit local Tesseract executable path; PATH discovery otherwise. | Local path. |
| `OCR_LANGUAGE` | `eng` | Tesseract trained-data language. | Runtime config; absent language yields safe OCR warning. |
| `OCR_DPI` | 200; 100–400 | Page rasterization resolution. | Resource config. |
| `OCR_TIMEOUT_SECONDS` | 30; 1–180 | Per-page OCR timeout. | Availability config. |
| `OCR_MIN_TEXT_CHARS` | 20; 0–1000 | Below this embedded text count, OCR is considered. | Processing rule. |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend default `http://localhost:8000` | Browser-visible API base URL. | Public; never place any secret in a `NEXT_PUBLIC_*` variable. |

No worker-specific queue, logging, or metrics setting is defined in `Settings` today. `.env.example` is an example, not proof every cloud setting works. `get_settings()` is cached; restart API/worker after changing environment.
