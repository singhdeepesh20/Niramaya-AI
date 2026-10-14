# Document processing access control

The authenticated user ID is taken from the verified JWT dependency. Every result endpoint first loads an owner-authorized document, then filters child rows by authenticated user ID, document ID, and active extraction generation. A second account receives the same not-found response for another user's document. PostgreSQL forced RLS policies cover extracted pages and tables; composite owner/document foreign keys prevent mismatched ownership.

Private S3 object keys are server generated. Workers take the owner ID from the durable job and apply tenant context before document reads and writes. Source documents and extracted page text are untrusted data. The processing pipeline uses only explicit local parsing rules and never executes embedded instructions or calls tools. No LLM is part of this pipeline.

Logs must not contain document content, excerpts, object keys, credentials, or extracted values. API output exposes only the current user's records and safe processing metadata.
