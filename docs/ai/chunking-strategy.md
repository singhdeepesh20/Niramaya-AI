# Chunking strategy

`app/health/chunking.py` uses deterministic character-bounded, page-local chunks. It retains page provenance, detects common standalone report section headings, prefers paragraph/sentence boundaries, and applies configurable overlap. Structured table headers/rows and extracted entity labels, values, units, reference ranges, and source excerpts are appended to their source page before chunking. Values and units remain together when they occur within the selected boundary; this is a heuristic, not a medical parser.

Chunk IDs are UUIDv5 values derived from document, extraction generation, order, and SHA-256 content hash. `medical_document_chunks` keeps text, source page, section, generation, hash, and model name. No vector payload is copied into PostgreSQL. Settings: `CHUNK_SIZE_CHARS` (1200 default) and `CHUNK_OVERLAP_CHARS` (160 default).
