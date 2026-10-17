# Data-flow catalogue

| Flow | Reads | Writes / external side effect | Authorization and evidence |
| --- | --- | --- | --- |
| Register | Registration DTO, duplicate lookup | Argon2 hash + `users` transaction | Public response excludes hash; auth tests. |
| Login | Username row/hash | HS256 bearer token | Generic invalid-credential error; rate limit. |
| Upload | File header/name/type/size, verified user | Private S3 object, document row, process job and event | Owner derived from dependency; S3/DB compensation on SQL failure. |
| Process | Owner/job/document, S3 bytes | Temporary local file; extraction results/pages/tables/stages/events | Job carries owner; temporary directory; generation and owner filters. |
| Index | Current-generation page/table/entity output | PostgreSQL chunks, optional local embeddings/Qdrant points and status | Server supplies owner/document metadata; failure preserves lexical chunks. |
| Ask | Verified user, question and filters, Qdrant IDs, PostgreSQL chunks | Optional LLM request; user chat row | Mandatory server filters plus PostgreSQL revalidation before evidence. |
| View/download | Owner document/object key | Presigned GET URL | Ownership check before issuing short-lived bearer URL. |
| Delete | Owner document and pending job | S3 delete, scoped vector delete, DB cascade | Cleanup is retryable; partial external data may remain on exhaustion. |

The default pipeline does not send source documents or extraction content to Groq. The Q&A flow sends only the question and backend-authorized evidence when generation is enabled. Cloud services may still receive operational metadata or vectors; review provider processing terms and data regions before real records.
