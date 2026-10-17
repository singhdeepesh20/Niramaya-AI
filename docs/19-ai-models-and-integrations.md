# AI models and external integrations

| Integration | Role | Configuration | Behavior/status |
| --- | --- | --- | --- |
| PyMuPDF | PDF text/table processing | Python dependency | Local parser; synthetic fixture tests. |
| Tesseract + pytesseract | OCR for low-text pages/images | `OCR_*`, system executable/language data | Optional external binary; missing OCR yields warning/review, not fabricated text. |
| Sentence Transformers | Local embedding for indexing/query | model/revision/path/device/batch/dimension/download settings | Lazy local inference; weight availability and hardware are environment-specific. |
| Qdrant Cloud or local | Vector candidate index | `QDRANT_URL`, optional key, collection | REST; optional. Collection is created if missing during indexing. Live connection not inferred from unit tests. |
| Groq-compatible endpoint | Answer generation | base URL, model, optional API key, enable flag, timeout | OpenAI-compatible chat completions; only authorized retrieved context is sent. Live API verification is separate. |
| Amazon S3 | Private original-file storage | region, bucket, SDK credential chain, URL TTL | Boto3; source bytes require live IAM/bucket validation. |
| PostgreSQL | Canonical account/document/results/jobs/chat data | `DATABASE_URL` | Async SQLAlchemy; Alembic-managed schema and PostgreSQL RLS. |

There is no remote LLM used by the deterministic extraction pipeline. Embeddings and answer generation are independent: a report can be extracted without an LLM, and an answer can be evidence-only without a generation key. Do not send real health data to an external model until data-protection terms, retention, region, consent and deployment controls are reviewed.
