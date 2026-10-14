# Extraction provenance

Every extracted laboratory finding stores a one-based PDF page number, the matched display alias, a bounded excerpt from the source line, extraction method (`rule_based`), deterministic rule version, quality score, warnings, and extraction generation. Page records store full extracted page text, method (text or OCR), character count, OCR state, and warnings. Detected tables store page and table index with headers and rows.

The `quality_score` describes parser evidence completeness (for example, whether an exact alias, value, and unit were found). It is not a probability that a result is clinically correct. `reported_abnormal` is set only from an explicit high/low/abnormal flag in the source; values are not judged against inferred reference ranges. The UI should preserve the provided excerpt and page citation and should not turn extraction output into a diagnosis.

Source PDFs remain in private object storage. Extracted text and structured records are sensitive health data, protected by owner-scoped queries and PostgreSQL tenant policies. Logs contain safe reason codes and operational counts only.
