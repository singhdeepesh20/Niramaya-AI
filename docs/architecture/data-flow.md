# Medical document processing data flow

```mermaid
flowchart LR
  U[Authenticated user] -->|PDF + JWT| API[FastAPI document API]
  API -->|owner ID from JWT| DB[(PostgreSQL: document + outbox)]
  API -->|server-generated key| S3[(Private S3 bucket)]
  DB --> W[Polling worker]
  W -->|owner-scoped document lookup| DB
  W -->|private download to temp directory| S3
  W --> P[PyMuPDF + deterministic rules]
  P -->|pages, tables, findings, provenance| DB
  UI[Next.js document detail] -->|JWT| API
  API -->|owner-filtered result endpoints| UI
```

The deterministic extraction/parser stage does not call an LLM, generative model, hosted embedding API, or remote OCR service. After extraction, the worker may run local embeddings and contact configured Qdrant for indexing. Result records are visible only through authenticated endpoints that resolve ownership from the verified token. Original files stay in private S3; temporary source/conversion files are removed after processing.
