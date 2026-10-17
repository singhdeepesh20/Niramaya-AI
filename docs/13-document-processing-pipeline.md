# Document processing pipeline

## End-to-end sequence

1. `POST /api/v1/documents/upload` authenticates, validates type/signature/size, uploads original bytes, inserts `medical_documents`, emits the initial transition event, and creates a durable process job in one PostgreSQL transaction.
2. `app.documents.worker:run_worker` polls every two seconds by default and periodically recovers expired leases. `process_one` claims one due job under row locking (`skip_locked`), increments attempts, and sets a bounded lease.
3. `DeterministicDocumentProcessor` downloads the user's source object into a temporary directory. PDF content is checked by PyMuPDF; JPEG/PNG are converted to a one-page PDF. The temporary directory is cleaned on exit.
4. `extract_pdf` extracts per-page embedded text, attempts table detection, and calls local Tesseract only on low-text pages when OCR is enabled and available. Limits apply to bytes, pages and aggregate text.
5. Explicit keyword rules classify report type; exact aliases parse configured lab labels and explicit report metadata; section rules extract selected imaging/discharge sections. A limited set of explicitly recognized units can be normalized.
6. Worker transaction writes generation-scoped pages, tables and entities, stage outcomes, processing summary and state event. It transitions to `completed` when no review reason exists, otherwise `review_required`.
7. Independent indexing builds deterministic page-local chunks, computes local embeddings if configured, upserts Qdrant points, stores chunk text in PostgreSQL, and records indexing outcome separately. If vector embedding/upsert fails, chunks are still persisted for keyword retrieval and an index retry can be queued.

## What is not in the extraction path

The deterministic document parser does not call Groq or use an LLM. The model score is parser-quality metadata, not a probability of clinical correctness. `medical_document_tables` are stored where PyMuPDF table detection returns a table; table extraction can be absent or incomplete. The API upload response means storage and job queueing succeeded, not extraction completion.

## Operational inputs and outputs

Inputs: private source object, stored document type/date and current extraction generation. Outputs: classification metadata, per-page text/method/OCR state, detected tables, rule-derived entities, stage ledger, events, and optional chunks/vector points. Failures are categorized and stateful; see [stage/state rules](15-document-state-machine.md), [extraction catalogue](14-medical-data-extraction-rules.md), and [runbook](operations/document-processing-runbook.md).

## Status correction

An older paragraph in `docs/medical-data/document-processing.md` incorrectly said indexing was not configured in the worker. Current code invokes `index_document` after deterministic extraction; Qdrant remains conditional on configuration. That focused lifecycle note is maintained alongside this page.
